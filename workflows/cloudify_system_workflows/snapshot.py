########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.


import json
import tempfile
import shutil
import zipfile
import itertools
import os
import subprocess

import elasticsearch
import elasticsearch.helpers

from datetime import datetime

from cloudify import utils
from cloudify.workflows import ctx
from cloudify.constants import COMPUTE_NODE_TYPE
from cloudify.context import BootstrapContext
from cloudify.decorators import workflow
from cloudify.exceptions import NonRecoverableError
from cloudify.manager import get_rest_client
from cloudify_system_workflows.deployment_environment import \
    generate_create_dep_tasks_graph


_METADATA_FILE = 'metadata.json'

# metadata fields
_M_HAS_CLOUDIFY_EVENTS = 'has_cloudify_events'
_M_VERSION = 'snapshot_version'

_AGENTS_FILE = 'agents.json'
_ELASTICSEARCH = 'es_data'
_CRED_DIR = 'snapshot-credentials'
_RESTORED_CRED_DIR = os.path.join('/opt/manager', _CRED_DIR)
_CRED_KEY_NAME = 'agent_key'
_INFLUXDB = 'influxdb_data'
_INFLUXDB_DUMP_CMD = ('curl -s -G "http://localhost:8086/db/cloudify/series'
                      '?u=root&p=root&chunked=true" --data-urlencode'
                      ' "q=select * from /.*/" > {0}')
_INFLUXDB_RESTORE_CMD = ('cat {0} | while read -r line; do curl -X POST '
                         '-d "[${{line}}]" "http://localhost:8086/db/cloudify/'
                         'series?u=root&p=root" ;done')
_STORAGE_INDEX_NAME = 'cloudify_storage'
_EVENTS_INDEX_NAME = 'cloudify_events'


class _DictToAttributes(object):
    def __init__(self, dic):
        self._dict = dic

    def __getattr__(self, name):
        return self._dict[name]


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
        raise NonRecoverableError('Error during converting InfluxDB dump '
                                  'data to data appropriate for snapshot.')


def _copy_data(archive_root, config, to_archive=True):
    """
    Copy files/dirs between snapshot/manager and manager/snapshot.

    :param archive_root: Path to the snapshot archive root.
    :param config: Config of manager.
    :param to_archive: If True then copying is from manager to snapshot,
        otherwise from snapshot to manager.
    """

    # Files/dirs with constant relative/absolute paths,
    # where first path is path in manager, second is path in snapshot.
    # If paths are relative then should be relative to file server (path
    # in manager) and snapshot archive (path in snapshot). If paths are
    # absolute then should point to proper data in manager/snapshot archive
    data_to_copy = [
        (config.file_server_blueprints_folder, 'blueprints'),
        (config.file_server_uploaded_blueprints_folder, 'uploaded-blueprints'),
        (config.file_server_uploaded_plugins_folder, 'plugins')
    ]

    for (p1, p2) in data_to_copy:
        # first expand relative paths
        if p1[0] != '/':
            p1 = os.path.join(config.file_server_root, p1)
        if p2[0] != '/':
            p2 = os.path.join(archive_root, p2)

        # make p1 to always point to source and p2 to target of copying
        if not to_archive:
            p1, p2 = p2, p1

        # source doesn't need to exist, then ignore
        if not os.path.exists(p1):
            continue

        # copy data (and override if target exists)
        if os.path.isfile(p1):
            shutil.copy(p1, p2)
        else:
            if os.path.exists(p2):
                shutil.rmtree(p2, ignore_errors=True)
            shutil.copytree(p1, p2)


def _create_es_client(config):
    return elasticsearch.Elasticsearch(hosts=[{'host': config.db_address,
                                               'port': int(config.db_port)}])


def _except_types(s, *args):
    return (e for e in s if e['_type'] not in args)


def _clean_up_db_before_restore(es_client, wf_exec_id):
    s = elasticsearch.helpers.scan(es_client)
    for doc in _except_types(s, 'provider_context', 'snapshot'):
        if doc['_id'] != wf_exec_id:
            doc['_op_type'] = 'delete'
            yield doc


def _get_manager_version(client=None):
    if client is None:
        client = get_rest_client()

    version_json = client.manager.get_version()
    return '.'.join(version_json['version'].split('.')[0:2])


def _create(snapshot_id, config, include_metrics, include_credentials, **kw):
    tempdir = tempfile.mkdtemp('-snapshot-data')

    snapshots_dir = os.path.join(
        config.file_server_root,
        config.file_server_snapshots_folder
    )

    try:
        if not os.path.exists(snapshots_dir):
            os.makedirs(snapshots_dir)

        metadata = {}

        # files/dirs copy
        _copy_data(tempdir, config)

        # elasticsearch
        es = _create_es_client(config)
        has_cloudify_events = es.indices.exists(index=_EVENTS_INDEX_NAME)
        _dump_elasticsearch(tempdir, es, has_cloudify_events)

        metadata[_M_HAS_CLOUDIFY_EVENTS] = has_cloudify_events

        # influxdb
        if include_metrics:
            _dump_influxdb(tempdir)

        # credentials
        if include_credentials:
            _dump_credentials(tempdir)

        # version
        metadata[_M_VERSION] = _get_manager_version()

        # metadata
        with open(os.path.join(tempdir, _METADATA_FILE), 'w') as f:
            json.dump(metadata, f)

        # agents
        _dump_agents(tempdir)

        # zip
        ctx.send_event('Creating snapshot archive')
        snapshot_dir = os.path.join(snapshots_dir, snapshot_id)
        os.makedirs(snapshot_dir)

        shutil.make_archive(
            os.path.join(snapshot_dir, snapshot_id),
            'zip',
            tempdir
        )
        # end
    finally:
        shutil.rmtree(tempdir)


@workflow(system_wide=True)
def create(snapshot_id, config, **kwargs):
    update_status = get_rest_client().snapshots.update_status
    config = _DictToAttributes(config)
    try:
        _create(snapshot_id, config, **kwargs)
        update_status(snapshot_id, config.created_status)
    except BaseException, e:
        update_status(snapshot_id, config.failed_status, str(e))
        raise


def _dump_elasticsearch(tempdir, es, has_cloudify_events):
    ctx.send_event('Dumping elasticsearch data')
    storage_scan = elasticsearch.helpers.scan(es, index=_STORAGE_INDEX_NAME)
    storage_scan = _except_types(storage_scan,
                                 'provider_context',
                                 'snapshot')
    storage_scan = (e for e in storage_scan if e['_id'] != ctx.execution_id)

    event_scan = elasticsearch.helpers.scan(
        es,
        index=_EVENTS_INDEX_NAME if has_cloudify_events else 'logstash-*'
    )

    with open(os.path.join(tempdir, _ELASTICSEARCH), 'w') as f:
        for item in itertools.chain(storage_scan, event_scan):
            f.write(json.dumps(item) + os.linesep)


def _dump_influxdb(tempdir):
    ctx.send_event('Dumping InfluxDB data')
    influxdb_file = os.path.join(tempdir, _INFLUXDB)
    influxdb_temp_file = influxdb_file + '.temp'
    rcode = subprocess.call(_INFLUXDB_DUMP_CMD.format(influxdb_temp_file),
                            shell=True)
    if rcode != 0:
        raise NonRecoverableError('Error during dumping InfluxDB data, '
                                  'error code: {0}'.format(rcode))
    with open(influxdb_temp_file, 'r') as f, open(influxdb_file, 'w') as g:
        for obj in _get_json_objects(f):
            g.write(obj + os.linesep)

    os.remove(influxdb_temp_file)


def _is_compute(node):
    return COMPUTE_NODE_TYPE in node.type_hierarchy


def _dump_credentials(tempdir):
    ctx.send_event('Dumping credentials data')
    archive_cred_path = os.path.join(tempdir, _CRED_DIR)
    os.makedirs(archive_cred_path)

    hosts = [(dep_id, node)
             for dep_id, wctx in ctx.deployments_contexts.iteritems()
             for node in wctx.nodes
             if _is_compute(node)]

    for dep_id, n in hosts:
        props = n.properties
        if 'cloudify_agent' in props and 'key' in props['cloudify_agent']:
            node_id = dep_id + '_' + n.id
            agent_key_path = props['cloudify_agent']['key']
            os.makedirs(os.path.join(archive_cred_path, node_id))
            shutil.copy(os.path.expanduser(agent_key_path),
                        os.path.join(archive_cred_path, node_id,
                                     _CRED_KEY_NAME))


def _get_broker_configuration(client):
    bootstrap_context_dict = client.manager.get_context()
    bootstrap_context_dict = bootstrap_context_dict['context']['cloudify']
    bootstrap_context = BootstrapContext(bootstrap_context_dict)
    bootstrap_agent = bootstrap_context.cloudify_agent

    broker_user, broker_pass = utils.internal.get_broker_credentials(
        bootstrap_agent
    )
    attributes = {}
    attributes['broker_user'] = broker_user
    attributes['broker_pass'] = broker_pass
    attributes['broker_ip'] = bootstrap_agent.broker_ip
    attributes['broker_ssl_enabled'] = bootstrap_agent.broker_ssl_enabled
    attributes['broker_ssl_cert'] = bootstrap_agent.broker_ssl_cert
    return attributes


def _dump_agents(tempdir):
    ctx.send_event('Preparing agents data')
    client = get_rest_client()
    defaults = _get_broker_configuration(client)
    defaults['version'] = _get_manager_version(client)
    result = {}
    for deployment in client.deployments.list():
        deployment_result = {}
        for node in client.nodes.list(deployment_id=deployment.id):
            if _is_compute(node):
                node_result = {}
                for node_instance in client.node_instances.list(
                        deployment_id=deployment.id,
                        node_name=node.id):
                    overrides = {}
                    current = node_instance.runtime_properties.get(
                        'cloudify_agent', {})
                    for k, v in defaults.iteritems():
                        overrides[k] = current.get(k, v)
                    node_result[node_instance.id] = overrides
                deployment_result[node.id] = node_result
        result[deployment.id] = deployment_result
    with open(os.path.join(tempdir, _AGENTS_FILE), 'w') as out:
        out.write(json.dumps(result))


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
            op_name = 'cloudify.interfaces.cloudify_agent.create_amqp'
            if op_name not in operations:
                operations[op_name] = {
                    'inputs': {
                        'install_agent_timeout': 300
                    },
                    'has_intrinsic_functions': False,
                    'plugin': 'agent',
                    'retry_interval': None,
                    'max_retries': None,
                    'executor': 'central_deployment_agent',
                    'operation': 'cloudify_agent.operations.create_agent_amqp'
                }

    if es_node['_type'] == 'blueprint':
        source = es_node['_source']
        if 'description' not in source:
            source['description'] = ''
        if 'main_file_name' not in source:
            source['main_file_name'] = ''


def _assert_clean_elasticsearch(es, log_warning=False):
    """
    Check if manager ElasticSearch is clean and raise error (or just
    log warning) if it isn't.

    :param es: ElasticSearch proxy object
    :param log_warning: instead raising error just log warning
    """

    def _raise_or_log():
        message = ('Manager is not clean, snapshot is allowed to be '
                   'restored only on a clean manager.')
        if log_warning:
            ctx.logger.warning(message)
        else:
            raise NonRecoverableError(message)

    # check storage
    storage_scan = elasticsearch.helpers.scan(es, index=_STORAGE_INDEX_NAME)
    storage_scan = _except_types(storage_scan,
                                 'provider_context',
                                 'snapshot',
                                 'execution')
    if next(storage_scan, False):
        _raise_or_log()


def _check_conflicts(es, restored_data):
    """
    Check names conflicts in restored snapshot and manager.
    If in restored snapshot there are blueprints/deployments then
    manager cannot contain any blueprints/deployments with the same names.

    :param es: ElasticSearch proxy object
    :param restored_data: iterator to snapshots Elasticsearch data that
        is supposed to be restored
    """

    old_data = elasticsearch.helpers.scan(es, index=_STORAGE_INDEX_NAME,
                                          doc_type='blueprint, deployment')
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
        raise NonRecoverableError(
            exception_message.format(blueprints_conflicts,
                                     deployments_conflicts)
        )


def _restore_elasticsearch(tempdir, es, metadata):

    has_cloudify_events_index = es.indices.exists(index=_EVENTS_INDEX_NAME)
    snap_has_cloudify_events_index = metadata[_M_HAS_CLOUDIFY_EVENTS]

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
                elem['_index'] = _EVENTS_INDEX_NAME
            yield elem

    # cloudify_events -> logstash-*
    def date_to_index_name(date):
        d = datetime.strptime(date, '%Y-%m-%dT%H:%M:%S.%fZ')
        return 'logstash-' + d.strftime('%Y.%m.%d')

    def get_event_date(e):
        return e['_source']['@timestamp']

    def cloudify_events_to_logstash():
        event_indices = []
        for elem in get_data_itr():
            if elem['_index'] == _EVENTS_INDEX_NAME:
                date = get_event_date(elem)
                index = date_to_index_name(date)
                if index not in event_indices and\
                        not es.indices.exists(index=index):
                    es.indices.create(index=index)
                    event_indices.append(index)
                elem['_index'] = index
            yield elem

    # choose iter
    if (has_cloudify_events_index and snap_has_cloudify_events_index) or\
            (not has_cloudify_events_index and
             not snap_has_cloudify_events_index):
        data_iter = get_data_itr()
    elif not snap_has_cloudify_events_index and has_cloudify_events_index:
        data_iter = logstash_to_cloudify_events()
    else:
        data_iter = cloudify_events_to_logstash()

    ctx.send_event('Restoring ElasticSearch data')
    elasticsearch.helpers.bulk(es, data_iter)
    es.indices.flush()


def _restore_influxdb_3_3(tempdir):
    ctx.send_event('Restoring InfluxDB metrics')
    influxdb_f = os.path.join(tempdir, _INFLUXDB)
    if os.path.exists(influxdb_f):
        rcode = subprocess.call(_INFLUXDB_RESTORE_CMD.format(influxdb_f),
                                shell=True)
        if rcode != 0:
            raise NonRecoverableError('Error during restoring InfluxDB data, '
                                      'error code: {0}'.format(rcode))


def _restore_credentials_3_3(tempdir, es):
    ctx.send_event('Restoring credentials')
    archive_cred_path = os.path.join(tempdir, _CRED_DIR)

    # in case when this is not the first restore action
    if os.path.exists(_RESTORED_CRED_DIR):
        shutil.rmtree(_RESTORED_CRED_DIR)

    os.makedirs(_RESTORED_CRED_DIR)

    update_actions = []
    if os.path.exists(archive_cred_path):
        for node_id in os.listdir(archive_cred_path):
            os.makedirs(os.path.join(_RESTORED_CRED_DIR, node_id))
            agent_key_path = os.path.join(_RESTORED_CRED_DIR, node_id,
                                          _CRED_KEY_NAME)
            shutil.copy(os.path.join(archive_cred_path, node_id,
                        _CRED_KEY_NAME), agent_key_path)

            update_action = {
                '_op_type': 'update',
                '_index': _STORAGE_INDEX_NAME,
                '_type': 'node',
                '_id': node_id,
                'doc': {
                    'properties': {
                        'cloudify_agent': {
                            'key': agent_key_path
                        }
                    }
                }
            }

            update_actions.append(update_action)

    elasticsearch.helpers.bulk(es, update_actions)


def insert_agents_data(client, agents):
    for nodes in agents.itervalues():
        for node_instances in nodes.itervalues():
            for node_instance_id, agent in node_instances.iteritems():
                node_instance = client.node_instances.get(node_instance_id)
                runtime_properties = node_instance.runtime_properties
                old_agent = runtime_properties.get('cloudify_agent', {})
                old_agent.update(agent)
                runtime_properties['cloudify_agent'] = old_agent
                client.node_instances.update(
                    node_instance_id=node_instance_id,
                    runtime_properties=runtime_properties)


def _restore_agents_data(tempdir):
    ctx.send_event('Updating cloudify agent data')
    client = get_rest_client()
    with open(os.path.join(tempdir, _AGENTS_FILE)) as agents_file:
        agents = json.load(agents_file)
    insert_agents_data(client, agents)


def _restore_snapshot(config, tempdir, metadata):
    # files/dirs copy
    _copy_data(tempdir, config, to_archive=False)

    # elasticsearch
    es = _create_es_client(config)

    _restore_elasticsearch(tempdir, es, metadata)

    # influxdb
    _restore_influxdb_3_3(tempdir)

    # credentials
    _restore_credentials_3_3(tempdir, es)

    es.indices.flush()

    # agents
    _restore_agents_data(tempdir)
    # end


def _restore_snapshot_format_3_3(config, tempdir, metadata):
    _restore_snapshot(config, tempdir, metadata)


def _restore_snapshot_format_3_2(config, tempdir, metadata):
    _restore_snapshot(config, tempdir, metadata)


def recreate_deployments_environments():
    rest_client = get_rest_client()
    for dep_id, dep_ctx in ctx.deployments_contexts.iteritems():
        with dep_ctx:
            dep = rest_client.deployments.get(dep_id)
            blueprint = rest_client.blueprints.get(dep_ctx.blueprint.id)
            blueprint_plan = blueprint['plan']
            tasks_graph = generate_create_dep_tasks_graph(
                dep_ctx,
                deployment_plugins_to_install=blueprint_plan[
                    'deployment_plugins_to_install'],
                workflow_plugins_to_install=blueprint_plan[
                    'workflow_plugins_to_install'],
                policy_configuration={
                    'policy_types': dep['policy_types'],
                    'policy_triggers': dep['policy_triggers'],
                    'groups': dep['groups']
                }
            )
            tasks_graph.execute()
            ctx.send_event('Successfully created deployment environment '
                           'for deployment {0}'.format(dep_id))


@workflow(system_wide=True)
def restore(snapshot_id, recreate_deployments_envs, config, force, **kwargs):
    mappings = {
        '3.3': _restore_snapshot_format_3_3,
        '3.2': _restore_snapshot_format_3_2
    }

    config = _DictToAttributes(config)

    es = _create_es_client(config)

    _assert_clean_elasticsearch(es, log_warning=force)

    tempdir = tempfile.mkdtemp('-snapshot-data')

    try:
        file_server_root = config.file_server_root
        snapshots_dir = os.path.join(
            file_server_root,
            config.file_server_snapshots_folder
        )

        snapshot_path = os.path.join(snapshots_dir, snapshot_id, '{0}.zip'
                                     .format(snapshot_id))

        with zipfile.ZipFile(snapshot_path, 'r') as zipf:
            zipf.extractall(tempdir)

        with open(os.path.join(tempdir, _METADATA_FILE), 'r') as f:
            metadata = json.load(f)

        from_version = metadata[_M_VERSION]

        if from_version not in mappings:
            raise NonRecoverableError('Manager is not able to restore snapshot'
                                      ' of manager {0}'.format(from_version))

        ctx.send_event('Starting restoring snapshot of manager {0}'
                       .format(from_version))
        mappings[from_version](config, tempdir, metadata)

        if recreate_deployments_envs:
            recreate_deployments_environments()

        ctx.send_event('Successfully restored snapshot of manager {0}'
                       .format(from_version))
    finally:
        shutil.rmtree(tempdir)
