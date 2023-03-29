import os
import json
import shutil
import tempfile
import zipfile

from cloudify.workflows import ctx
from cloudify.manager import get_rest_client
from cloudify.constants import FILE_SERVER_SNAPSHOTS_FOLDER

from . import constants, utils, INCLUDES
from .agents import Agents


EMPTY_B64_ZIP = 'UEsFBgAAAAAAAAAAAAAAAAAAAAAAAA=='
ENTITIES_PER_GROUPING = 500
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
        self._composer_client = utils.get_composer_client()
        self._stage_client = utils.get_stage_client()
        self._tenant_clients = {}
        self._zip_handle = None
        self._archive_dest = self._get_snapshot_archive_name()
        self._agents_handler = Agents()

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
                self._dump_composer()
                self._dump_stage()
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

    def _dump_composer(self):
        dump_dir_name = os.path.join(self._tempdir, 'composer')
        os.makedirs(dump_dir_name, exist_ok=True)
        for dump_type in INCLUDES['composer']:
            dump_client = getattr(self._composer_client, dump_type)
            if dump_type == 'blueprints':
                self._dump_data(
                    dump_client.get_snapshot(),
                    os.path.join(dump_dir_name, 'blueprints.zip')
                )
                self._dump_data(
                    dump_client.get_metadata(),
                    os.path.join(dump_dir_name, 'blueprints.json')
                )
            else:
                self._dump_data(
                    dump_client.get_snapshot(),
                    os.path.join(dump_dir_name, f'{dump_type}.json')
                )

    def _dump_stage(self):
        dump_dir_name = os.path.join(self._tempdir, 'stage')
        os.makedirs(dump_dir_name, exist_ok=True)
        for dump_type in INCLUDES['stage']:
            dump_client = getattr(self._stage_client,
                                  dump_type.replace('-', '_'))
            file_ext = 'zip' if dump_type == 'widgets' else 'json'

            if dump_type == 'ua':
                for tenant in self._tenants:
                    os.makedirs(os.path.join(dump_dir_name, tenant),
                                exist_ok=True)
                    self._dump_data(
                            dump_client.get_snapshot(tenant=tenant),
                            os.path.join(dump_dir_name, tenant,
                                         f'{dump_type}.{file_ext}'),
                    )
            else:
                self._dump_data(
                        dump_client.get_snapshot(),
                        os.path.join(dump_dir_name, f'{dump_type}.{file_ext}'),
                )

    def _dump_data(self, data, file_name):
        """Dump data into the file."""
        with open(file_name, 'wb') as fh:
            fh.write(data)
        self._zip_handle.write(
            file_name,
            os.path.relpath(file_name, self._tempdir),
        )

    def _dump_tenant(self, tenant_name):
        """Dump objects from a tenant."""
        self._dump_objects('sites', tenant_name)
        self._dump_objects('plugins', tenant_name)
        self._dump_objects('secrets_providers', tenant_name)
        self._dump_objects('secrets', tenant_name)
        self._dump_objects('blueprints', tenant_name)
        self._dump_objects('deployments', tenant_name)
        self._dump_objects('inter_deployment_dependencies', tenant_name)
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
            add_tenant_dir = False
            if tenant_name not in self._tenant_clients:
                add_tenant_dir = True
                self._tenant_clients[tenant_name] = get_rest_client(
                    tenant=tenant_name)
            client = self._tenant_clients[tenant_name]
            dump_dir = os.path.join(self._tempdir, 'tenants', tenant_name)
            if add_tenant_dir:
                os.makedirs(dump_dir, exist_ok=True)
                self._zip_handle.write(dump_dir,
                                       os.path.relpath(dump_dir,
                                                       self._tempdir))
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
            'plugins': '.zip',
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
                if dump_type == 'plugins':
                    getattr(client, dump_type).download(entity_id, entity_dest,
                                                        full_archive=True)
                else:
                    getattr(client, dump_type).download(entity_id, entity_dest)
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
        elif part == 'node_instances':
            # for "agent" node instances, store broker config in runtime-props
            # as well, so that during agent upgrade, we can connect to the old
            # rabbitmq. This is later analyzed by snapshot_restore,
            # _inject_broker_config, and by several calls in
            # cloudify-agent/operations.py (related to creating the AMQP
            # client there)
            for ni in parts:
                runtime_properties = ni.get('runtime_properties') or {}
                if 'cloudify_agent' not in runtime_properties:
                    continue
                broker_conf = self._agents_handler.get_broker_conf(ni)
                runtime_properties['cloudify_agent'].update(broker_conf)

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
