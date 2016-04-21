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
import os

import elasticsearch
import elasticsearch.helpers

import db_helper

from cloudify.workflows import ctx
from cloudify.constants import COMPUTE_NODE_TYPE
from cloudify.context import BootstrapContext
from cloudify.decorators import workflow
from cloudify.exceptions import NonRecoverableError
from cloudify.manager import get_rest_client
from cloudify_system_workflows.deployment_environment import \
    generate_create_dep_tasks_graph
from cloudify.utils import ManagerVersion


_METADATA_FILE = 'metadata.json'
# metadata fields
_M_VERSION = 'snapshot_version'
_M_HAS_CLOUDIFY_EVENTS = db_helper.M_HAS_CLOUDIFY_EVENTS

_AGENTS_FILE = 'agents.json'
_CRED_DIR = 'snapshot-credentials'
_RESTORED_CRED_DIR = os.path.join('/opt/manager', _CRED_DIR)
_CRED_KEY_NAME = 'agent_key'


class _DictToAttributes(object):
    def __init__(self, dic):
        self._dict = dic

    def __getattr__(self, name):
        return self._dict[name]


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
        (config.file_server_deployments_folder, 'deployments'),
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

        # copy data
        if os.path.isfile(p1):
            shutil.copy(p1, p2)
        else:
            if not os.path.exists(p2):
                os.makedirs(p2)

            for item in os.listdir(p1):
                s = os.path.join(p1, item)
                d = os.path.join(p2, item)
                # The only case when it is possible that `d` exists is when
                # restoring snapshot with plugins on the same manager this
                # snapshot was created on. It means it is the same plugin so
                # we are ok with not copying it.
                if not os.path.exists(d):
                    if os.path.isdir(s):
                        shutil.copytree(s, d)
                    else:
                        shutil.copy2(s, d)


def _create_es_client(config):
    return elasticsearch.Elasticsearch(hosts=[{'host': config.db_address,
                                               'port': int(config.db_port)}])


def _get_manager_version(client=None):
    if client is None:
        client = get_rest_client()

    return ManagerVersion(client.manager.get_version()['version'])


def _create(snapshot_id, config, include_metrics, include_credentials, **kw):
    tempdir = tempfile.mkdtemp('-snapshot-data')

    snapshots_dir = os.path.join(
        config.file_server_root,
        config.file_server_snapshots_folder
    )

    try:
        if not os.path.exists(snapshots_dir):
            os.makedirs(snapshots_dir)

        # files/dirs copy
        _copy_data(tempdir, config)

        # elasticsearch
        es = _create_es_client(config)
        ctx.send_event('Dumping elasticsearch data')
        db_helper.dump_elasticsearch(tempdir, es,
                                     execution_id=ctx.execution_id)

        # metadata
        has_cloudify_events = \
            es.indices.exists(index=db_helper.EVENTS_INDEX_NAME)
        _create_metadata_file(tempfile, has_cloudify_events)

        # influxdb
        if include_metrics:
            ctx.send_event('Dumping InfluxDB data')
            try:
                db_helper.dump_influxdb(tempdir)
            except RuntimeError as e:
                raise NonRecoverableError(e.message)

        # credentials
        if include_credentials:
            _dump_credentials(tempdir)

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


def _create_metadata_file(dump_dir_path, has_cloudify_events):
    metadata = {}
    metadata[_M_HAS_CLOUDIFY_EVENTS] = has_cloudify_events
    metadata[_M_VERSION] = str(_get_manager_version())
    with open(os.path.join(dump_dir_path, _METADATA_FILE), 'w') as f:
        json.dump(metadata, f)


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


def _dump_agents(tempdir):
    ctx.send_event('Preparing agents data')
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


def _assert_clean_elasticsearch(log_warning=False):
    """
    Check if manager ElasticSearch is clean and raise error (or just
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
                '_index': db_helper.STORAGE_INDEX_NAME,
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
                    broker_config['broker_ip'] = old_agent.get('manager_ip',
                                                               '')
                agent['broker_config'] = broker_config
                old_agent.update(agent)
                runtime_properties['cloudify_agent'] = old_agent
                # Results of agent validation on old manager.
                # Might be incorrect for new manager.
                runtime_properties.pop('agent_status', None)
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

    ctx.send_event('Restoring ElasticSearch data')
    try:
        db_helper.restore_elasticsearch(tempdir, es, metadata)
    except RuntimeError as e:
        raise NonRecoverableError(e.message)

    # influxdb
    ctx.send_event('Restoring InfluxDB metrics')
    try:
        db_helper.restore_influxdb_3_3(tempdir)
    except RuntimeError as e:
        raise NonRecoverableError(e.message)

    # credentials
    _restore_credentials_3_3(tempdir, es)

    es.indices.flush()

    # agents
    _restore_agents_data(tempdir)
    # end


def recreate_deployments_environments(deployments_to_skip):
    rest_client = get_rest_client()
    for dep_id, dep_ctx in ctx.deployments_contexts.iteritems():
        if dep_id in deployments_to_skip:
            continue
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

    ctx.logger.info('Restoring snapshot {0}'.format(snapshot_id))

    config = _DictToAttributes(config)

    _assert_clean_elasticsearch(log_warning=force)

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
        ctx.send_event('Starting restoring snapshot of manager {0}'
                       .format(from_version))

        _restore_snapshot(config, tempdir, metadata)

        if recreate_deployments_envs:
            recreate_deployments_environments(existing_deployments_ids)

        ctx.send_event('Successfully restored snapshot of manager {0}'
                       .format(from_version))
    finally:
        shutil.rmtree(tempdir)
