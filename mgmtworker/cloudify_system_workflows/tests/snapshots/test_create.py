import json
import os
import zipfile
from unittest import mock

import pytest

from cloudify_system_workflows.snapshots.snapshot_create import EMPTY_B64_ZIP
from cloudify_system_workflows.tests.snapshots.utils import (
    AuditLogResponse,
    load_snapshot_to_dict,
    prepare_snapshot_create_with_mocks,
    FAKE_EXECUTION_ID,
    FAKE_MANAGER_VERSION,
    EMPTY_TENANTS_LIST_SE,
    ONE_TENANTS_LIST_SE,
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
        assert metadata == {
            'snapshot_version': FAKE_MANAGER_VERSION,
            'execution_id': FAKE_EXECUTION_ID,
        }


def test_dump_management():
    with prepare_snapshot_create_with_mocks(
        'test-dump-management',
        rest_mocks=[
            (mock.Mock, ('tenants', 'list'), EMPTY_TENANTS_LIST_SE),
            (mock.Mock, ('user_groups', 'dump'), [[]]),
            (mock.Mock, ('tenants', 'dump'), [[]]),
            (mock.Mock, ('users', 'dump'), [[]]),
            (mock.Mock, ('permissions', 'dump'), [[]]),
        ],
    ) as sc:
        sc._dump_management()
        sc._client.blueprints.dump.assert_not_called()
        sc._client.permissions.dump.assert_called_once_with()
        sc._client.user_groups.dump.assert_called_once_with()
        sc._client.users.dump.assert_called_once_with()
        sc._client.tenants.dump.assert_called_once_with()


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
            (mock.Mock, (dump_type, 'dump'), [[]])
            for dump_type in ['sites', 'plugins', 'secrets_providers',
                              'secrets', 'blueprints',
                              'inter_deployment_dependencies',
                              'deployment_groups', 'deployment_updates',
                              'plugins_update', 'deployments_filters',
                              'blueprints_filters', 'execution_schedules',
                              'nodes', 'node_instances', 'agents', 'events',
                              'operations', 'tasks_graphs']
        ] + [
            (mock.Mock, ('tenants', 'list'), TWO_TENANTS_LIST_SE),
            (mock.Mock, ('blueprints', 'list'), TWO_BLUEPRINTS_LIST_SE),
            (mock.Mock, ('deployments', 'dump'),
             [[{'id': 'd1'}, {'id': 'd2'}]]),
            (mock.Mock, ('deployments', 'get'),
             {'workdir_zip': EMPTY_B64_ZIP}),
            (mock.Mock, ('inter_deployment_dependencies', 'dump'), [[]]),
            (mock.Mock, ('executions', 'dump'),
             [[{'id': 'e1'}, {'id': 'e2'}]]),
            (mock.Mock, ('execution_groups', 'dump'),
             [[{'id': 'eg1'}, {'id': 'eg2'}]]),
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
            method.assert_called_once_with()
        for dump_type in ['nodes', 'agents']:
            method = getattr(cli, dump_type).dump
            method.assert_called_once_with(deployment_ids={'d1', 'd2'})
        cli.node_instances.dump.assert_called_once_with(
            deployment_ids={'d1', 'd2'},
            get_broker_conf=sc._agents_handler.get_broker_conf
        )
        cli.events.dump.assert_called_once_with(
            execution_ids={'e1', 'e2'},
            execution_group_ids={'eg1', 'eg2'},
            include_logs=False)
        cli.operations.dump.assert_called_once_with(execution_ids={'e1', 'e2'})


def test_create_success():
    with prepare_snapshot_create_with_mocks(
        'test-create-success',
        rest_mocks=[
            (mock.Mock, (dump_type, 'dump'), [[]])
            for dump_type in ['user_groups', 'tenants', 'users', 'permissions',
                              'sites', 'plugins', 'secrets_providers',
                              'secrets', 'blueprints', 'deployments',
                              'inter_deployment_dependencies',
                              'deployment_groups', 'deployment_updates',
                              'plugins_update', 'deployments_filters',
                              'blueprints_filters', 'execution_schedules',
                              'nodes', 'node_instances', 'agents', 'events',
                              'operations', 'tasks_graphs']
        ] + [
            (mock.Mock, ('tenants', 'list'), TWO_TENANTS_LIST_SE),
            (mock.Mock, ('blueprints', 'list'), TWO_BLUEPRINTS_LIST_SE),
            (mock.Mock, ('executions', 'dump'),
             [[{'id': 'e1'}, {'id': 'e2'}]]),
            (mock.Mock, ('execution_groups', 'dump'),
             [[{'id': 'eg1'}, {'id': 'eg2'}]]),
            (mock.AsyncMock, ('auditlog', 'stream'), AuditLogResponse([])),
        ],
    ) as sc:
        sc.create(timeout=0.2)
        sc._tenant_clients['tenant1'].executions.dump.assert_called_once_with()
        sc._tenant_clients['tenant1'].events.dump.assert_called_once_with(
            execution_ids={'e1', 'e2'},
            execution_group_ids={'eg1', 'eg2'},
            include_logs=True)
        sc._client.snapshots.update_status.assert_called_once_with(
            sc._snapshot_id, status='created', error=None)
        assert os.path.isfile(sc._archive_dest.with_suffix('.zip'))


def test_create_events_dump_failure():
    with prepare_snapshot_create_with_mocks(
        'test-create-events-dump-failure',
        rest_mocks=[
            (mock.Mock, (dump_type, 'dump'), [[]])
            for dump_type in ['user_groups', 'tenants', 'users', 'permissions',
                              'sites', 'plugins', 'secrets_providers',
                              'secrets', 'blueprints', 'deployments',
                              'inter_deployment_dependencies',
                              'executions', 'execution_groups',
                              'deployment_groups', 'deployment_updates',
                              'plugins_update', 'deployments_filters',
                              'blueprints_filters', 'execution_schedules',
                              'nodes', 'node_instances', 'agents',
                              'operations']
        ] + [
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
            (mock.Mock, (dump_type, 'dump'), [[]])
            for dump_type in [
                'user_groups', 'tenants', 'users', 'permissions', 'sites',
                'plugins', 'secrets_providers', 'secrets', 'blueprints',
                'deployments', 'inter_deployment_dependencies', 'executions',
                'execution_groups', 'deployment_groups', 'deployment_updates',
                'plugins_update', 'deployments_filters', 'blueprints_filters',
                'execution_schedules', 'nodes', 'node_instances', 'agents',
                'operations', 'events',
            ]
        ] + [
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
            (mock.Mock, (dump_type, 'dump'), [[]])
            for dump_type in ['user_groups', 'tenants', 'users', 'permissions',
                              'sites', 'plugins', 'secrets_providers',
                              'secrets', 'blueprints', 'execution_groups',
                              'inter_deployment_dependencies',
                              'deployment_groups', 'deployment_updates',
                              'plugins_update', 'deployments_filters',
                              'blueprints_filters', 'execution_schedules',
                              'nodes', 'node_instances', 'agents',
                              'operations', 'tasks_graphs']
        ] + [
            (mock.Mock, ('tenants', 'list'), TWO_TENANTS_LIST_SE),
            (mock.Mock, ('blueprints', 'list'), TWO_BLUEPRINTS_LIST_SE),
            (mock.Mock, ('deployments', 'dump'),
             [[{'id': 'd1'}, {'id': 'd2'}]]),
            (mock.Mock, ('deployments', 'get'),
             {'workdir_zip': EMPTY_B64_ZIP}),
            (mock.Mock, ('executions', 'dump'),
             [[{'id': 'e1'}, {'id': 'e2'}]]),
            (mock.AsyncMock, ('auditlog', 'stream'), AuditLogResponse([])),
        ],
        include_events=False,
    ) as sc:
        sc.create(timeout=0.2)
        sc._tenant_clients['tenant1'].events.dump.assert_not_called()


def test_create_with_events():
    timestamp_seconds = '2023-05-09T08:28:46'
    events_dump_se = [[
        {
            '__entity': {
                '_storage_id': 1,
                'timestamp': f'{timestamp_seconds}.001Z',
                'message': 'message #1',
            },
            '__source': 'executions',
            '__source_id': 'e1'
        },
        {
            '__entity': {
                '_storage_id': 2,
                'timestamp': f'{timestamp_seconds}.002Z',
                'message': 'message #2',
            },
            '__source': 'executions',
            '__source_id': 'e1'
        },
        {
            '__entity': {
                '_storage_id': 3,
                'timestamp': f'{timestamp_seconds}.003Z',
                'message': 'message #1',
            },
            '__source': 'executions',
            '__source_id': 'e2'
        },
    ]]
    with prepare_snapshot_create_with_mocks(
        'test-create-with-events',
        rest_mocks=[
            (mock.Mock, (dump_type, 'dump'), [[]])
            for dump_type in ['user_groups', 'tenants', 'users', 'permissions',
                              'sites', 'plugins', 'secrets_providers',
                              'secrets', 'blueprints', 'execution_groups',
                              'inter_deployment_dependencies',
                              'deployment_groups', 'deployment_updates',
                              'plugins_update', 'deployments_filters',
                              'blueprints_filters', 'execution_schedules',
                              'nodes', 'node_instances', 'agents',
                              'operations', 'tasks_graphs']
        ] + [
            (mock.Mock, ('tenants', 'list'), ONE_TENANTS_LIST_SE),
            (mock.Mock, ('blueprints', 'list'), TWO_BLUEPRINTS_LIST_SE),
            (mock.Mock, ('deployments', 'dump'),
             [[{'id': 'd1'}, {'id': 'd2'}]]),
            (mock.Mock, ('deployments', 'get'),
             {'workdir_zip': EMPTY_B64_ZIP}),
            (mock.Mock, ('executions', 'dump'),
             [[{'id': 'e1'}, {'id': 'e2'}]]),
            (mock.Mock, ('events', 'dump'), events_dump_se),
            (mock.AsyncMock, ('auditlog', 'stream'), AuditLogResponse([])),
        ],
    ) as sc:
        sc.create(timeout=0.2)
        sc._tenant_clients['tenant1'].events.dump.assert_called_once_with(
            execution_ids={'e1', 'e2'},
            execution_group_ids=set(),
            include_logs=True
        )

        snapshot = load_snapshot_to_dict(sc._archive_dest.with_suffix('.zip'))
        e1_key = ('events', 'executions', 'e1')
        e2_key = ('events', 'executions', 'e2')
        e1_events = snapshot['tenants']['tenant1'][e1_key]
        e2_events = snapshot['tenants']['tenant1'][e2_key]

        assert e1_events['latest_timestamp'] == f'{timestamp_seconds}.003Z'
        assert len(e1_events['items']) == 2
        assert e2_events['latest_timestamp'] == f'{timestamp_seconds}.003Z'
        assert len(e2_events['items']) == 1


def test_create_many_blueprints():
    timestamp_seconds = '2023-05-09T08:28:47'
    many_blueprints_dump_se = [[{
        'id': f'bp{n}',
        'tenant_name': 'tenant1',
        'created_at': f'{timestamp_seconds}.{(n % 1000):03d}Z'
    } for n in range(1002)]]
    with prepare_snapshot_create_with_mocks(
        'test-create-many-blueprints',
        rest_mocks=[
            (mock.Mock, (dump_type, 'dump'), [[]])
            for dump_type in ['user_groups', 'tenants', 'users', 'permissions',
                              'sites', 'plugins', 'secrets_providers',
                              'secrets', 'deployments',
                              'inter_deployment_dependencies',
                              'deployment_groups', 'deployment_updates',
                              'executions', 'execution_groups',
                              'plugins_update', 'deployments_filters',
                              'blueprints_filters', 'execution_schedules',
                              'nodes', 'node_instances', 'agents', 'events',
                              'operations', 'tasks_graphs']
        ] + [
            (mock.Mock, ('tenants', 'list'), ONE_TENANTS_LIST_SE),
            (mock.Mock, ('blueprints', 'dump'), many_blueprints_dump_se),
            (mock.AsyncMock, ('auditlog', 'stream'), AuditLogResponse([])),
        ],
    ) as sc:
        sc.create(timeout=0.2)
        sc._tenant_clients['tenant1'].blueprints.dump.assert_called_once_with()

        snapshot = load_snapshot_to_dict(sc._archive_dest.with_suffix('.zip'))
        blueprints = snapshot['tenants']['tenant1'][('blueprints', None, None)]

        assert len(blueprints['items']) == 1002
        assert blueprints['latest_timestamp'] == f'{timestamp_seconds}.999Z'


def test_create_with_plugins():
    timestamp_seconds = '2023-05-09T08:28:48'
    many_plugins_dump_se = [[{
        'id': f'plugin{n}',
        'tenant_name': 'tenant1',
        'uploaded_at': f'{timestamp_seconds}.{(n % 1000):03d}Z'
    } for n in range(995, 1005)]]
    with prepare_snapshot_create_with_mocks(
        'test-create-with-plugins',
        rest_mocks=[
            (mock.Mock, (dump_type, 'dump'), [[]])
            for dump_type in ['user_groups', 'tenants', 'users', 'permissions',
                              'sites', 'blueprints', 'secrets_providers',
                              'secrets', 'deployments',
                              'inter_deployment_dependencies',
                              'deployment_groups', 'deployment_updates',
                              'executions', 'execution_groups',
                              'plugins_update', 'deployments_filters',
                              'blueprints_filters', 'execution_schedules',
                              'nodes', 'node_instances', 'agents', 'events',
                              'operations', 'tasks_graphs']
        ] + [
            (mock.Mock, ('tenants', 'list'), ONE_TENANTS_LIST_SE),
            (mock.Mock, ('plugins', 'dump'), many_plugins_dump_se),
            (mock.AsyncMock, ('auditlog', 'stream'), AuditLogResponse([])),
        ],
    ) as sc:
        sc.create(timeout=0.2)
        sc._tenant_clients['tenant1'].plugins.dump.assert_called_once_with()

        snapshot = load_snapshot_to_dict(sc._archive_dest.with_suffix('.zip'))
        plugins = snapshot['tenants']['tenant1'][('plugins', None, None)]

        assert plugins['latest_timestamp'] == f'{timestamp_seconds}.999Z'
        assert len(plugins['items']) == 10


def test_create_with_agents():
    timestamp_seconds = '2023-05-09T08:28:49'
    many_agents_dump_se = [[{
        '__entity': {
            'id': f'agent{n}',
            'tenant_name': 'tenant1',
            'created_at': f'{timestamp_seconds}.{(n % 1000):03d}Z',
        },
        '__source_id': 'd1',
    } for n in range(995, 1005)]]
    with prepare_snapshot_create_with_mocks(
        'test-create-with-agents',
        rest_mocks=[
            (mock.Mock, (dump_type, 'dump'), [[]])
            for dump_type in ['user_groups', 'tenants', 'users', 'permissions',
                              'sites', 'blueprints', 'secrets_providers',
                              'secrets', 'inter_deployment_dependencies',
                              'deployment_groups', 'deployment_updates',
                              'executions', 'execution_groups',
                              'plugins_update', 'deployments_filters',
                              'blueprints_filters', 'execution_schedules',
                              'nodes', 'node_instances', 'events', 'plugins',
                              'operations', 'tasks_graphs']
        ] + [
            (mock.Mock, ('tenants', 'list'), ONE_TENANTS_LIST_SE),
            (mock.Mock, ('deployments', 'dump'),
             [[{'id': 'd1'}, {'id': 'd2'}]]),
            (mock.Mock, ('deployments', 'get'),
             {'workdir_zip': EMPTY_B64_ZIP}),
            (mock.Mock, ('agents', 'dump'), many_agents_dump_se),
            (mock.AsyncMock, ('auditlog', 'stream'), AuditLogResponse([])),
        ],
    ) as sc:
        sc.create(timeout=0.2)
        sc._tenant_clients['tenant1'].agents.dump.assert_called_once_with(
                deployment_ids={'d1', 'd2'})

        snapshot = load_snapshot_to_dict(sc._archive_dest.with_suffix('.zip'))
        d1_agents = snapshot['tenants']['tenant1'][('agents', None, 'd1')]
        d2_agents = snapshot['tenants']['tenant1'][('agents', None, 'd2')]

        assert d1_agents['latest_timestamp'] == f'{timestamp_seconds}.999Z'
        assert len(d1_agents['items']) == 10

        assert d2_agents == {'items': {}, 'latest_timestamp': None}


def test_create_deployment_workdir():
    with prepare_snapshot_create_with_mocks(
        'test-create-deployment-workdir',
        rest_mocks=[
            (mock.Mock, (dump_type, 'dump'), [[]])
            for dump_type in ['user_groups', 'tenants', 'users', 'permissions',
                              'sites', 'blueprints', 'secrets_providers',
                              'secrets', 'inter_deployment_dependencies',
                              'deployment_groups', 'deployment_updates',
                              'executions', 'execution_groups', 'agents',
                              'plugins_update', 'deployments_filters',
                              'blueprints_filters', 'execution_schedules',
                              'nodes', 'node_instances', 'events', 'plugins',
                              'operations', 'tasks_graphs']
        ] + [
            (mock.Mock, ('tenants', 'list'), ONE_TENANTS_LIST_SE),
            (mock.Mock, ('deployments', 'dump'), [[{'id': 'd1'}]]),
            (mock.Mock, ('deployments', 'get'),
             {'workdir_zip': 'non-empty-workdir-content'}),
            (mock.AsyncMock, ('auditlog', 'stream'), AuditLogResponse([])),
        ],
    ) as sc:
        sc.create(timeout=0.2)
        with zipfile.ZipFile(sc._archive_dest.with_suffix('.zip'), 'r') as zf:
            d1_archive = zf.read(
                    'tenants/tenant1/deployments/d1.b64zip')
            assert d1_archive == b'non-empty-workdir-content'


def test_create_tasks_graphs():
    with prepare_snapshot_create_with_mocks(
        'test-create-tasks-graphs',
        rest_mocks=[
            (mock.Mock, (dump_type, 'dump'), [[]])
            for dump_type in ['user_groups', 'tenants', 'users', 'permissions',
                              'secrets_providers', 'secrets',
                              'sites', 'blueprints', 'deployments',
                              'inter_deployment_dependencies',
                              'deployment_groups', 'deployment_updates',
                              'executions', 'execution_groups', 'agents',
                              'plugins_update', 'deployments_filters',
                              'blueprints_filters', 'execution_schedules',
                              'nodes', 'node_instances', 'events', 'plugins',
                              'operations', '']
        ] + [
            (mock.Mock, ('tenants', 'list'), ONE_TENANTS_LIST_SE),
            (mock.Mock, ('executions', 'dump'), [[{'id': 'e1'}]]),
            (mock.Mock, ('operations', 'dump'), [[
                {
                    '__entity': {'id': 'op1', 'tasks_graph_id': 'tg1'},
                    '__source_id': 'e1',
                },
                {
                    '__entity': {'id': 'op2', 'tasks_graph_id': 'tg2'},
                    '__source_id': 'e1',
                },
                {
                    '__entity': {'id': 'op3', 'tasks_graph_id': 'tg1'},
                    '__source_id': 'e2',
                },
            ]]),
            (mock.Mock, ('tasks_graphs', 'dump'), [[
                {
                    '__entity': {
                        'created_at': '2022-11-25T15:14:39.194Z',
                        'id': 'tg1',
                        'name': 'update_check_drift',
                        'execution_id': 'e1'
                    },
                    '__source_id': 'e1'
                }
            ]]),
            (mock.AsyncMock, ('auditlog', 'stream'), AuditLogResponse([])),
        ],
    ) as sc:
        sc.create(timeout=0.2)
        cli = sc._tenant_clients['tenant1']
        cli.operations.dump.assert_called_once_with(execution_ids={'e1'})
        cli.tasks_graphs.dump.assert_called_once_with(
            execution_ids={'e1'},
            operations={
                'e1': [
                    {'id': 'op1', 'tasks_graph_id': 'tg1'},
                    {'id': 'op2', 'tasks_graph_id': 'tg2'}
                ],
                'e2': [
                    {'id': 'op3', 'tasks_graph_id': 'tg1'}
                ]
            }
        )
        snapshot = load_snapshot_to_dict(sc._archive_dest.with_suffix('.zip'))
        e1_key = ('tasks_graphs', None, 'e1')
        e1_tasks_graphs = snapshot['tenants']['tenant1'][e1_key]

        assert len(e1_tasks_graphs['items']) == 1
