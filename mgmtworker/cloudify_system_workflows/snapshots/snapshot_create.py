import json
import os
import pathlib
import queue
import shutil
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

from cloudify.constants import FILE_SERVER_SNAPSHOTS_FOLDER
from cloudify.manager import get_rest_client
from cloudify.workflows import ctx
from cloudify_rest_client import CloudifyClient
from cloudify_system_workflows.snapshots import constants
from cloudify_system_workflows.snapshots.agents import Agents
from cloudify_system_workflows.snapshots.audit_listener import AuditLogListener
from cloudify_system_workflows.snapshots.ui_clients import (ComposerClient,
                                                            StageClient)
from cloudify_system_workflows.snapshots.utils import (DictToAttributes,
                                                       get_manager_version,
                                                       get_composer_client,
                                                       get_stage_client)

DUMP_ENTITIES_PER_FILE = 500
EMPTY_B64_ZIP = 'UEsFBgAAAAAAAAAAAAAAAAAAAAAAAA=='


class SnapshotCreate:
    """SnapshotCreate is a class, which handles snapshot creation process."""
    _snapshot_id: str
    _config: DictToAttributes
    _include_logs: bool
    _include_events: bool
    _client: CloudifyClient
    _tenant_clients: dict[str, CloudifyClient]
    _composer_client: ComposerClient
    _stage_client: StageClient
    _archive_dest: Path
    _temp_dir: Path
    _ids_dumped: dict[str, list[str]]

    def __init__(
            self,
            snapshot_id: str,
            config: dict[str, Any],
            include_logs=True,
            include_events=True,
    ):
        self._snapshot_id = snapshot_id
        self._config = DictToAttributes(config)
        self._include_logs = include_logs
        self._include_events = include_events

        # Initialize clients
        self._client = get_rest_client()
        self._composer_client = get_composer_client()
        self._stage_client = get_stage_client()

        # Initialize tenants and per-tenant clients
        self._tenants = self._get_tenants()
        self._tenant_clients = {}
        for tenant_name in set(self._tenants.keys()):
            if tenant_name not in self._tenant_clients:
                self._tenant_clients[tenant_name] = get_rest_client(
                        tenant=tenant_name)

        # Initialize directories
        snapshot_dir = _prepare_snapshot_dir(self._config.file_server_root,
                                             self._snapshot_id)
        self._archive_dest = snapshot_dir / f'{self._snapshot_id}'
        self._temp_dir = _prepare_temp_dir()

        # Initialize tools
        self._agents_handler = Agents()
        self._auditlog_queue = queue.Queue()
        self._auditlog_listener = AuditLogListener(self._client,
                                                   self._auditlog_queue)
        self._ids_dumped = {}

    def create(self, timeout=10):
        """Dumps manager's data and some metadata into a single zip file"""
        ctx.logger.debug('Using `new` snapshot format')
        self._auditlog_listener.start(self._tenant_clients)
        try:
            self._dump_metadata()
            self._dump_management()
            self._dump_composer()
            self._dump_stage()
            for tenant_name in self._tenants:
                self._dump_tenant(tenant_name)
            self._append_from_auditlog(timeout)
            self._create_archive()
            self._update_snapshot_status(self._config.created_status)
            ctx.logger.info('Snapshot created successfully')
        except BaseException as exc:
            self._update_snapshot_status(self._config.failed_status, str(exc))
            ctx.logger.error(f'Snapshot creation failed: {str(exc)}')
            if os.path.exists(self._archive_dest.with_suffix('.zip')):
                os.unlink(self._archive_dest.with_suffix('.zip'))
            raise
        finally:
            ctx.logger.debug(f'Removing temp dir: {self._temp_dir}')
            shutil.rmtree(self._temp_dir)

    def _get_tenants(self):
        return {
            tenant['name']: tenant
            for tenant in get_all(
                self._client.tenants.list,
                {'_include': ['name', 'rabbitmq_password']})
        }

    def _dump_metadata(self):
        ctx.logger.debug('Dumping metadata')
        manager_version = get_manager_version(self._client)
        metadata = {
            constants.M_VERSION: str(manager_version),
            constants.M_EXECUTION_ID: ctx.execution_id,
        }
        with open(self._temp_dir / constants.METADATA_FILENAME, 'w') as f:
            json.dump(metadata, f)

    def _dump_management(self):
        for dump_type in ['user_groups', 'tenants', 'users', 'permissions']:
            ctx.logger.debug(f'Dumping {dump_type}')
            client = getattr(self._client, dump_type)
            entities = client.dump()
            self._write_files(None, dump_type, entities)

    def _dump_composer(self):
        output_dir = self._temp_dir / 'composer'
        os.makedirs(output_dir, exist_ok=True)
        for dump_type in ['blueprints', 'configuration', 'favorites']:
            ctx.logger.debug(f'Dumping composer\'s {dump_type}')
            getattr(self._composer_client, dump_type).dump(output_dir)

    def _dump_stage(self):
        output_dir = self._temp_dir / 'stage'
        os.makedirs(output_dir, exist_ok=True)
        for dump_type in ['blueprint_layouts', 'configuration', 'page_groups',
                          'pages', 'templates', 'ua', 'widgets']:
            ctx.logger.debug(f'Dumping stage\'s {dump_type}')
            dump_client = getattr(self._stage_client, dump_type)
            if dump_type == 'ua':
                for tenant_name in self._tenants:
                    os.makedirs(output_dir / tenant_name, exist_ok=True)
                    dump_client.dump(output_dir / tenant_name,
                                     tenant=tenant_name)
            else:
                dump_client.dump(output_dir)

    def _dump_tenant(self, tenant_name):
        for dump_type in ['sites', 'plugins', 'secrets_providers', 'secrets',
                          'blueprints', 'deployments', 'deployment_groups',
                          'nodes', 'node_instances', 'agents',
                          'inter_deployment_dependencies',
                          'executions', 'execution_groups', 'events',
                          'deployment_updates', 'plugins_update',
                          'deployments_filters', 'blueprints_filters',
                          'tasks_graphs', 'execution_schedules']:
            if dump_type == 'events' and not self._include_events:
                continue
            ctx.logger.debug(f'Dumping {dump_type} of {tenant_name}')
            api = getattr(self._tenant_clients[tenant_name], dump_type)
            entities = api.dump(
                    **self._dump_call_extra_args(tenant_name, dump_type)
            )
            self._ids_dumped[dump_type] = \
                self._write_files(tenant_name, dump_type, entities)

    def _dump_call_extra_args(self, tenant_name: str, dump_type: str):
        if dump_type in ['agents', 'nodes']:
            return {'deployment_ids': self._ids_dumped['deployments']}
        if dump_type == 'node_instances':
            return {
                'deployment_ids': self._ids_dumped['deployments'],
                'get_broker_conf': self._agents_handler.get_broker_conf
            }
        if dump_type == 'events':
            return {
                'execution_ids': self._ids_dumped['executions'],
                'execution_group_ids': self._ids_dumped['execution_groups'],
                'include_logs': self._include_logs,
            }
        if dump_type == 'tasks_graphs':
            execution_ids = self._ids_dumped['executions']
            operations = defaultdict(list)
            for op in self._tenant_clients[tenant_name].operations\
                    .dump(execution_ids=execution_ids):
                operations[op['__source_id']].append(op['__entity'])
            return {
                'execution_ids': execution_ids,
                'operations': operations,
            }
        return {}

    def _write_files(self, tenant_name, dump_type, data):
        """Dumps all data of dump_type into JSON files inside output_dir."""
        data_buckets = {}
        output_dir = self._prepare_output_dir(tenant_name)
        os.makedirs(output_dir, exist_ok=True)
        ids_added = []
        latest_timestamp = None

        # Prepare data for dumping and create archives
        for entity_raw in data:
            source, source_id, entity_id, entity = _prepare_dump_entity(
                    dump_type, entity_raw)
            if (source, source_id) not in data_buckets:
                data_buckets[(source, source_id)] = []
            data_buckets[(source, source_id)].append(entity)
            latest_timestamp = _extract_latest_timestamp(entity, dump_type,
                                                         latest_timestamp)
            if dump_type in ['blueprints', 'deployments', 'plugins']:
                _write_dump_archive(
                        dump_type,
                        entity_id,
                        output_dir,
                        self._tenant_clients[tenant_name]
                )
            if entity_id:
                ids_added.append(entity_id)
                self._auditlog_listener.append_entity(tenant_name, dump_type,
                                                      entity_id)
        # Dump the data as JSON files
        filenum = _get_max_filenum_in_dir(output_dir) or 0
        for (source, source_id), items in data_buckets.items():
            data = {'type': dump_type}
            if source:
                data['source'] = source
            if source_id:
                data['source_id'] = source_id
            if latest_timestamp:
                data['latest_timestamp'] = latest_timestamp
            remainder = len(items) % DUMP_ENTITIES_PER_FILE
            file_count = len(items) // DUMP_ENTITIES_PER_FILE
            if remainder:
                file_count += 1
            for i in range(file_count):
                filenum += 1
                output_file = output_dir / f'{filenum:08d}.json'
                start = i * DUMP_ENTITIES_PER_FILE
                finish = (i + 1) * DUMP_ENTITIES_PER_FILE
                data['items'] = items[start:finish]
                with open(output_file, 'w') as handle:
                    json.dump(data, handle)
        return ids_added

    def _prepare_output_dir(self, tenant_name: str):
        return self._temp_dir / 'tenants' / tenant_name if tenant_name \
            else self._temp_dir / 'mgmt'

    def _create_archive(self):
        ctx.logger.debug('Creating snapshot archive')
        shutil.make_archive(self._archive_dest, 'zip', self._temp_dir)

    def _append_from_auditlog(self, timeout):
        try:
            # Fetch all the remaining items in a queue, don't wait longer
            # than `timeout` seconds in case queue is empty.
            while audit_log := self._auditlog_queue.get(timeout=timeout):
                self._append_new_object_from_auditlog(audit_log)
        except queue.Empty:
            self._auditlog_listener.stop()
            self._auditlog_listener.join(timeout=timeout)

    def _append_new_object_from_auditlog(self, audit_log):
        # to be implemented in RND-309
        pass

    def _update_snapshot_status(self, status, error=None):
        self._client.snapshots.update_status(
            self._snapshot_id,
            status=status,
            error=error
        )


def _prepare_temp_dir() -> Path:
    """Prepare temporary (working) directory structure"""
    temp_dir = tempfile.mkdtemp('-snapshot-data')
    nested = ['mgmt', 'tenants', 'composer', 'stage']
    for nested_dir in nested:
        os.makedirs(os.path.join(temp_dir, nested_dir))
    return Path(temp_dir)


def _prepare_snapshot_dir(file_server_root: str, snapshot_id: str) -> Path:
    snapshot_dir = os.path.join(
            file_server_root,
            FILE_SERVER_SNAPSHOTS_FOLDER,
            snapshot_id,
    )
    os.makedirs(snapshot_dir, exist_ok=True)
    return Path(snapshot_dir)


def _prepare_dump_entity(dump_type, entity_raw):
    if '__entity' in entity_raw:
        entity = entity_raw['__entity']
        source = entity_raw.get('__source')
        source_id = entity_raw.get('__source_id')
    else:
        entity = entity_raw
        source = None
        source_id = None

    if dump_type == 'events':
        entity_id = entity.pop('_storage_id')
    else:
        entity_id = entity.get('id')

    return source, source_id, entity_id, entity


def _extract_latest_timestamp(entity: dict[str, Any], dump_type: str,
                              latest_timestamp: str | None) -> str | None:
    if dump_type == 'events':
        timestamp = entity['timestamp']
    elif dump_type == 'plugins':
        timestamp = entity['uploaded_at']
    else:
        timestamp = entity.get('created_at')

    if not timestamp:
        return latest_timestamp

    if not latest_timestamp:
        latest_timestamp = timestamp
    else:
        latest_timestamp = max(latest_timestamp, timestamp)
    return latest_timestamp


def _write_dump_archive(
        dump_type: str,
        entity_id: str,
        output_dir: pathlib.Path,
        api: CloudifyClient
):
    dest_dir = (output_dir / f'{dump_type}').resolve()
    os.makedirs(dest_dir, exist_ok=True)
    suffix = {
        'plugins': '.zip',
        'blueprints': '.tar.gz',
        'deployments': '.b64zip',
    }[dump_type]

    entity_dest = dest_dir / f'{entity_id}{suffix}'
    client = getattr(api, dump_type)
    if dump_type == 'deployments':
        data = client.get(
           deployment_id=entity_id, _include=['workdir_zip'],
           include_workdir=True)
        b64_zip = data['workdir_zip']
        if b64_zip == EMPTY_B64_ZIP:
            return
        with open(entity_dest, 'w') as dump_handle:
            dump_handle.write(b64_zip)
    elif dump_type == 'plugins':
        client.download(entity_id, entity_dest, full_archive=True)
    else:
        client.download(entity_id, entity_dest)


def _get_max_filenum_in_dir(dirname: pathlib.Path):
    try:
        max_file_name = max(
                f for f in dirname.iterdir()
                if f.is_file and f.name.endswith('.json')
        )
        if max_file_name:
            return int(max_file_name.stem)
    except (FileNotFoundError, ValueError):
        pass
    return None


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
