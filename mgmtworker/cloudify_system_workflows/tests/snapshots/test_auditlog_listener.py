from unittest import mock

from cloudify_system_workflows.snapshots.snapshot_create import EMPTY_B64_ZIP
from cloudify_system_workflows.tests.snapshots.utils import (
    AuditLogResponse,
    ExecutionResponse,
    ExecutionGroupResponse,
    ListResponse,
    load_snapshot_to_dict,
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
                'operations', 'tasks_graphs', 'events',
            ]
        ] + [
            (mock.AsyncMock, ('auditlog', 'stream'), auditlog_stream_se),
            (mock.Mock, ('tenants', 'list'), TWO_TENANTS_LIST_SE),
            (mock.Mock, ('blueprints', 'list'), TWO_BLUEPRINTS_LIST_SE),
            (mock.Mock, ('blueprints', 'dump'),
             [[{'id': 'bp1'}, {'id': 'bp2'}]]),
        ],
    ) as snap_cre:
        snap_cre._dump_from_auditlog = mock.Mock()
        snap_cre.create(timeout=0.2)
        snap_cre._dump_from_auditlog.assert_called_once_with({
            'tenant1': {'blueprints': {'bp1'}}
        })


def test_dont_append_new_blueprints():
    auditlog_stream_se = [
        AuditLogResponse([{
            'id': 1292,
            'ref_table': 'blueprints',
            'ref_id': 2,
            'ref_identifier': {'id': 'bp2', 'tenant_name': 'tenant1'},
            'operation': 'create',
            'creator_name': 'admin',
            'execution_id': '',
            'created_at': '2023-04-05T10:27:57.927',
        }]),
        AuditLogResponse([{
            'id': 1293,
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
                'operations', 'tasks_graphs', 'events',
            ]
        ] + [
            (mock.AsyncMock, ('auditlog', 'stream'), auditlog_stream_se),
            (mock.Mock, ('tenants', 'list'), TWO_TENANTS_LIST_SE),
            (mock.Mock, ('blueprints', 'list'), ONE_BLUEPRINT_LIST_SE),
            (mock.Mock, ('blueprints', 'dump'), [[{'id': 'bp1'}]]),
        ],
    ) as snap_cre:
        snap_cre._dump_from_auditlog = mock.Mock()
        snap_cre.create(timeout=0.2)
        snap_cre._dump_from_auditlog.assert_called_once_with({
            'tenant1': {'blueprints': {'bp1'}}
        })


def test_append_related_executions():
    auditlog_stream_se = [
        AuditLogResponse([{
            'id': 1392,
            'ref_table': 'executions',
            'ref_id': 1,
            'ref_identifier': {'id': 'exec2', 'tenant_name': 'tenant1'},
            'operation': 'update',
            'creator_name': 'admin',
            'execution_id': '',
            'created_at': '2023-04-05T11:27:57.926',
        }]),
        AuditLogResponse([{
            'id': 1393,
            'ref_table': 'execution_groups',
            'ref_id': 1,
            'ref_identifier': {'id': 'execgr2', 'tenant_name': 'tenant1'},
            'operation': 'update',
            'creator_name': 'admin',
            'execution_id': '',
            'created_at': '2023-04-05T11:27:57.927',
        }]),
    ]
    executions_get_se = ExecutionResponse(id='exec2', deployment_id='d1')
    execution_groups_get_se = ExecutionGroupResponse(id='execgr2',
                                                     deployment_group_id='g1')
    with prepare_snapshot_create_with_mocks(
        'test-snapshot-append-related-executions',
        rest_mocks=[
            (mock.Mock, (dump_type, 'dump'), [[]])
            for dump_type in [
                'user_groups', 'tenants', 'users', 'permissions', 'sites',
                'plugins', 'secrets_providers', 'secrets', 'blueprints',
                'inter_deployment_dependencies', 'deployment_updates',
                'plugins_update', 'deployments_filters', 'blueprints_filters',
                'execution_schedules', 'nodes', 'node_instances', 'agents',
                'operations', 'tasks_graphs', 'events',
            ]
        ] + [
            (mock.AsyncMock, ('auditlog', 'stream'), auditlog_stream_se),
            (mock.Mock, ('tenants', 'list'), TWO_TENANTS_LIST_SE),
            (mock.Mock, ('deployments', 'dump'), [[{'id': 'd1'}]]),
            (mock.Mock, ('deployments', 'get'),
             {'workdir_zip': EMPTY_B64_ZIP}),
            (mock.Mock, ('deployment_groups', 'dump'), [[{'id': 'g1'}]]),
            (mock.Mock, ('executions', 'dump'), [[{'id': 'exec1'}]]),
            (mock.Mock, ('executions', 'get'), executions_get_se),
            (mock.Mock, ('execution_groups', 'dump'), [[{'id': 'execgr1'}]]),
            (mock.Mock, ('execution_groups', 'get'), execution_groups_get_se),
        ],
    ) as snap_cre:
        snap_cre._dump_from_auditlog = mock.Mock()
        snap_cre.create(timeout=0.2)
        snap_cre._dump_from_auditlog.assert_called_once_with({
            'tenant1': {
                'executions': {'exec2'},
                'execution_groups': {'execgr2'},
            }
        })


def test_append_related_entities():
    auditlog_stream_se = [
        AuditLogResponse([{
            'id': 1491,
            'ref_table': 'blueprints',
            'ref_id': 1,
            'ref_identifier': {'id': 'bp1', 'tenant_name': 'tenant1'},
            'operation': 'update',
            'creator_name': 'admin',
            'execution_id': '',
            'created_at': '2023-04-05T12:27:57.926',
        }]),
        AuditLogResponse([{
            'id': 1492,
            'ref_table': 'deployments',
            'ref_id': 1,
            'ref_identifier': {'id': 'd1', 'tenant_name': 'tenant1'},
            'operation': 'update',
            'creator_name': 'admin',
            'execution_id': '',
            'created_at': '2023-04-05T12:27:57.927',
        }]),
    ]
    deployments_list_se = [
        ListResponse(
                items=[{'id': 'd1', 'tenant_name': 'tenant1'}],
                metadata={'pagination': {'offset': 0, 'size': 1, 'total': 1}}
        )
    ]
    with prepare_snapshot_create_with_mocks(
        'test-snapshot-append-related-entities',
        rest_mocks=[
            (mock.Mock, (dump_type, 'dump'), [[]])
            for dump_type in [
                'user_groups', 'tenants', 'users', 'permissions', 'sites',
                'plugins', 'secrets_providers', 'secrets', 'deployment_groups',
                'inter_deployment_dependencies', 'deployment_updates',
                'plugins_update', 'deployments_filters', 'blueprints_filters',
                'execution_schedules', 'nodes', 'node_instances', 'agents',
                'executions', 'execution_groups', 'operations', 'tasks_graphs',
                'events',
            ]
        ] + [
            (mock.AsyncMock, ('auditlog', 'stream'), auditlog_stream_se),
            (mock.Mock, ('tenants', 'list'), TWO_TENANTS_LIST_SE),
            (mock.Mock, ('blueprints', 'dump'), [
                [
                    {'id': 'bp1'},
                    {'id': 'bp2'},
                ],
                [
                    {'id': 'bp1', 'created_by': 'someone'},
                ],
            ]),
            (mock.Mock, ('deployments', 'list'), deployments_list_se),
            (mock.Mock, ('deployments', 'dump'), [
                [{'id': 'd1'}],
                [{'id': 'd1', 'display_name': 'deployment #1'}],
            ]),
            (mock.Mock, ('deployments', 'get'),
             {'workdir_zip': EMPTY_B64_ZIP}),
        ],
    ) as sc:
        sc.create(timeout=0.2)
        snapshot = load_snapshot_to_dict(sc._archive_dest.with_suffix('.zip'))

        blueprints = snapshot['tenants']['tenant1'][('blueprints', None, None)]

        assert blueprints['items'] == {
            'bp1': {'id': 'bp1', 'created_by': 'someone'},
            'bp2': {'id': 'bp2'}
        }
