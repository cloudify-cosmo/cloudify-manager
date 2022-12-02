from copy import deepcopy
from dataclasses import dataclass
import json
from math import ceil
import os
import shutil

import mock
import pytest

from cloudify_rest_client.responses import ListResponse

from cloudify_system_workflows.snapshots.snapshot_create import (
    constants,
    EMPTY_B64_ZIP,
    EXTRA_DUMP_KWARGS,
    GET_DATA,
    INCLUDES,
    SnapshotCreate,
)

FAKE_MANAGER_VERSION = 'THIS_MANAGER_VERSION'
ENTITIES_PER_GROUP = 2
MOCK_CLIENT_RESPONSES = {
    None: {
        'user_groups': {
            'list': [{'data': 'user_groups_list'}],
        },
        'tenants': {
            'list': [{'name': 'tenant1'}, {'name': 'tenant2'}],
        },
        'users': {
            'list': [{'data': 'users_list'}],
        },
        'permissions': {
            'list': [{'data': 'perms_list'}],
        },
        'snapshots': {
            'update_status': [],
        },
    },
    'tenant1': {
        'sites': {
            'list': [{'id': 'sites_list_t1'}],
        },
        'plugins': {
            'list': [{'id': 'plugin_t1'}],
            'download': 'abc123',
            'download_yaml': 'def456',
        },
        'secrets': {
            'export': [{'id': 'secrets_list_t1'}],
        },
        'blueprints': {
            'list': [
                {'id': 'blueprint_t1',
                 'upload_execution': {'id': 'some_execution_uploading_t1'}}],
            'download': 'ghi789',
        },
        'deployments': {
            'list': [{'id': 'deployment_t1.1',
                      'create_execution': 'somecreate',
                      'latest_execution': 'somelatest'},
                     {'id': 'deployment_t1.2',
                      'create_execution': 'somecreate2',
                      'latest_execution': 'somelatest2'},
                     {'id': 'deployment_t1.3',
                      'create_execution': 'somecreate3',
                      'latest_execution': 'somelatest3'}],
            'get': [{'workdir_zip': 'DEF1'},
                    {'workdir_zip': EMPTY_B64_ZIP},
                    {'workdir_zip': 'DEF3'}],
        },
        'deployment_groups': {
            'list': [{'id': 'deployments_groups_list_t1'}],
        },
        'executions': {
            'list': [{'id': 'executions_list_t1'}],
        },
        'execution_groups': {
            'list': [{'id': 'execution_groups_list_t1'}],
        },
        'deployment_updates': {
            'list': [{'id': 'deployment_updates_list_t1'}],
        },
        'plugins_update': {
            'list': [{'id': 'plugins_update_list_t1'}],
        },
        'deployments_filters': {
            'list': [{'id': 'deployments_filters_list_t1.1',
                      'is_system_filter': False},
                     {'id': 'deployments_filters_list_t1.2',
                      'is_system_filter': True}],
        },
        'blueprints_filters': {
            'list': [{'id': 'blueprints_filters_list_t1.1',
                      'is_system_filter': True},
                     {'id': 'blueprints_filters_list_t1.2',
                      'is_system_filter': False}],
        },
        'execution_schedules': {
            'list': [{'id': 'execution_schedules_list_t1'}],
        },
        'nodes': {
            'list': [{'id': 'nodes_list_t1'}],
        },
        'node_instances': {
            'list': [{'id': 'node_instances_list_t1'}],
        },
        'agents': {
            'list': [{'id': 'agents_list_t1'}],
        },
        'events': {
            'list': [{'id': 'events_list_t1'}],
        },
        'tasks_graphs': {
            'list': [{'id': 'tasks_graphs_list_t1'}],
        },
        'operations': {
            'list': [{'id': 'some_operation_t2',
                      'tasks_graph_id': 'tasks_graphs_list_t1'}],
        },
    },
    'tenant2': {
        'sites': {
            'list': [{'id': 'sites_list_t2'}],
        },
        'plugins': {
            'list': [{'id': 'plugin_t2'}],
            'download': 'abc123',
            'download_yaml': 'def456',
        },
        'secrets': {
            'export': [{'id': 'secrets_list_t2'}],
        },
        'blueprints': {
            'list': [{'id': 'blueprint_t2'}],
            'download': 'ghi789',
        },
        'deployments': {
            'list': [{'id': 'deployment_t2',
                      'create_execution': 'somecreate_t2',
                      'latest_execution': 'somelatest_t2'}],
            'get': [{'workdir_zip': 'XYZF'}],
        },
        'deployment_groups': {
            'list': [{'id': 'deployments_groups_list_t2'}],
        },
        'executions': {
            'list': [{'id': 'executions_list_t2'}],
        },
        'execution_groups': {
            'list': [{'id': 'execution_groups_list_t2'}],
        },
        'deployment_updates': {
            'list': [{'id': 'deployment_updates_list_t2'}],
        },
        'plugins_update': {
            'list': [{'id': 'plugins_update_list_t2'}],
        },
        'deployments_filters': {
            'list': [{'id': 'deployments_filters_list_t2',
                      'is_system_filter': False}],
        },
        'blueprints_filters': {
            'list': [{'id': 'blueprints_filters_list_t2',
                      'is_system_filter': False}],
        },
        'execution_schedules': {
            'list': [{'id': 'execution_schedules_list_t2'}],
        },
        'nodes': {
            'list': [{'id': 'nodes_list_t2'}],
        },
        'node_instances': {
                'list': [{'id': 'node_instances_list_t2'}],
        },
        'agents': {
            'list': [{'id': 'agents_list_t2'}],
        },
        'events': {
            'list': [{'id': 'events_list_t2'}],
        },
        'tasks_graphs': {
            'list': [{'id': 'tasks_graphs_list_t2'}],
        },
        'operations': {
            'list': [{'id': 'some_operation_t2',
                      'tasks_graph_id': 'tasks_graph_list_t2'}],
        },
    },
}


@dataclass
class _Call:
    args: tuple
    kwargs: dict
    # So that we can see what call is failing when tests fail
    endpoint: str

    def __hash__(self):
        return hash((self.args, json.dumps(self.kwargs, sort_keys=True),
                     self.endpoint))


class _FakeCaller:
    def __init__(self, results, call_type, entity_type):
        self.results = results
        self.calls = []
        self.call_type = call_type
        self.entity_type = entity_type
        self.endpoint = f'{entity_type}.{call_type}'
        self.idx = 0

    def assert_called_once_with(self, *args, **kwargs):
        assert len(self.calls) == 1
        assert self.calls[0] == _Call(args, kwargs, self.endpoint)

    def assert_calls(self, expected_calls):
        # We deliberately don't care about order here to avoid test
        # if we add parallel processing later
        assert set(self.calls) == set(expected_calls)

    def __call__(self, *args, **kwargs):
        # Running this through a fake caller rather than mock so that we can
        # deepcopy to avoid mutating the data we want to compare to later
        self.calls.append(_Call(args, kwargs, self.endpoint))

        if self.entity_type in ['nodes', 'node_instances', 'agents']:
            # Handle deployments' possessions
            dep_id = kwargs['deployment_id']
            results = _mangle_dependents(dep_id, self.results)
        elif self.entity_type in ['tasks_graphs', 'operations']:
            exc_id = kwargs['execution_id']
            results = _mangle_dependents(exc_id, self.results)
        elif self.entity_type == 'events':
            if 'execution_id' in kwargs:
                entity_id_key = 'execution_id'
            else:
                entity_id_key = 'execution_group_id'
            entity_id = kwargs[entity_id_key]
            results = _mangle_dependents(entity_id, self.results)
        else:
            results = self.results

        if self.call_type in ['list', 'export']:
            return ListResponse(
                deepcopy(results),
                {'pagination': {'total': len(results),
                                'size': 1000}},
            )
        elif self.call_type == 'get':
            # Each get should return just one result
            result = deepcopy(results[self.idx])
            self.idx += 1
            return result
        elif 'download' in self.call_type:
            # args are entity_id, destination
            with open(args[1], 'w') as fh:
                fh.write(str(results))
        return results


def _mangle_dependents(entity_id, prior_data):
    results = []
    for result in prior_data:
        result = deepcopy(result)
        result['id'] = entity_id + '_' + result['id']
        if 'tasks_graph_id' in result:
            result['tasks_graph_id'] = \
                entity_id + '_' + result['tasks_graph_id']
        results.append(result)
    return results


def _get_rest_client(tenant=None):
    mock_client = mock.Mock(spec=MOCK_CLIENT_RESPONSES)
    tenant_responses = MOCK_CLIENT_RESPONSES[tenant]
    for group in tenant_responses:
        mock_group = mock.Mock(spec=tenant_responses[group])
        for call, return_value in tenant_responses[group].items():
            setattr(mock_group, call, _FakeCaller(return_value, call, group))
        setattr(mock_client, group, mock_group)
    return mock_client


@pytest.fixture
def mock_get_client():
    with mock.patch(
        'cloudify_system_workflows.snapshots.snapshot_create'
        '.get_rest_client',
        side_effect=_get_rest_client,
    ):
        yield


@pytest.fixture
def mock_shutil_rmtree():
    with mock.patch(
        'cloudify_system_workflows.snapshots.snapshot_create'
        '.shutil.rmtree'
    ):
        yield


@pytest.fixture
def mock_ctx():
    with mock.patch(
        'cloudify_system_workflows.snapshots.snapshot_create'
        '.ctx',
        # Don't try to magicmock the context or we need a context
        new=mock.Mock(),
    ):
        yield


@pytest.fixture
def mock_get_manager_version():
    with mock.patch(
        'cloudify_system_workflows.snapshots.snapshot_create'
        '.utils.get_manager_version',
        return_value=FAKE_MANAGER_VERSION
    ):
        yield


@pytest.fixture
def mock_override_entities_per_grouping():
    with mock.patch(
        'cloudify_system_workflows.snapshots.snapshot_create'
        '.ENTITIES_PER_GROUPING',
        new=ENTITIES_PER_GROUP,
    ):
        yield


def test_create_snapshot(mock_shutil_rmtree, mock_get_manager_version,
                         mock_ctx, mock_get_client,
                         mock_override_entities_per_grouping):
    snap_id = 'testsnapshot'
    snap_cre = SnapshotCreate(
        snapshot_id=snap_id,
        config={
            'created_status': 'created',
            'failed_status': 'failed',
        },
    )
    # Disable archive creation
    snap_cre._create_archive = mock.Mock()
    snap_cre.create()

    tempdir = snap_cre._tempdir

    try:
        _check_snapshot_top_level(tempdir)
        _check_snapshot_mgmt(tempdir, snap_cre._client)
        _assert_tenants(tempdir, snap_cre._tenant_clients)

        _assert_snapshot_status_update(snap_id, True, snap_cre._client)
    finally:
        shutil.rmtree(tempdir)


def _assert_snapshot_status_update(snap_id, success, client):
    assert len(client.snapshots.update_status.calls) == 1
    call = client.snapshots.update_status.calls[0]
    assert call.args == (snap_id, )
    assert len(call.kwargs) == 2
    if success:
        assert call.kwargs['status'] == 'created'
        assert call.kwargs['error'] is None
    else:
        assert call.kwargs['status'] == 'failed'
        assert call.kwargs['error'] is not None


def _check_snapshot_top_level(tempdir):
    top_level_data = set(os.listdir(tempdir))
    assert top_level_data == {'mgmt', 'tenants', constants.METADATA_FILENAME}
    with open(os.path.join(tempdir, constants.METADATA_FILENAME)) as md_handle:
        metadata = json.load(md_handle)
    assert metadata == {constants.M_VERSION: FAKE_MANAGER_VERSION}


def _check_snapshot_mgmt(tempdir, client):
    mgmt_base_dir = os.path.join(tempdir, 'mgmt')
    top_level_mgmt = set(os.listdir(mgmt_base_dir))
    entities = ['user_groups', 'tenants', 'users', 'permissions']
    expected_files = {
        i: f'{i}0.json' for i in entities
    }
    assert top_level_mgmt == set(expected_files.values())
    for entity in entities:
        file_name = expected_files[entity]
        expected_content = MOCK_CLIENT_RESPONSES[None][entity]['list']
        with open(os.path.join(mgmt_base_dir, file_name)) as entity_handle:
            content = json.load(entity_handle)
        assert content == expected_content
        client_group = getattr(client, entity)
        expected_kwargs = EXTRA_DUMP_KWARGS.get(entity, {})
        if entity in INCLUDES:
            expected_kwargs['_include'] = INCLUDES[entity]
        if entity in GET_DATA:
            expected_kwargs['_get_data'] = True
        client_group.list.assert_called_once_with(**expected_kwargs)


def _assert_tenants(tempdir, clients):
    tenants = [tenant for tenant in MOCK_CLIENT_RESPONSES.keys()
               if tenant is not None]

    tenants_dir = os.path.join(tempdir, 'tenants')
    tenants_dir_content = set(os.listdir(tenants_dir))
    assert tenants_dir_content == set(tenants)

    for tenant in tenants:
        tenant_dir = os.path.join(tenants_dir, tenant)

        for r_type, methods_data in MOCK_CLIENT_RESPONSES[tenant].items():
            if r_type == 'secrets':
                method = 'export'
            else:
                method = 'list'
            data = methods_data[method]
            for group in range(0, ceil(len(data) / ENTITIES_PER_GROUP)):
                data_start = group * ENTITIES_PER_GROUP
                data_end = data_start + ENTITIES_PER_GROUP

                if r_type == 'agents' or 'node' in r_type:
                    dep_ids = [
                        dep['id']
                        for dep in MOCK_CLIENT_RESPONSES[tenant][
                            'deployments']['list'][data_start:data_end]
                    ]
                    _check_deployment_entities(
                        r_type, group, data, dep_ids, tenant_dir,
                    )
                    continue
                if r_type in ['events', 'tasks_graphs']:
                    exc_ids = [
                        exc['id']
                        for exc in MOCK_CLIENT_RESPONSES[tenant][
                            'executions']['list'][data_start:data_end]
                    ]
                    group_ids = [
                        group['id']
                        for group in MOCK_CLIENT_RESPONSES[tenant][
                            'execution_groups']['list'][data_start:data_end]
                    ]
                    _check_exec_entities(
                        r_type, group, data, exc_ids, group_ids, tenant_dir,
                        operations=MOCK_CLIENT_RESPONSES[tenant][
                            'operations']['list'],
                    )
                    continue
                if r_type == 'operations':
                    # The stored data on these is checked within tasks_graphs
                    continue

                expected = []
                if r_type.endswith('_filters'):
                    for item in data[data_start:data_end]:
                        if item['is_system_filter']:
                            # We don't expect to copy system filters
                            continue
                        item = deepcopy(item)
                        item.pop('is_system_filter')
                        expected.append(item)
                elif r_type == 'blueprints':
                    expected_executions = []
                    for item in data[data_start:data_end]:
                        item = deepcopy(item)
                        upload_exec = item.pop('upload_execution', None)
                        if upload_exec:
                            expected_executions.append(
                                {item['id']: upload_exec['id']})
                        expected.append(item)
                elif r_type == 'deployments':
                    expected_executions = []
                    for item in data[data_start:data_end]:
                        item = deepcopy(item)
                        create_exc = item.pop('create_execution', None)
                        latest_exc = item.pop('latest_execution', None)
                        if create_exc or latest_exc:
                            execs = {'deployment_id': item['id']}
                            if create_exc:
                                execs['create_execution'] = create_exc
                            if latest_exc:
                                execs['latest_execution'] = latest_exc
                            expected_executions.append(execs)
                        expected.append(item)
                else:
                    expected = data[data_start:data_end]

                _check_resource_type(r_type, group, expected, tenant_dir)

                sub_dir = os.path.join(tenant_dir, f'{r_type}{group}')
                if r_type == 'plugins':
                    stored_plugins = set(os.listdir(sub_dir))
                    expected_plugins = {plugin['id'] + '.zip'
                                        for plugin in expected}
                    assert stored_plugins == expected_plugins
                elif r_type == 'blueprints':
                    _check_resource_type('blueprints_executions', group,
                                         expected_executions, tenant_dir)

                    stored_blueprints = set(os.listdir(sub_dir))
                    expected_blueprints = {blueprint['id'] + '.zip'
                                           for blueprint in expected}
                    assert stored_blueprints == expected_blueprints
                elif r_type == 'deployments':
                    _check_resource_type('deployments_executions', group,
                                         expected_executions, tenant_dir)

                    dep_workdirs = methods_data['get']
                    stored_dep_workdirs = set(os.listdir(sub_dir))
                    expected_dep_workdirs = set()
                    for idx in range(data_start, data_end):
                        if (idx >= len(dep_workdirs)
                            or dep_workdirs[idx][
                                'workdir_zip'] == EMPTY_B64_ZIP):
                            # We don't save empty workdirs.
                            continue
                        expected_dep_workdirs.add(data[idx]['id'] + '.b64zip')
                    assert stored_dep_workdirs == expected_dep_workdirs

        _check_tenant_calls(tenant, MOCK_CLIENT_RESPONSES[tenant],
                            clients[tenant], tenant_dir)


def _check_resource_type(r_type, group, expected, tenant_dir):
    resource_file = os.path.join(tenant_dir, f'{r_type}{group}.json')
    with open(resource_file) as stored_handle:
        stored = json.load(stored_handle)
    assert stored == expected


def _check_deployment_entities(r_type, group, data, dep_ids, tenant_dir):
    entities_path = os.path.join(tenant_dir, f'{r_type}{group}')
    stored_dep_entities = set(os.listdir(entities_path))
    assert stored_dep_entities == {dep_id + '.json' for dep_id in dep_ids}
    _check_stored_dependents(entities_path, dep_ids, data)


def _check_exec_entities(r_type, group, data, exc_ids, group_ids, tenant_dir,
                         operations=None):
    if r_type == 'events':
        execs_path = os.path.join(tenant_dir, 'events', 'executions',
                                  f'{r_type}{group}')
        groups_path = os.path.join(tenant_dir, 'events', 'execution_groups',
                                   f'{r_type}{group}')

        stored_exec_events = set(os.listdir(execs_path))
        stored_group_events = set(os.listdir(groups_path))

        assert stored_exec_events == {exc_id + '.json' for exc_id in exc_ids}
        assert stored_group_events == {group_id + '.json'
                                       for group_id in group_ids}

        _check_stored_dependents(execs_path, exc_ids, data)
        _check_stored_dependents(groups_path, group_ids, data)
    elif r_type == 'tasks_graphs':
        graphs_path = os.path.join(tenant_dir, f'{r_type}{group}')

        stored_graphs = set(os.listdir(graphs_path))

        assert stored_graphs == {exc_id + '.json' for exc_id in exc_ids}

        _check_stored_dependents(graphs_path, exc_ids, data, operations)


def _check_stored_dependents(base_path, parent_ids, data, operations=None):
    for parent_id in parent_ids:
        expected = _mangle_dependents(parent_id, data)
        if operations:
            operations = _mangle_dependents(parent_id, operations)
            for item in expected:
                ops = []
                for op in operations:
                    if op['tasks_graph_id'] == item['id']:
                        op = deepcopy(op)
                        op.pop('tasks_graph_id')
                        ops.append(op)
                if ops:
                    item['operations'] = ops
        dependents_path = os.path.join(base_path, parent_id + '.json')
        with open(dependents_path) as stored_handle:
            stored = json.load(stored_handle)
        assert stored == expected


def _check_tenant_calls(tenant, tenant_mock_data, client, tenant_dir):
    for entity_type, commands in tenant_mock_data.items():
        mock_entity_base = getattr(client, entity_type)
        for command in commands:
            if 'download' in command:
                if command == 'download':
                    if entity_type == 'plugins':
                        extension = 'wgn'
                    else:
                        extension = 'zip'
                    dest = os.path.join(
                        tenant_dir, f'{entity_type}0', f'{{}}.{extension}')
                elif command == 'download_yaml':
                    dest = os.path.join(tenant_dir,
                                        f'{entity_type}0', '{}.yaml')
                expected_calls = {
                    _Call((entity['id'], dest.format(entity['id'])), {},
                          f'{entity_type}.{command}')
                    for entity in tenant_mock_data[entity_type]['list']
                }
            elif 'get' in command:
                # We only need 'get' on deps currently for the workdir
                # We do one 'get' per dep currently (in case of huge workdirs)
                expected_calls = {
                    _Call(
                        (),
                        {
                            '_include': ['workdir_zip'],
                            'deployment_id': dep['id'],
                            'include_workdir': True
                        },
                        f'{entity_type}.{command}',
                    )
                    for dep in tenant_mock_data[entity_type]['list']
                }
            else:
                expected_kwargs = {'_include': INCLUDES[entity_type]}
                expected_kwargs.update(EXTRA_DUMP_KWARGS.get(
                                       entity_type, {}))
                if entity_type in GET_DATA:
                    expected_kwargs['_get_data'] = True
                if entity_type == 'secrets' and command == 'export':
                    expected_kwargs['_include_metadata'] = True

                if 'node' in entity_type or entity_type == 'agents':
                    # We list nodes for each deployment in turn
                    expected_calls = set()
                    for dep in tenant_mock_data['deployments']['list']:
                        dep_kwargs = {'deployment_id': dep['id']}
                        dep_kwargs.update(expected_kwargs)
                        expected_calls.add(_Call(
                            (), dep_kwargs,
                            f'{entity_type}.{command}',
                        ))
                elif entity_type == 'events':
                    # We list events for each execution
                    # and each execution group
                    expected_calls = set()
                    # This might need to be amended if we add a test to not
                    # include logs later, so isn't in EXTRA_DUMP_KWARGS
                    expected_kwargs['include_logs'] = True
                    for source in ['execution', 'execution_group']:
                        for assoc in tenant_mock_data[f'{source}s']['list']:
                            events_kwargs = {f'{source}_id': assoc['id']}
                            events_kwargs.update(expected_kwargs)
                            expected_calls.add(_Call(
                                (), events_kwargs,
                                f'{entity_type}.{command}',
                            ))
                elif entity_type in ['tasks_graphs', 'operations']:
                    # We list tasks graphs and operations for each execution
                    expected_calls = set()
                    for exc in tenant_mock_data['executions']['list']:
                        graph_kwargs = {'execution_id': exc['id']}
                        graph_kwargs.update(expected_kwargs)
                        expected_calls.add(_Call(
                            (), graph_kwargs,
                            f'{entity_type}.{command}',
                        ))
                else:
                    # Shared resources are picked up by the tenant client, so
                    # many resource types need the tenant_name as an arg
                    expected_kwargs['tenant_name'] = tenant
                    expected_calls = set([_Call((), expected_kwargs,
                                          f'{entity_type}.{command}')])

            mock_endpoint = getattr(mock_entity_base, command)
            mock_endpoint.assert_calls(expected_calls)
