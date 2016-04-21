import os
import json
import subprocess
import itertools
from datetime import datetime

import elasticsearch
import elasticsearch.helpers


M_HAS_CLOUDIFY_EVENTS = 'has_cloudify_events'

STORAGE_INDEX_NAME = 'cloudify_storage'
EVENTS_INDEX_NAME = 'cloudify_events'

_INFLUXDB = 'influxdb_data'
_INFLUXDB_DUMP_CMD = ('curl -s -G "http://{0}:{1}/db/cloudify/series'
                      '?u=root&p=root&chunked=true" --data-urlencode'
                      ' "q=select * from /.*/" > {2}')
_INFLUXDB_RESTORE_CMD = ('cat {0} | while read -r line; do curl -X POST '
                         '-d "[${{line}}]" "http://{1}:{2}/db/cloudify/'
                         'series?u=root&p=root" ;done')
_ELASTICSEARCH = 'es_data'

# This variable also appears in cloudify_plugins_common.cloudify.constants
#  and values should be aligned.
COMPUTE_NODE_TYPE = 'cloudify.nodes.Compute'


def local_restore_elasticsearch_data(data_dir_path, endpoint, port):
    es = elasticsearch.Elasticsearch(hosts=[{'host': endpoint,
                                             'port': port}])
    metadata = {'has_cloudify_events': _snapshot_has_events(data_dir_path)}
    restore_elasticsearch(data_dir_path, es, metadata)


def local_dump_elasticsearch_data(dump_dir_path, endpoint, port=9200):
    es = elasticsearch.Elasticsearch(hosts=[{'host': endpoint,
                                             'port': port}])
    dump_elasticsearch(dump_dir_path, es, snapshot_dump=False)


def local_dump_influxdb_data(data_dir_path, endpoint, port):
    dump_influxdb(data_dir_path, endpoint, port)


def local_restore_influxdb_data(data_dir_path, endpoint, port):
    restore_influxdb_3_3(data_dir_path, endpoint, port)


def restore_elasticsearch(tempdir, es, metadata):

    has_cloudify_events_index = es.indices.exists(index=EVENTS_INDEX_NAME)
    snap_has_cloudify_events_index = metadata[M_HAS_CLOUDIFY_EVENTS]

    # cloudify_events -> cloudify_events, logstash-* -> logstash-*
    def get_data_itr():
        for line in open(os.path.join(tempdir, _ELASTICSEARCH), 'r'):
            elem = json.loads(line)
            _update_es_node(elem)
            yield elem

    _check_conflicts(es, get_data_itr())

    # logstash-* -> cloudify_events
    def logstash_to_cloudify_events():
        for elem in get_data_itr():
            if elem['_index'].startswith('logstash-'):
                elem['_index'] = EVENTS_INDEX_NAME
            yield elem

    def cloudify_events_to_logstash():
        d = datetime.now()
        index = 'logstash-{0}'.format(d.strftime('%Y.%m.%d'))
        for elem in get_data_itr():
            if elem['_index'] == EVENTS_INDEX_NAME:
                elem['_index'] = index
            yield elem

    # choose iter
    if (has_cloudify_events_index and snap_has_cloudify_events_index) or \
            (not has_cloudify_events_index and
                not snap_has_cloudify_events_index):
        data_iter = get_data_itr()
    elif not snap_has_cloudify_events_index and has_cloudify_events_index:
        data_iter = logstash_to_cloudify_events()
    else:
        data_iter = cloudify_events_to_logstash()

    elasticsearch.helpers.bulk(es, data_iter)
    es.indices.flush()


def dump_elasticsearch(tempdir, es, snapshot_dump=True, execution_id=None):
    has_cloudify_events = es.indices.exists(index=EVENTS_INDEX_NAME)
    storage_scan = elasticsearch.helpers.scan(es, index=STORAGE_INDEX_NAME)
    if snapshot_dump:
        storage_scan = _except_types(storage_scan,
                                     'provider_context',
                                     'snapshot')
        storage_scan = (e for e in storage_scan
                        if e['_id'] != execution_id)

    event_scan = elasticsearch.helpers.scan(
            es,
            index=EVENTS_INDEX_NAME if has_cloudify_events else 'logstash-*'
    )

    with open(os.path.join(tempdir, _ELASTICSEARCH), 'w') as f:
        for item in itertools.chain(storage_scan, event_scan):
            f.write(json.dumps(item) + os.linesep)


def dump_influxdb(tempdir, endpoint='localhost', port=8086):
    influxdb_file = os.path.join(tempdir, _INFLUXDB)
    influxdb_temp_file = influxdb_file + '.temp'
    cmd = _INFLUXDB_DUMP_CMD.format(endpoint, str(port), influxdb_temp_file)
    rcode = subprocess.call(cmd, shell=True)
    if rcode != 0:
        raise RuntimeError('Error running dump InfluxDB data cmd {0}, '
                           'error code: {1}'.format(cmd, rcode))
    with open(influxdb_temp_file, 'r') as f, open(influxdb_file, 'w') as g:
        for obj in _get_json_objects(f):
            g.write(obj + os.linesep)

    os.remove(influxdb_temp_file)


def restore_influxdb_3_3(tempdir, endpoint='localhost', port=8086):
    influxdb_f = os.path.join(tempdir, _INFLUXDB)
    if os.path.exists(influxdb_f):
        rcode = subprocess.call(_INFLUXDB_RESTORE_CMD.format(influxdb_f,
                                                             endpoint, port),
                                shell=True)
    if rcode != 0:
        raise RuntimeError('Error during restoring InfluxDB data, '
                           'error code: {0}'.format(rcode))


def _get_json_objects(f):
    def chunks(g):
        ch = g.read(10000)
        yield ch
        while ch:
            ch = g.read(10000)
            yield ch

    s = ''
    n = 0
    decoder = json.JSONDecoder()
    for ch in chunks(f):
        s += ch
        try:
            while s:
                obj, idx = decoder.raw_decode(s)
                n += 1
                yield json.dumps(obj)
                s = s[idx:]
        except:
            pass

    # assert not n or not s
    # not (not n or not s) -> n and s
    if n and s:
        raise RuntimeError('Error during converting InfluxDB dump '
                           'data to data appropriate for snapshot.')


def _check_conflicts(es, restored_data):
    """
    Check names conflicts in restored snapshot and manager.
    If in restored snapshot there are blueprints/deployments then
    manager cannot contain any blueprints/deployments with the same names.

    :param es: ElasticSearch proxy object
    :param restored_data: iterator to snapshots Elasticsearch data that
        is supposed to be restored
    """

    old_data = elasticsearch.helpers.scan(es, index=STORAGE_INDEX_NAME,
                                          doc_type='blueprint,deployment')
    old_data = list(old_data)
    # if there is no data in manager then just return
    if not len(old_data):
        return

    blueprints_names = [e['_id'] for e in old_data
                        if e['_type'] == 'blueprint']
    deployments_names = [e['_id'] for e in old_data
                         if e['_type'] == 'deployment']

    exception_message = 'There are blueprints/deployments names conflicts ' \
                        'in manager and restored data: blueprints {0}, ' \
                        'deployments {1}'
    blueprints_conflicts = []
    deployments_conflicts = []

    for elem in restored_data:
        if elem['_type'] == 'blueprint':
            if elem['_id'] in blueprints_names:
                blueprints_conflicts.append(elem['_id'])
        else:
            if elem['_id'] in deployments_names:
                deployments_conflicts.append(elem['_id'])

    if blueprints_conflicts or deployments_conflicts:
        raise RuntimeError(
                exception_message.format(blueprints_conflicts,
                                         deployments_conflicts)
        )


def _except_types(s, *args):
    return (e for e in s if e['_type'] not in args)


def _add_operation(operations, op_name, inputs, implementation):
    if op_name not in operations:
        operations[op_name] = {
            'inputs': inputs,
            'has_intrinsic_functions': False,
            'plugin': 'agent',
            'retry_interval': None,
            'max_retries': None,
            'executor': 'central_deployment_agent',
            'operation': implementation
        }


def _snapshot_has_events(data_dir_path):
    with open(os.path.join(data_dir_path, _ELASTICSEARCH)) as f:
        lines = f.readlines()
    for line in lines:
        index_data = json.loads(line)
        if index_data['_index'] == EVENTS_INDEX_NAME:
            return True
    return False


def _update_es_node(es_node):
    if es_node['_type'] == 'deployment':
        workflows = es_node['_source']['workflows']
        if 'install_new_agents' not in workflows:
            workflows['install_new_agents'] = {
                'operation': 'cloudify.plugins.workflows.install_new_agents',
                'parameters': {
                    'install_agent_timeout': {
                        'default': 300
                    },
                    'node_ids': {
                        'default': []
                    },
                    'node_instance_ids': {
                        'default': []
                    }
                },
                'plugin': 'default_workflows'
            }
    if es_node['_type'] == 'node':
        source = es_node['_source']
        type_hierarchy = source.get('type_hierarchy', [])
        if COMPUTE_NODE_TYPE in type_hierarchy:
            operations = source['operations']
            _add_operation(operations,
                           'cloudify.interfaces.cloudify_agent.create_amqp',
                           {
                               'install_agent_timeout': 300
                           },
                           'cloudify_agent.operations.create_agent_amqp')
            _add_operation(operations,
                           'cloudify.interfaces.cloudify_agent.validate_amqp',
                           {
                               'validate_agent_timeout': 20
                           },
                           'cloudify_agent.operations.validate_agent_amqp')
    if es_node['_type'] == 'blueprint':
        source = es_node['_source']
        if 'description' not in source:
            source['description'] = ''
        if 'main_file_name' not in source:
            source['main_file_name'] = ''
