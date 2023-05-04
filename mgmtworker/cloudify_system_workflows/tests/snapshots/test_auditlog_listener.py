from unittest import mock

from cloudify_system_workflows.tests.snapshots.mocks import (
    AuditLogResponse,
    prepare_snapshot_create_with_mocks,
    TWO_TENANTS_LIST_SE,
    ONE_BLUEPRINT_LIST_SE,
    TWO_BLUEPRINTS_LIST_SE
)


def test_reconnect():
    auditlog_stream_se = [
        AuditLogResponse([{
            'id': 1192,
            'ref_table': 'blueprints',
            'ref_id': 0,
            'ref_identifier': {'id': 'bp1', 'tenant_name': 'tenant1'},
            'operation': 'update',
            'creator_name': '',
            'execution_id': '',
            'created_at': '2023-04-05T09:27:57.926'
        }]),
        Exception('breaking connection'),
        AuditLogResponse([{
            'id': 1193,
            'ref_table': 'blueprints',
            'ref_id': 0,
            'ref_identifier': {'id': 'bp1', 'tenant_name': 'tenant1'},
            'operation': 'update',
            'creator_name': '',
            'execution_id': '',
            'created_at': '2023-04-05T09:27:57.927'
        }]),
    ]
    with prepare_snapshot_create_with_mocks(
        'test-reconnect-snapshot',
        rest_mocks=[
            (mock.Mock, (dump_type, 'dump'), [[]])
            for dump_type in [
                'user_groups', 'tenants', 'users', 'permissions', 'sites',
                'plugins', 'secrets_providers', 'secrets', 'deployments',
                'inter_deployment_dependencies', 'executions',
                'execution_groups', 'deployment_groups', 'deployment_updates',
                'plugins_update', 'deployments_filters', 'blueprints_filters',
                'execution_schedules', 'nodes', 'node_instances', 'agents',
                'operations', 'events',
            ]
        ] + [
            (mock.AsyncMock, ('auditlog', 'stream'), auditlog_stream_se),
            (mock.Mock, ('tenants', 'list'), TWO_TENANTS_LIST_SE),
            (mock.Mock, ('blueprints', 'list'), TWO_BLUEPRINTS_LIST_SE),
            (mock.Mock, ('blueprints', 'dump'), [['bp1', 'bp2']]),
        ],
    ) as snap_cre:
        snap_cre._append_new_object_from_auditlog = mock.Mock()
        snap_cre.create(timeout=0.2)
        snap_cre._append_new_object_from_auditlog.assert_has_calls([
            mock.call({
                'id': 1192,
                'ref_table': 'blueprints',
                'ref_id': 0,
                'ref_identifier': {'id': 'bp1', 'tenant_name': 'tenant1'},
                'operation': 'update',
                'creator_name': '',
                'execution_id': '',
                'created_at': '2023-04-05T09:27:57.926'
            }),
            mock.call({
                'id': 1193,
                'ref_table': 'blueprints',
                'ref_id': 0,
                'ref_identifier': {'id': 'bp1', 'tenant_name': 'tenant1'},
                'operation': 'update',
                'creator_name': '',
                'execution_id': '',
                'created_at': '2023-04-05T09:27:57.927'
            }),
        ])


def test_dont_append_new_blueprints():
    auditlog_stream_se = [
        AuditLogResponse([{
            'id': 1293,
            'ref_table': 'blueprints',
            'ref_id': 2,
            'ref_identifier': {'id': 'bp2', 'tenant_name': 'tenant1'},
            'operation': 'create',
            'creator_name': 'admin',
            'execution_id': '',
            'created_at': '2023-04-05T10:27:57.927',
        }]),
        AuditLogResponse([{
            'id': 1294,
            'ref_table': 'blueprints',
            'ref_id': 1,
            'ref_identifier': {'id': 'bp1', 'tenant_name': 'tenant1'},
            'operation': 'update',
            'creator_name': 'admin',
            'execution_id': '',
            'created_at': '2023-04-05T10:27:57.928',
        }]),
    ]
    with prepare_snapshot_create_with_mocks(
        'test-snapshot-dont-append-new-blueprints',
        rest_mocks=[
            (mock.Mock, (dump_type, 'dump'), [[]])
            for dump_type in [
                'user_groups', 'tenants', 'users', 'permissions', 'sites',
                'plugins', 'secrets_providers', 'secrets', 'deployments',
                'inter_deployment_dependencies', 'executions',
                'execution_groups', 'deployment_groups', 'deployment_updates',
                'plugins_update', 'deployments_filters', 'blueprints_filters',
                'execution_schedules', 'nodes', 'node_instances', 'agents',
                'operations', 'events',
            ]
        ] + [
            (mock.AsyncMock, ('auditlog', 'stream'), auditlog_stream_se),
            (mock.Mock, ('tenants', 'list'), TWO_TENANTS_LIST_SE),
            (mock.Mock, ('blueprints', 'list'), ONE_BLUEPRINT_LIST_SE),
            (mock.Mock, ('blueprints', 'dump'), [['bp1']]),
        ],
    ) as snap_cre:
        snap_cre._append_new_object_from_auditlog = mock.Mock()
        snap_cre.create(timeout=0.2)
        snap_cre._append_new_object_from_auditlog.assert_called_once_with({
            'id': 1294,
            'ref_table': 'blueprints',
            'ref_id': 1,
            'ref_identifier': {'id': 'bp1', 'tenant_name': 'tenant1'},
            'operation': 'update',
            'creator_name': 'admin',
            'execution_id': '',
            'created_at': '2023-04-05T10:27:57.928'
        })
