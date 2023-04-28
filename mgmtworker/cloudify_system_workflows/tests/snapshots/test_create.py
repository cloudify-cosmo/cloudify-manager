import json
import os
from unittest import mock

import pytest

from cloudify_system_workflows.tests.snapshots.mocks import (
    AuditLogResponse,
    prepare_snapshot_create_with_mocks,
    FAKE_MANAGER_VERSION,
    EMPTY_TENANTS_LIST_SE,
    TWO_TENANTS_LIST_SE,
    TWO_BLUEPRINTS_LIST_SE,
)


def test_dump_metadata():
    with prepare_snapshot_create_with_mocks(
        'test-dump-metadata',
        rest_mocks=[(mock.Mock, ('tenants', 'list'), EMPTY_TENANTS_LIST_SE)],
    ) as sc:
        sc._dump_metadata()
        with open(sc._temp_dir / 'metadata.json', 'r') as f:
            metadata = json.load(f)
        assert metadata == {'snapshot_version': FAKE_MANAGER_VERSION}


def test_dump_management():
    with prepare_snapshot_create_with_mocks(
        'test-dump-management',
        rest_mocks=[(mock.Mock, ('tenants', 'list'), EMPTY_TENANTS_LIST_SE)],
    ) as sc:
        sc._dump_management()
        sc._client.blueprints.dump.assert_not_called()
        sc._client.permissions.dump.assert_called_once_with(
                sc._temp_dir / 'mgmt' / 'permissions')
        sc._client.user_groups.dump.assert_called_once_with(
                sc._temp_dir / 'mgmt' / 'user_groups')
        sc._client.users.dump.assert_called_once_with(
                sc._temp_dir / 'mgmt' / 'users')
        sc._client.tenants.dump.assert_called_once_with(
                sc._temp_dir / 'mgmt' / 'tenants')


def test_dump_composer():
    with prepare_snapshot_create_with_mocks(
        'test-dump-composer',
        rest_mocks=[(mock.Mock, ('tenants', 'list'), EMPTY_TENANTS_LIST_SE)],
    ) as sc:
        sc._dump_composer()
        c_dir = sc._temp_dir / 'composer'
        sc._composer_client.blueprints.dump.assert_called_once_with(c_dir)
        sc._composer_client.configuration.dump.assert_called_once_with(c_dir)
        sc._composer_client.favorites.dump.assert_called_once_with(c_dir)


def test_dump_stage_no_tenants():
    with prepare_snapshot_create_with_mocks(
        'test-dump-stage-no-tenants',
        rest_mocks=[(mock.Mock, ('tenants', 'list'), EMPTY_TENANTS_LIST_SE)],
    ) as sc:
        sc._dump_stage()
        s_dir = sc._temp_dir / 'stage'
        sc._stage_client.blueprint_layouts.dump.assert_called_once_with(s_dir)
        sc._stage_client.configuration.dump.assert_called_once_with(s_dir)
        sc._stage_client.page_groups.dump.assert_called_once_with(s_dir)
        sc._stage_client.pages.dump.assert_called_once_with(s_dir)
        sc._stage_client.templates.dump.assert_called_once_with(s_dir)
        sc._stage_client.widgets.dump.assert_called_once_with(s_dir)
        sc._stage_client.ua.dump.assert_not_called()


def test_dump_stage_two_tenants():
    with prepare_snapshot_create_with_mocks(
        'test-dump-stage-no-tenants',
        rest_mocks=[(mock.Mock, ('tenants', 'list'), TWO_TENANTS_LIST_SE)],
    ) as sc:
        sc._dump_stage()
        sc._stage_client.ua.dump.assert_has_calls([
            mock.call(sc._temp_dir / 'stage' / 'tenant1', tenant='tenant1'),
            mock.call(sc._temp_dir / 'stage' / 'tenant2', tenant='tenant2'),
        ])


def test_dump_tenants():
    with prepare_snapshot_create_with_mocks(
        'test-dump-tenants',
        rest_mocks=[
            (mock.Mock, ('tenants', 'list'), TWO_TENANTS_LIST_SE),
            (mock.Mock, ('blueprints', 'list'), TWO_BLUEPRINTS_LIST_SE),
            (mock.Mock, ('deployments', 'dump'), [['d1', 'd2']]),
            (mock.Mock, ('executions', 'dump'), [['e1', 'e2']]),
            (mock.Mock, ('execution_groups', 'dump'), [['eg1', 'eg2']]),
        ],
        include_logs=False
    ) as sc:
        sc._dump_tenant('tenant1')
        cli = sc._tenant_clients['tenant1']
        for dump_type in ['sites', 'plugins', 'secrets_providers', 'secrets',
                          'blueprints', 'deployments', 'deployment_groups',
                          'inter_deployment_dependencies', 'executions',
                          'execution_groups', 'deployment_updates',
                          'plugins_update', 'deployments_filters',
                          'blueprints_filters', 'execution_schedules']:
            method = getattr(sc._tenant_clients['tenant1'], dump_type).dump
            method.assert_called_once_with(
                sc._temp_dir / 'tenants' / 'tenant1' / dump_type)
        for dump_type in ['nodes', 'agents']:
            method = getattr(cli, dump_type).dump
            method.assert_called_once_with(
                sc._temp_dir / 'tenants' / 'tenant1' / dump_type,
                deployment_ids=['d1', 'd2'])
        cli.node_instances.dump.assert_called_once_with(
            sc._temp_dir / 'tenants' / 'tenant1' / 'node_instances',
            deployment_ids=['d1', 'd2'],
            get_broker_conf=sc._agents_handler.get_broker_conf
        )
        cli.events.dump.assert_called_once_with(
            sc._temp_dir / 'tenants' / 'tenant1' / 'events',
            execution_ids=['e1', 'e2'],
            execution_group_ids=['eg1', 'eg2'],
            include_logs=False)
        cli.operations.dump.assert_called_once_with(
            sc._temp_dir / 'tenants' / 'tenant1' / 'tasks_graphs',
            execution_ids=['e1', 'e2'])


def test_create_success():
    with prepare_snapshot_create_with_mocks(
        'test-create-success',
        rest_mocks=[
            (mock.Mock, ('tenants', 'list'), TWO_TENANTS_LIST_SE),
            (mock.Mock, ('blueprints', 'list'), TWO_BLUEPRINTS_LIST_SE),
            (mock.Mock, ('executions', 'dump'), [['e1', 'e2']]),
            (mock.Mock, ('execution_groups', 'dump'), [['eg1', 'eg2']]),
            (mock.AsyncMock, ('auditlog', 'stream'), AuditLogResponse([])),
        ],
    ) as sc:
        sc.create(timeout=0.2)
        sc._tenant_clients['tenant1'].executions.dump.assert_called_once_with(
            sc._temp_dir / 'tenants' / 'tenant1' / 'executions',
        )
        sc._tenant_clients['tenant1'].events.dump.assert_called_once_with(
            sc._temp_dir / 'tenants' / 'tenant1' / 'events',
            execution_ids=['e1', 'e2'],
            execution_group_ids=['eg1', 'eg2'],
            include_logs=True)
        sc._client.snapshots.update_status.assert_called_once_with(
            sc._snapshot_id, status='created', error=None)
        assert os.path.isfile(sc._archive_dest.with_suffix('.zip'))


def test_create_events_dump_failure():
    with prepare_snapshot_create_with_mocks(
        'test-create-events-dump-failure',
        rest_mocks=[
            (mock.Mock, ('tenants', 'list'), TWO_TENANTS_LIST_SE),
            (mock.Mock, ('blueprints', 'list'), TWO_BLUEPRINTS_LIST_SE),
            (mock.Mock, ('events', 'dump'), [BaseException('test failure')]),
            (mock.AsyncMock, ('auditlog', 'stream'), AuditLogResponse([])),
        ],
    ) as sc:
        with pytest.raises(BaseException):
            sc.create(timeout=0.2)
        sc._tenant_clients['tenant1'].deployments.dump.assert_called_once()
        sc._client.snapshots.update_status.assert_called_once_with(
            sc._snapshot_id, status='failed', error='test failure')
        assert not os.path.exists(f'{sc._archive_dest}.zip')


def test_create_failure_removes_snapshot_zip():
    with prepare_snapshot_create_with_mocks(
        'test-failure-removes-snapshot-zip',
        rest_mocks=[
            (mock.Mock, ('tenants', 'list'), TWO_TENANTS_LIST_SE),
            (mock.Mock, ('blueprints', 'list'), TWO_BLUEPRINTS_LIST_SE),
            (mock.AsyncMock, ('auditlog', 'stream'), AuditLogResponse([])),
        ],
    ) as sc:
        sc._update_snapshot_status = mock.Mock(side_effect=[
            Exception('error setting status to `created`'),
            mock.Mock(),
        ])
        with pytest.raises(BaseException):
            sc.create(timeout=0.2)
        sc._tenant_clients['tenant1'].deployments.dump.assert_called_once()
        assert not os.path.exists(f'{sc._archive_dest}.zip')


def test_create_skip_events():
    with prepare_snapshot_create_with_mocks(
        'test-create-skip-events',
        rest_mocks=[
            (mock.Mock, ('tenants', 'list'), TWO_TENANTS_LIST_SE),
            (mock.Mock, ('blueprints', 'list'), TWO_BLUEPRINTS_LIST_SE),
            (mock.Mock, ('deployments', 'dump'), [['d1', 'd2']]),
            (mock.Mock, ('executions', 'dump'), [['e1', 'e2']]),
            (mock.AsyncMock, ('auditlog', 'stream'), AuditLogResponse([])),
        ],
        include_events=False,
    ) as sc:
        sc.create(timeout=0.2)
        sc._tenant_clients['tenant1'].events.dump.assert_not_called()
