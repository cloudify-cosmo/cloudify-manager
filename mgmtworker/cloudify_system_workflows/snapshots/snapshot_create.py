import os
import json
import shutil
import tempfile
import zipfile

from cloudify.workflows import ctx
from cloudify.manager import get_rest_client
from cloudify.constants import FILE_SERVER_SNAPSHOTS_FOLDER

from . import constants, utils


EMPTY_B64_ZIP = 'UEsFBgAAAAAAAAAAAAAAAAAAAAAAAA=='
ENTITIES_PER_GROUPING = 500
FILTERS_INCLUDE = ['created_at', 'id', 'visibility', 'value', 'created_by',
                   'is_system_filter']
INCLUDES = {
    'tenants': ['name', 'rabbitmq_password'],
    'users': ['username', 'role', 'tenant_roles', 'first_login_at',
              'last_login_at', 'created_at'],
    'user_groups': ['name', 'ldap_dn', 'tenants', 'role'],
    'sites': ['name', 'location', 'visibility', 'created_by', 'created_at'],
    'plugins': ['id', 'title', 'visibility', 'uploaded_at', 'created_by'],
    'secrets': ['key', 'value', 'visibility', 'is_hidden_value', 'encrypted',
                'tenant_name', 'creator', 'created_at'],
    'blueprints': ['id', 'visibility', 'labels', 'created_at', 'created_by',
                   'state', 'main_file_name', 'plan', 'description', 'error',
                   'error_traceback', 'is_hidden', 'requirements'],
    'deployments': ['id', 'blueprint_id', 'inputs', 'visibility', 'labels',
                    'display_name', 'runtime_only_evaluation', 'created_by',
                    'created_at', 'workflows', 'groups', 'policy_triggers',
                    'policy_types', 'outputs', 'capabilities', 'description',
                    'scaling_groups', 'resource_tags', 'deployment_status',
                    'installation_status'],
    'nodes': ['id', 'host_id', 'plugins', 'plugins_to_install', 'properties',
              'max_number_of_instances', 'min_number_of_instances',
              'planned_number_of_instances', 'deploy_number_of_instances',
              'relationships', 'operations', 'type', 'type_hierarchy',
              'visibility', 'created_by', 'number_of_instances'],
    'node_instances': ['id', 'runtime_properties', 'state', 'relationships',
                       'system_properties', 'scaling_groups', 'host_id',
                       'index', 'visibility', 'node_id', 'created_by',
                       'has_configuration_drift',
                       'is_status_check_ok', 'created_by'],
    'agents': ['id', 'node_instance_id', 'state', 'created_at', 'created_by',
               'rabbitmq_password', 'rabbitmq_username', 'rabbitmq_exchange',
               'version', 'system', 'install_method', 'ip', 'visibility'],
    'deployment_groups': ['id', 'visibility', 'description', 'labels',
                          'default_blueprint_id', 'default_inputs',
                          'deployment_ids', 'created_by', 'created_at',
                          'creation_counter'],
    'executions': ['deployment_id', 'workflow_id', 'parameters', 'is_dry_run',
                   'allow_custom_parameters', 'status', 'created_by',
                   'created_at', 'id', 'started_at', 'ended_at', 'error'],
    'events': ['timestamp', 'reported_timestamp', 'blueprint_id',
               'deployment_id', 'deployment_display_name', 'workflow_id',
               'message', 'error_causes', 'event_type', 'operation',
               'source_id', 'target_id', 'node_instance_id',
               'type', 'logger', 'level', 'manager_name', 'agent_name'],
    'execution_groups': ['id', 'created_at', 'workflow_id', 'execution_ids',
                         'concurrency', 'deployment_group_id', 'created_by'],
    'deployment_updates': ['id', 'deployment_id', 'new_blueprint_id', 'state',
                           'new_inputs', 'created_at', 'created_by',
                           'execution_id', 'old_blueprint_id',
                           'runtime_only_evaluation', 'deployment_plan',
                           'deployment_update_node_instances',
                           'visibility', 'steps',
                           'central_plugins_to_uninstall',
                           'central_plugins_to_install', 'old_inputs',
                           'deployment_update_nodes', 'modified_entity_ids'],
    'execution_schedules': ['id', 'rule', 'deployment_id', 'workflow_id',
                            'created_at', 'since', 'until', 'stop_on_fail',
                            'parameters', 'execution_arguments', 'slip',
                            'enabled', 'created_by'],
    'plugins_update': ['id', 'state', 'forced', 'all_tenants',
                       'blueprint_id', 'execution_id', 'created_by',
                       'created_at', 'deployments_to_update',
                       'deployments_per_tenant', 'temp_blueprint_id'],
    'blueprints_filters': FILTERS_INCLUDE,
    'deployments_filters': FILTERS_INCLUDE,
    'tasks_graphs': ['created_at', 'execution_id', 'name', 'id'],
    'operations': ['agent_name', 'created_at', 'dependencies', 'id',
                   'manager_name', 'name', 'parameters', 'state', 'type',
                   'tasks_graph_id'],
}
GET_DATA = [
    'users', 'user_groups',
    'sites', 'plugins', 'secrets', 'blueprints', 'deployments', 'agents',
    'deployment_groups', 'executions', 'events', 'execution_groups',
]
EXTRA_DUMP_KWARGS = {
    'users': {'_include_hash': True},
    'executions': {'include_system_workflows': True},
    'secrets': {'_include_metadata': True},
}


class SnapshotCreate(object):
    def __init__(self,
                 snapshot_id,
                 config,
                 include_credentials=None,
                 include_logs=True,
                 include_events=True,
                 all_tenants=True):
        # include_credentials was for dealing with fs level keys/etc and
        # should've been deprecated long ago as the use-case for it started
        # its slide into history when we converted them to secrets
        # (and that's why it's just thrown away)
        self._snapshot_id = snapshot_id
        self._config = utils.DictToAttributes(config)
        self._include_logs = include_logs
        self._include_events = include_events
        self._all_tenants = all_tenants

        self._tempdir = None
        self._client = None
        self._tenant_clients = {}
        self._zip_handle = None
        self._archive_dest = self._get_snapshot_archive_name()

    def create(self):
        self._client = get_rest_client()
        self._tenants = self._get_tenants()
        self._prepare_tempdir()
        try:
            with zipfile.ZipFile(
                self._archive_dest,
                'w',
                compression=zipfile.ZIP_DEFLATED,
                allowZip64=True,
            ) as zip_handle:
                self._zip_handle = zip_handle

                manager_version = utils.get_manager_version(self._client)

                self._dump_metadata(manager_version)

                self._dump_management()
                for tenant in self._tenants:
                    self._dump_tenant(tenant)

                self._update_snapshot_status(self._config.created_status)
                ctx.logger.info('Snapshot created successfully')
        except BaseException as e:
            self._update_snapshot_status(self._config.failed_status, str(e))
            ctx.logger.error('Snapshot creation failed: {0}'.format(str(e)))
            if os.path.exists(self._archive_dest):
                # Clean up snapshot archive
                os.unlink(self._archive_dest)
            raise
        finally:
            ctx.logger.debug('Removing temp dir: {0}'.format(self._tempdir))
            shutil.rmtree(self._tempdir)

    def _prepare_tempdir(self):
        self._tempdir = tempfile.mkdtemp('-snapshot-data')
        nested = ['mgmt', 'tenants']
        for nested_dir in nested:
            os.makedirs(os.path.join(self._tempdir, nested_dir))

    def _dump_management(self):
        """Dump top level objects that don't reside in a tenant."""
        self._dump_objects('user_groups')
        self._dump_objects('tenants')
        self._dump_objects('users')
        self._dump_objects('permissions')

    def _dump_tenant(self, tenant_name):
        """Dump objects from a tenant."""
        self._dump_objects('sites', tenant_name)
        self._dump_objects('plugins', tenant_name)
        self._dump_objects('secrets', tenant_name)
        self._dump_objects('blueprints', tenant_name)
        self._dump_objects('deployments', tenant_name)
        self._dump_objects('deployment_groups', tenant_name)
        self._dump_objects('executions', tenant_name)
        self._dump_objects('execution_groups', tenant_name)
        self._dump_objects('deployment_updates', tenant_name)
        self._dump_objects('plugins_update', tenant_name)
        self._dump_objects('deployments_filters', tenant_name)
        self._dump_objects('blueprints_filters', tenant_name)
        self._dump_objects('execution_schedules', tenant_name)

    def _get_tenants(self):
        return {
            tenant['name']: tenant
            for tenant in get_all(
                self._client.tenants.list, {'_include': INCLUDES['tenants']})
        }

    def _dump_objects(self, dump_type, tenant_name=None):
        get_kwargs = {}
        suffix = '.json'
        if tenant_name:
            if tenant_name not in self._tenant_clients:
                self._tenant_clients[tenant_name] = get_rest_client(
                    tenant=tenant_name)
            client = self._tenant_clients[tenant_name]
            dump_dir = os.path.join(self._tempdir, 'tenants', tenant_name)
            os.makedirs(dump_dir, exist_ok=True)
            destination_base = os.path.join(dump_dir, dump_type)
            get_kwargs = {'tenant_name': tenant_name}
        else:
            client = self._client
            destination_base = os.path.join(
                self._tempdir, 'mgmt', dump_type
            )
        if dump_type in GET_DATA:
            get_kwargs['_get_data'] = True

        os.makedirs(destination_base, exist_ok=True)

        include = INCLUDES.get(dump_type)
        if include:
            get_kwargs['_include'] = include

        extra_kwargs = EXTRA_DUMP_KWARGS.get(dump_type)
        if extra_kwargs:
            get_kwargs.update(extra_kwargs)

        if dump_type == 'tenants':
            data = list(self._tenants.values())
        elif dump_type == 'secrets':
            data = getattr(client, dump_type).export(**get_kwargs)
        else:
            data = get_all(getattr(client, dump_type).list, get_kwargs)

        if include and 'is_system_filter' in include:
            data = [item for item in data
                    if not item['is_system_filter']]
            for item in data:
                item.pop('is_system_filter')

        remainder = len(data) % ENTITIES_PER_GROUPING
        file_count = len(data) // ENTITIES_PER_GROUPING
        if remainder:
            file_count += 1
        for i in range(file_count):
            start = i * ENTITIES_PER_GROUPING
            finish = (i+1) * ENTITIES_PER_GROUPING
            this_file = os.path.join(destination_base, str(i) + suffix)
            with open(this_file, 'w') as dump_handle:
                json.dump(data[start:finish], dump_handle)
            self._zip_handle.write(this_file,
                                   os.path.relpath(this_file, self._tempdir))
            os.unlink(this_file)

        if dump_type in ('plugins', 'blueprints', 'deployments'):
            self._dump_blobs(data, dump_type, client, tenant_name)
        elif dump_type in ('executions', 'execution_groups'):
            ctx.logger.debug('Dumped %s %s. Kwargs %s; getter %s',
                             len(data), dump_type, get_kwargs,
                             str(getattr(client, dump_type).list))
            self._dump_events(data, dump_type, client, tenant_name)

        if dump_type == 'executions':
            self._dump_tasks_graphs(data, client, tenant_name)

        if dump_type == 'deployments':
            self._dump_nodes_and_instances(data, client, tenant_name)

    def _dump_blobs(self, entities, dump_type, client, tenant_name):
        dest_dir = os.path.join(self._tempdir, 'tenants', tenant_name,
                                dump_type + '_archives')
        os.makedirs(dest_dir, exist_ok=True)
        suffix = {
            'plugins': '.wgn',
            'blueprints': '.zip',
            'deployments': '.b64zip',
        }[dump_type]
        for entity in entities:
            entity_id = entity['id']
            entity_dest = os.path.join(dest_dir, entity_id + suffix)
            if dump_type == 'deployments':
                data = getattr(client, dump_type).get(
                   deployment_id=entity_id, _include=['workdir_zip'],
                   include_workdir=True)
                b64_zip = data['workdir_zip']
                if b64_zip == EMPTY_B64_ZIP:
                    continue
                with open(entity_dest, 'w') as dump_handle:
                    dump_handle.write(b64_zip)
            else:
                getattr(client, dump_type).download(entity_id, entity_dest)
                if dump_type == 'plugins':
                    yaml_dest = os.path.join(dest_dir, entity_id + '.yaml')
                    client.plugins.download_yaml(entity_id, yaml_dest)
                    # We need the wagon and yaml as a zip when restoring
                    zip_dest = os.path.join(dest_dir, entity_id + '.zip')
                    with zipfile.ZipFile(
                        zip_dest,
                        'w',
                        compression=zipfile.ZIP_DEFLATED,
                        allowZip64=True,
                    ) as zip_file:
                        zip_file.write(yaml_dest, 'plugin.yaml')
                        zip_file.write(entity_dest,
                                       os.path.basename(entity_dest))
                    os.remove(yaml_dest)
                    os.remove(entity_dest)
                    entity_dest = zip_dest
            self._zip_handle.write(
                entity_dest, os.path.relpath(entity_dest, self._tempdir))
            os.unlink(entity_dest)

    def _dump_events(self, event_sources, event_source_type, client,
                     tenant_name):
        if not self._include_events:
            return
        dest_dir = os.path.join(self._tempdir, 'tenants', tenant_name,
                                event_source_type + '_events')
        # executions -> execution_id, execution-groups -> execution-group_id
        event_source_id_prop = event_source_type[:-1] + '_id'
        for source in event_sources:
            source_id = source['id']
            self._dump_parts(event_source_id_prop, source_id, client,
                             dest_dir, 'events')

    def _dump_tasks_graphs(self, executions, client, tenant_name):
        dest_dir = os.path.join(self._tempdir, 'tenants', tenant_name,
                                'tasks_graphs')
        for execution in executions:
            source_id = execution['id']
            self._dump_parts('execution_id', source_id, client,
                             dest_dir, 'tasks_graphs')

    def _dump_nodes_and_instances(self, deployments, client, tenant_name):
        dest_dir_base = os.path.join(self._tempdir, 'tenants', tenant_name)
        for deployment in deployments:
            dep_id = deployment['id']
            for part in ['nodes', 'node_instances', 'agents']:
                dest_dir = os.path.join(dest_dir_base, part)
                self._dump_parts('deployment_id', dep_id, client, dest_dir,
                                 part)

    def _dump_parts(self, filter_name, filter_id, client, dest_dir, part):
        os.makedirs(dest_dir, exist_ok=True)
        part_kwargs = {
            filter_name: filter_id,
            '_include': INCLUDES[part],
        }
        if part == 'events':
            part_kwargs['include_logs'] = self._include_logs
        if part in GET_DATA:
            part_kwargs['_get_data'] = True
        parts = get_all(getattr(client, part).list, part_kwargs)
        if not parts:
            return
        if part == 'tasks_graphs':
            ops_kwargs = {
                filter_name: filter_id,
                '_include': INCLUDES['operations'],
            }
            ops = get_all(client.operations.list, ops_kwargs)
            ctx.logger.debug('Execution %s has %s operations',
                             filter_id, len(ops))
            for graph in parts:
                graph_ops = [op for op in ops
                             if op['tasks_graph_id'] == graph['id']]
                ops = [op for op in ops
                       if op['tasks_graph_id'] != graph['id']]
                for op in graph_ops:
                    op.pop('tasks_graph_id')
                if graph_ops:
                    graph['operations'] = graph_ops
        elif part == 'executions':
            parts = [
                part for part in parts
                if not part['id'] == ctx.execution_id
            ]
        parts_dest = os.path.join(dest_dir, filter_id + '.json')
        with open(parts_dest, 'w') as dump_handle:
            json.dump(parts, dump_handle)
        self._zip_handle.write(parts_dest,
                               os.path.relpath(parts_dest, self._tempdir))
        os.unlink(parts_dest)

    def _update_snapshot_status(self, status, error=None):
        self._client.snapshots.update_status(
            self._snapshot_id,
            status=status,
            error=error
        )

    def _dump_metadata(self, manager_version):
        ctx.logger.info('Dumping metadata')
        metadata = {
            constants.M_VERSION: str(manager_version),
        }
        metadata_filename = os.path.join(
            self._tempdir,
            constants.METADATA_FILENAME
        )
        with open(metadata_filename, 'w') as f:
            json.dump(metadata, f)
        self._zip_handle.write(
            metadata_filename,
            os.path.relpath(metadata_filename, self._tempdir))
        os.unlink(metadata_filename)

    def _get_snapshot_archive_name(self):
        """Return the base name for the snapshot archive
        """
        snapshots_dir = self._get_and_create_snapshots_dir()
        snapshot_dir = os.path.join(snapshots_dir, self._snapshot_id)
        # Cope with existing dir from a previous attempt to create a snap with
        # the same name
        os.makedirs(snapshot_dir, exist_ok=True)
        return os.path.join(snapshot_dir, '{}.zip'.format(self._snapshot_id))

    def _get_and_create_snapshots_dir(self):
        """Create (if necessary) and return the snapshots directory
        """
        snapshots_dir = os.path.join(
            self._config.file_server_root,
            FILE_SERVER_SNAPSHOTS_FOLDER
        )
        if not os.path.exists(snapshots_dir):
            os.makedirs(snapshots_dir)
        return snapshots_dir


def get_all(method, kwargs=None):
    kwargs = kwargs or {}
    data = []
    total = 1

    while len(data) < total:
        result = method(**kwargs)
        total = result.metadata['pagination']['total']
        data.extend(result)
        kwargs['_offset'] = len(data)

    return data
