import json
import os
import queue
import shutil
import tempfile
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


class SnapshotCreate:
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

    def create(self, timeout=10):
        ctx.logger.debug('Using `new` snapshot format')
        self._auditlog_listener.start(
                self._tenant_clients,
                self._blueprints_list(),
        )
        try:
            self._dump_metadata()
            self._dump_management()
            self._dump_composer()
            self._dump_stage()
            for tenant_name in self._tenants:
                self._dump_tenant(tenant_name)
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
            try:
                # Fetch all the remaining items in a queue, don't wait longer
                # than `timeout` seconds in case queue is empty.
                while audit_log := self._auditlog_queue.get(timeout=timeout):
                    # to be implemented in RND-309
                    self._append_new_object_from_auditlog(audit_log)
            except queue.Empty:
                self._auditlog_listener.stop()
                self._auditlog_listener.join(timeout=timeout)
            ctx.logger.debug(f'Removing temp dir: {self._temp_dir}')
            shutil.rmtree(self._temp_dir)

    def _get_tenants(self):
        return {
            tenant['name']: tenant
            for tenant in get_all(
                self._client.tenants.list,
                {'_include': ['name', 'rabbitmq_password']})
        }

    def _blueprints_list(self) -> list[tuple[str, str]]:
        for blueprint in get_all(
            self._client.blueprints.list,
            {'_all_tenants': True, '_include': ['tenant_name', 'id']}
        ):
            yield blueprint['tenant_name'], blueprint['id']

    def _dump_metadata(self):
        ctx.logger.debug('Dumping metadata')
        manager_version = get_manager_version(self._client)
        metadata = {
            constants.M_VERSION: str(manager_version),
        }
        with open(self._temp_dir / constants.METADATA_FILENAME, 'w') as f:
            json.dump(metadata, f)

    def _dump_management(self):
        for dump_type in ['user_groups', 'tenants', 'users', 'permissions']:
            ctx.logger.debug(f'Dumping {dump_type}')
            output_dir = self._temp_dir / 'mgmt' / dump_type
            os.makedirs(output_dir, exist_ok=True)
            getattr(self._client, dump_type).dump(output_dir)

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
        deployment_ids = []
        execution_ids = []
        execution_group_ids = []
        for dump_type in ['sites', 'plugins', 'secrets_providers', 'secrets',
                          'blueprints', 'deployments', 'deployment_groups',
                          'nodes', 'node_instances', 'agents',
                          'inter_deployment_dependencies',
                          'executions', 'execution_groups',
                          'events', 'operations',
                          'deployment_updates', 'plugins_update',
                          'deployments_filters', 'blueprints_filters',
                          'execution_schedules']:
            if dump_type == 'events' and not self._include_events:
                continue

            ctx.logger.debug(f'Dumping {dump_type} of {tenant_name}')
            output_dir = self._temp_dir / 'tenants' / tenant_name / dump_type
            extra_args = {}
            if dump_type in ['nodes', 'agents']:
                extra_args = {'deployment_ids': deployment_ids}
            elif dump_type in ['node_instances']:
                extra_args = {
                    'deployment_ids': deployment_ids,
                    'get_broker_conf': self._agents_handler.get_broker_conf
                }
            elif dump_type in ['events']:
                output_dir = self._temp_dir / 'tenants' / tenant_name
                extra_args = {
                    'execution_ids': execution_ids,
                    'execution_group_ids': execution_group_ids,
                    'include_logs': self._include_logs,
                }
            elif dump_type in ['operations']:
                output_dir = self._temp_dir / 'tenants' / \
                             tenant_name / 'tasks_graphs'
                extra_args = {
                    'execution_ids': execution_ids,
                }

            if dump_type == 'events':
                if execution_ids:
                    os.makedirs(output_dir / 'executions_events',
                                exist_ok=True)
                if execution_group_ids:
                    os.makedirs(output_dir / 'execution_groups_events',
                                exist_ok=True)
            else:
                os.makedirs(output_dir, exist_ok=True)
            ids_dumped = getattr(
                    self._tenant_clients[tenant_name],
                    dump_type
            ).dump(output_dir, **extra_args)

            if dump_type == 'deployments':
                deployment_ids = ids_dumped
            elif dump_type == 'executions':
                execution_ids = ids_dumped
            elif dump_type == 'execution_groups':
                execution_group_ids = ids_dumped

    def _create_archive(self):
        ctx.logger.debug('Creating snapshot archive')
        shutil.make_archive(self._archive_dest, 'zip', self._temp_dir)

    def _update_snapshot_status(self, status, error=None):
        self._client.snapshots.update_status(
            self._snapshot_id,
            status=status,
            error=error
        )

    def _append_new_object_from_auditlog(self, audit_log):
        # to be implemented in RND-364
        pass


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
