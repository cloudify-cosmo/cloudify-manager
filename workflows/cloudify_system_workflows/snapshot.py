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
import platform
import tempfile
import shutil
import zipfile
import os
import pickle
import subprocess
from datetime import datetime

import utils
import elasticsearch
import elasticsearch.helpers
from wagon import wagon

from cloudify.workflows import ctx
from cloudify.constants import COMPUTE_NODE_TYPE
from cloudify.context import BootstrapContext
from cloudify.decorators import workflow
from cloudify.exceptions import NonRecoverableError
from cloudify.manager import get_rest_client
from cloudify_system_workflows.deployment_environment import \
    generate_create_dep_tasks_graph
from cloudify_system_workflows import plugins
from cloudify.utils import ManagerVersion

from utils import DictToAttributes
from postgres import Postgres

_METADATA_FILE = 'metadata.json'

# metadata fields
_M_HAS_CLOUDIFY_EVENTS = 'has_cloudify_events'
_M_VERSION = 'snapshot_version'

_AGENTS_FILE = 'agents.json'
_ELASTICSEARCH = 'es_data'
_POSTGRES_DUMP_FILENAME = 'pg_data'
_CRED_DIR = 'snapshot-credentials'
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
_CLOUDIFY_DATA_TABLES = ['blueprints',
                         'deployment_modifications',
                         'deployment_update_steps',
                         'deployment_updates',
                         'deployments',
                         'node_instances',
                         'nodes',
                         'plugins']


@workflow(system_wide=True)
def create(snapshot_id, config, **kwargs):
    ctx.logger.info('Creating snapshot..')
    update_status = get_rest_client().snapshots.update_status
    config = DictToAttributes(config)
    try:
        _create_snapshot(snapshot_id, config, **kwargs)
        update_status(snapshot_id, config.created_status)
    except BaseException, e:
        update_status(snapshot_id, config.failed_status, str(e))
        raise


@workflow(system_wide=True)
def restore(snapshot_id, recreate_deployments_envs, config, force, timeout,
            **kwargs):
    ctx.logger.info('Restoring snapshot {0}'.format(snapshot_id))
    ctx.logger.debug('Restoring snapshot config: {0}'.format(config))
    config = DictToAttributes(config)

    _assert_clean_postgres(log_warning=force)

    tempdir = tempfile.mkdtemp('-snapshot-data')
    try:
        file_server_root = config.file_server_root
        snapshots_dir = os.path.join(
            file_server_root,
            config.file_server_snapshots_folder
        )
        snapshot_path = os.path.join(snapshots_dir,
                                     snapshot_id,
                                     '{0}.zip'.format(snapshot_id))
        with zipfile.ZipFile(snapshot_path, 'r') as zipf:
            zipf.extractall(tempdir)
        with open(os.path.join(tempdir, _METADATA_FILE), 'r') as f:
            metadata = json.load(f)
        client = get_rest_client()
        manager_version = _get_manager_version(client)
        from_version = ManagerVersion(metadata[_M_VERSION])
        ctx.logger.info('Manager version = {0}, snapshot version = {1}'.format(
            str(manager_version), str(from_version)))
        if from_version.greater_than(manager_version):
            raise NonRecoverableError(
                'Cannot restore a newer manager\'s snapshot on this manager '
                '[{0} > {1}]'.format(str(from_version), str(manager_version)))
        existing_deployments_ids = [d.id for d in client.deployments.list()]
        ctx.logger.info('Starting restoring snapshot of manager {0}'
                        .format(from_version))

        version_at_least_4 = _version_at_least(from_version, '4.0.0')
        plugins_to_install = _restore_snapshot(config,
                                               tempdir,
                                               metadata,
                                               timeout,
                                               version_at_least_4)
        if plugins_to_install:
            _install_plugins(plugins_to_install)
        if recreate_deployments_envs:
            _recreate_deployments_environments(existing_deployments_ids)
        ctx.logger.info('Successfully restored snapshot of manager {0}'
                        .format(from_version))
    finally:
        ctx.logger.debug('Removing temp dir: {0}'.format(tempdir))
        shutil.rmtree(tempdir)


def _version_at_least(version_a, version_b):
    return version_a.equals(ManagerVersion(version_b)) \
           or version_a.greater_than(ManagerVersion(version_b))


def _create_es_client(config):
    return elasticsearch.Elasticsearch(hosts=[{'host': config.db_address,
                                               'port': int(config.db_port)}])


def _except_types(s, *args):
    return (e for e in s if e['_type'] not in args)


def _get_manager_version(client=None):
    if client is None:
        client = get_rest_client()

    return ManagerVersion(client.manager.get_version()['version'])


def _create_snapshot(snapshot_id,
                     config,
                     include_metrics,
                     include_credentials,
                     **kw):
    tempdir = tempfile.mkdtemp('-snapshot-data')
    ctx.logger.debug('Snapshot archive temp dir: {0}'.format(tempdir))

    snapshots_dir = os.path.join(
        config.file_server_root,
        config.file_server_snapshots_folder
    )

    try:
        if not os.path.exists(snapshots_dir):
            os.makedirs(snapshots_dir)

        metadata = {}

        # files/dirs copy
        utils.copy_data(tempdir, config)

        # elasticsearch
        es = _create_es_client(config)
        has_cloudify_events = es.indices.exists(index=_EVENTS_INDEX_NAME)
        _dump_elasticsearch(tempdir, es, has_cloudify_events)

        metadata[_M_HAS_CLOUDIFY_EVENTS] = has_cloudify_events

        # postgres
        _dump_postgres(tempdir, config, metadata)

        # influxdb
        if include_metrics:
            _dump_influxdb(tempdir)

        # credentials
        if include_credentials:
            _dump_credentials(tempdir)

        # version
        metadata[_M_VERSION] = str(_get_manager_version())

        # metadata
        with open(os.path.join(tempdir, _METADATA_FILE), 'w') as f:
            json.dump(metadata, f)

        # agents
        _dump_agents(tempdir)

        # zip
        snapshot_dir = os.path.join(snapshots_dir, snapshot_id)
        ctx.logger.info('Creating snapshot archive: {0}'.format(snapshot_dir))
        os.makedirs(snapshot_dir)

        shutil.make_archive(
            os.path.join(snapshot_dir, snapshot_id),
            'zip',
            tempdir
        )
        # end
    finally:
        ctx.logger.debug('Snapshot - deleting temp dir: {0}'.format(tempdir))
        shutil.rmtree(tempdir)


def _dump_postgres(tempdir, config, metadata):
    ctx.logger.info('Dumping Postgres data')

    postgres = Postgres(config)
    destination_path = os.path.join(tempdir,
                                    _POSTGRES_DUMP_FILENAME)
    exclude_tables = ['snapshots', 'provider_context']
    try:
        postgres.dump(destination_path, exclude_tables)
    except Exception as ex:
        raise NonRecoverableError('Error during dumping Postgres data, '
                                  'exception: {0}'.format(ex))

    delete_current_execution = "DELETE FROM executions WHERE id = '{0}';"\
        .format(ctx.execution_id)
    postgres.append_dump(destination_path, delete_current_execution)


def _dump_elasticsearch(tempdir, es, has_cloudify_events):
    ctx.logger.info('Dumping elasticsearch data')

    event_scan = elasticsearch.helpers.scan(
        es,
        index=_EVENTS_INDEX_NAME if has_cloudify_events else 'logstash-*'
    )

    with open(os.path.join(tempdir, _ELASTICSEARCH), 'w') as f:
        for item in event_scan:
            f.write(json.dumps(item) + os.linesep)


def _dump_influxdb(tempdir):
    ctx.logger.info('Dumping InfluxDB data')
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
    ctx.logger.info('Dumping credentials data')
    archive_cred_path = os.path.join(tempdir, _CRED_DIR)
    ctx.logger.debug('Dumping credentials data, archive_cred_path: {0}'.format(
        archive_cred_path))
    os.makedirs(archive_cred_path)

    hosts = [(deployment_id, node)
             for deployment_id, wctx in ctx.deployments_contexts.iteritems()
             for node in wctx.nodes
             if _is_compute(node)]

    for deployment_id, n in hosts:
        props = n.properties
        if 'cloudify_agent' in props and 'key' in props['cloudify_agent']:
            node_id = deployment_id + '_' + n.id
            agent_key_path = props['cloudify_agent']['key']
            os.makedirs(os.path.join(archive_cred_path, node_id))
            source = os.path.expanduser(agent_key_path)
            destination = os.path.join(archive_cred_path, node_id,
                                       _CRED_KEY_NAME)
            ctx.logger.debug('Dumping credentials data, copy from: {0} to {1}'
                             .format(source, destination))
            shutil.copy(source, destination)


def _dump_agents(tempdir):
    ctx.logger.info('Preparing agents data')
    client = get_rest_client()
    broker_config = BootstrapContext(ctx.bootstrap_context).broker_config()
    defaults = {
        'version': str(_get_manager_version(client)),
        'broker_config': broker_config
    }
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


def _assert_clean_postgres(log_warning=False):
    """
    Check if Postgres is clean and raise error (or just
    log warning) if it isn't.

    :param log_warning: instead raising error just log warning
    """

    client = get_rest_client()

    # No blueprints implies that there are no deployments and executions
    # corresponding to deployments.
    if client.blueprints.list().items:
        if log_warning:
            ctx.logger.warning(
                "Forcing snapshot restoration on a dirty manager.")
        else:
            raise NonRecoverableError(
                "Snapshot restoration on a dirty manager is not permitted.")


def _restore_postgres(tempdir, config):
    ctx.logger.info('Restoring Postgres data')
    postgres = Postgres(config)
    client = get_rest_client()
    existing_plugins = client.plugins.list().items
    existing_plugins_archive_names = set(p.archive_name for p in
                                         existing_plugins)
    delete_data_tables = ["DELETE FROM {0};".format(table)
                          for table in _CLOUDIFY_DATA_TABLES]
    delete_old_executions = ["DELETE FROM executions "
                             "WHERE id != '{0}';".format(ctx.execution_id)]
    queries = delete_data_tables + delete_old_executions
    dump_file = os.path.join(tempdir, _POSTGRES_DUMP_FILENAME)
    dump_file = postgres.prepend_dump(dump_file, queries)
    postgres.restore(dump_file)
    ctx.logger.debug('Postgres restored')
    all_plugins = client.plugins.list().items
    plugins_to_install = filter(
        lambda x: x.archive_name not in existing_plugins_archive_names,
        all_plugins
    )
    return plugins_to_install


def _restore_elasticsearch(tempdir, es, metadata, bulk_read_timeout):

    has_cloudify_events_index = es.indices.exists(index=_EVENTS_INDEX_NAME)
    snap_has_cloudify_events_index = metadata[_M_HAS_CLOUDIFY_EVENTS]

    # cloudify_events -> cloudify_events, logstash-* -> logstash-*
    def get_data_itr():
        for line in open(os.path.join(tempdir, _ELASTICSEARCH), 'r'):
            elem = json.loads(line)
            yield elem

    # logstash-* -> cloudify_events
    def logstash_to_cloudify_events():
        for elem in get_data_itr():
            if elem['_index'].startswith('logstash-'):
                elem['_index'] = _EVENTS_INDEX_NAME
            yield elem

    def cloudify_events_to_logstash():
        d = datetime.now()
        index = 'logstash-{0}'.format(d.strftime('%Y.%m.%d'))
        for elem in get_data_itr():
            if elem['_index'] == _EVENTS_INDEX_NAME:
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

    ctx.logger.info('Restoring ElasticSearch data '
                    '[timeout={0} sec]'.format(bulk_read_timeout))

    try:
        first = next(data_iter)
    except StopIteration:
        # no elements to restore
        return

    def not_empty_data_iter():
        yield first
        for e in data_iter:
            yield e

    elasticsearch.helpers.bulk(es,
                               not_empty_data_iter(),
                               request_timeout=bulk_read_timeout)
    es.indices.flush()


def _restore_influxdb_3_3(tempdir):
    ctx.logger.info('Restoring InfluxDB metrics')
    influxdb_f = os.path.join(tempdir, _INFLUXDB)
    if os.path.exists(influxdb_f):
        rcode = subprocess.call(_INFLUXDB_RESTORE_CMD.format(influxdb_f),
                                shell=True)
        if rcode != 0:
            raise NonRecoverableError('Error during restoring InfluxDB data, '
                                      'error code: {0}'.format(rcode))


def _restore_agent_key_from_dump(dump_cred_dir,
                                 restored_cred_dir,
                                 deployment_node_id):
    os.makedirs(os.path.join(restored_cred_dir, deployment_node_id))
    agent_key_path = os.path.join(restored_cred_dir,
                                  deployment_node_id,
                                  _CRED_KEY_NAME)
    agent_key_path_in_dump = os.path.join(dump_cred_dir,
                                          deployment_node_id,
                                          _CRED_KEY_NAME)
    shutil.copy(agent_key_path_in_dump, agent_key_path)
    return agent_key_path


def _create_restored_cred_dir():
    restored_cred_dir = os.path.join('/opt/manager', _CRED_DIR)
    if os.path.exists(restored_cred_dir):
        shutil.rmtree(restored_cred_dir)
    os.makedirs(restored_cred_dir)
    return restored_cred_dir


def _restore_credentials(tempdir, config):
    ctx.logger.info('Restoring credentials')
    dump_cred_dir = os.path.join(tempdir, _CRED_DIR)
    if not os.path.isdir(dump_cred_dir):
        ctx.logger.info('Missing credentials dir: {0}'.format(dump_cred_dir))
        return
    restored_cred_dir = _create_restored_cred_dir()
    for dep_node_id in os.listdir(dump_cred_dir):
        restored_agent_key_path = \
            _restore_agent_key_from_dump(dump_cred_dir,
                                         restored_cred_dir,
                                         dep_node_id)
        deployment_id, node_id = dep_node_id.split('_')
        agent_key_path_in_db = _agent_key_path_in_db(config,
                                                     node_id,
                                                     deployment_id)
        agent_key_path_in_db = os.path.expanduser(agent_key_path_in_db)
        if os.path.isfile(agent_key_path_in_db):
            with open(agent_key_path_in_db) as key_file:
                content_1 = key_file.read()
            with open(restored_agent_key_path) as key_file:
                content_2 = key_file.read()
            if content_1 != content_2:
                raise NonRecoverableError('Agent key path already taken: {0}'
                                          .format(agent_key_path_in_db))
            ctx.logger.debug('Agent key path already exist: {0}'
                             .format(agent_key_path_in_db))
        else:
            utils.copy(restored_agent_key_path, agent_key_path_in_db)


def _agent_key_path_in_db(config, node_id, deployment_id):
    postgres = Postgres(config)
    get_node_data = "SELECT properties FROM nodes " \
                    "WHERE id = '{0}' " \
                    "AND deployment_id = '{1}';" \
                    "".format(node_id, deployment_id)
    result = postgres.run_query(get_node_data)
    pickled_buffer = result['all'][0][0]
    properties = pickle.loads(pickled_buffer)
    key_path = properties['cloudify_agent']['key']
    ctx.logger.debug('Agent key path in db: {0}'.format(key_path))
    return key_path


def _restore_snapshot(config,
                      tempdir,
                      metadata,
                      elasticsearch_read_timeout,
                      version_at_least_4):
    # files/dirs copy
    utils.copy_data(tempdir, config, to_archive=False)

    # elasticsearch (events)
    es = _create_es_client(config)

    _restore_elasticsearch(tempdir, es, metadata,
                           elasticsearch_read_timeout)

    plugins = []

    # postgres
    if version_at_least_4:
        plugins = _restore_postgres(tempdir, config)

    # influxdb
    _restore_influxdb_3_3(tempdir)

    # credentials
    _restore_credentials(tempdir, config)

    es.indices.flush()

    # agents
    _restore_agents_data(tempdir)

    return plugins


def _restore_agents_data(tempdir):
    ctx.logger.info('Updating cloudify agent data')
    client = get_rest_client()
    with open(os.path.join(tempdir, _AGENTS_FILE)) as agents_file:
        agents = json.load(agents_file)
    _insert_agents_data(client, agents)


def _insert_agents_data(client, agents):
    for deployment_id, nodes in agents.iteritems():
        try:
            _create_agent(client, nodes)
        except:
            ctx.logger.warning('Failed restoring agents for '
                               'deployment {0}'.format(deployment_id),
                               exc_info=True)


def _create_agent(client, nodes):
    for node_instances in nodes.itervalues():
        for node_instance_id, agent in node_instances.iteritems():
            # We need to retrieve broker_config:
            # 3.3.1 and later
            if 'broker_config' in agent:
                broker_config = agent['broker_config']
            # 3.3 and earlier
            else:
                broker_config = {}
                for k in ['broker_user', 'broker_pass', 'broker_ip',
                          'broker_ssl_enabled', 'broker_ssl_cert']:
                    broker_config[k] = agent.pop(k)
                if broker_config['broker_ssl_enabled']:
                    broker_config['broker_port'] = '5671'
                else:
                    broker_config['broker_port'] = '5672'
            node_instance = client.node_instances.get(node_instance_id)
            runtime_properties = node_instance.runtime_properties
            old_agent = runtime_properties.get('cloudify_agent', {})
            if not broker_config.get('broker_ip'):
                broker_config['broker_ip'] = \
                    old_agent.get('manager_ip', '')
            agent['broker_config'] = broker_config
            old_agent.update(agent)
            runtime_properties['cloudify_agent'] = old_agent
            # Results of agent validation on old manager.
            # Might be incorrect for new manager.
            runtime_properties.pop('agent_status', None)
            client.node_instances.update(
                node_instance_id=node_instance_id,
                runtime_properties=runtime_properties,
                version=node_instance.version
            )


def _install_plugins(new_plugins):
    plugins_to_install = [p for p in new_plugins if
                          _plugin_installable_on_current_platform(p)]
    for plugin in plugins_to_install:
        plugins.install(ctx=ctx, plugin={
            'name': plugin['package_name'],
            'package_name': plugin['package_name'],
            'package_version': plugin['package_version']
        })


def _recreate_deployments_environments(deployments_to_skip):
    rest_client = get_rest_client()
    for deployment_id, dep_ctx in ctx.deployments_contexts.iteritems():
        if deployment_id in deployments_to_skip:
            continue
        with dep_ctx:
            dep = rest_client.deployments.get(deployment_id)
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
            ctx.logger.info('Successfully created deployment environment '
                            'for deployment {0}'.format(deployment_id))


def _plugin_installable_on_current_platform(plugin):
    dist, _, release = platform.linux_distribution(
        full_distribution_name=False)
    dist, release = dist.lower(), release.lower()
    return (plugin['supported_platform'] == 'any' or all([
        plugin['supported_platform'] == wagon.utils.get_platform(),
        plugin['distribution'] == dist,
        plugin['distribution_release'] == release
    ]))


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
