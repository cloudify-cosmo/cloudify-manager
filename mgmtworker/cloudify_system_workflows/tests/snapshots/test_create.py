import json
import os
import shutil
from copy import deepcopy
from dataclasses import dataclass
from math import ceil
import tempfile
from unittest import mock

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
        },
        'secrets': {
            'export': [{'id': 'secrets_list_t1'}],
        },
        'blueprints': {
            'list': [{'id': 'blueprint_t1'}],
            'download': 'ghi789',
        },
        'deployments': {
            'list': [{'id': 'deployment_t1.1'},
                     {'id': 'deployment_t1.2'},
                     {'id': 'deployment_t1.3'}],
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
        'secrets_providers': {
            'list': [{'name': 'happyprovider'}],
        },
    },
    'tenant2': {
        'sites': {
            'list': [{'id': 'sites_list_t2'}],
        },
        'plugins': {
            'list': [{'id': 'plugin_t2'}],
            'download': 'abc123',
        },
        'secrets': {
            'export': [{'id': 'secrets_list_t2'}],
        },
        'blueprints': {
            'list': [{'id': 'blueprint_t2'}],
            'download': 'ghi789',
        },
        'deployments': {
            'list': [{'id': 'deployment_t2'}],
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
        'secrets_providers': {
            'list': [{'name': 'something'}],
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


@pytest.fixture
def mock_zipfile():
    with mock.patch(
        'cloudify_system_workflows.snapshots.snapshot_create'
        '.zipfile.ZipFile',
    ) as zipfile:
        data = {
            'base': zipfile,
            'zipfiles': [
                mock.Mock()
                # We need at least as many mocks as we have plugins in the
                # test snapshot, + 1 for the main snapshot.
                # Having more won't hurt.
                for i in range(50)
            ]
        }
        for f in data['zipfiles']:
            f.__enter__ = mock.Mock()
            f.__exit__ = mock.Mock()
        zipfile.side_effect = data['zipfiles']
        yield data


@pytest.fixture
def mock_unlink():
    with mock.patch(
        'cloudify_system_workflows.snapshots.snapshot_create'
        '.os.unlink',
    ) as unlink:
        yield unlink


def test_create_snapshot(mock_shutil_rmtree, mock_get_manager_version,
                         mock_ctx, mock_get_client, mock_unlink,
                         mock_override_entities_per_grouping,
                         mock_zipfile):
    snap_id = 'testsnapshot'
    tempdir = tempfile.mkdtemp(prefix='snap-cre-test')
    snap_cre = SnapshotCreate(
        snapshot_id=snap_id,
        config={
            'created_status': 'created',
            'failed_status': 'failed',
            'file_server_root': tempdir,
        },
    )
    # Disable archive creation
    snap_cre._create_archive = mock.Mock()
    snap_cre.create()
    snap_dir = snap_cre._tempdir

    try:
        _check_snapshot_top_level(snap_dir, mock_unlink, mock_zipfile)
        _check_snapshot_mgmt(snap_dir, snap_cre._client, mock_unlink,
                             mock_zipfile)
        _assert_tenants(snap_dir, snap_cre._tenant_clients, mock_unlink,
                        mock_zipfile)

        _assert_snapshot_status_update(snap_id, True, snap_cre._client)
    finally:
        shutil.rmtree(tempdir)
        shutil.rmtree(snap_dir)


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


def _check_zip_and_delete(paths, unlink, zipfile, base_dir, zip_idx=0):
    zip_writer = zipfile['zipfiles'][zip_idx].__enter__.return_value.write

    expected_zip_calls = [
        mock.call(path, path[len(base_dir) + 1:])
        for path in paths
    ]

    zip_writer.assert_has_calls(expected_zip_calls, any_order=True)
    unlink.assert_has_calls([
        mock.call(path)
        for path in paths
    ], any_order=True)


def _check_tenant_dir_in_zip(tenant_name, zipfile, base_dir):
    zip_writer = zipfile['zipfiles'][0].__enter__.return_value.write
    path = os.path.join(base_dir, 'tenants', tenant_name)
    expected_zip_calls = [
        mock.call(path, path[len(base_dir) + 1:]),
    ]
    zip_writer.assert_has_calls(expected_zip_calls, any_order=True)


def _check_snapshot_top_level(tempdir, unlink, zipfile):
    top_level_data = set(os.listdir(tempdir))
    assert top_level_data == {'mgmt', 'tenants', constants.METADATA_FILENAME}
    metadata_path = os.path.join(tempdir, constants.METADATA_FILENAME)
    with open(metadata_path) as md_handle:
        metadata = json.load(md_handle)
    assert metadata == {constants.M_VERSION: FAKE_MANAGER_VERSION}
    _check_zip_and_delete([metadata_path], unlink, zipfile, tempdir)


def _check_snapshot_mgmt(tempdir, client, unlink, zipfile):
    mgmt_base_dir = os.path.join(tempdir, 'mgmt')
    top_level_mgmt = set(os.listdir(mgmt_base_dir))
    entities = ['user_groups', 'tenants', 'users', 'permissions']
    assert top_level_mgmt == set(entities)
    for entity in entities:
        assert os.listdir(os.path.join(mgmt_base_dir, entity)) == ['0.json']
        file_path = os.path.join(mgmt_base_dir, entity, '0.json')
        _check_zip_and_delete([file_path], unlink, zipfile, tempdir)
        expected_content = MOCK_CLIENT_RESPONSES[None][entity]['list']
        with open(file_path) as entity_handle:
            content = json.load(entity_handle)
        assert content == expected_content
        client_group = getattr(client, entity)
        expected_kwargs = EXTRA_DUMP_KWARGS.get(entity, {})
        if entity in INCLUDES:
            expected_kwargs['_include'] = INCLUDES[entity]
        if entity in GET_DATA:
            expected_kwargs['_get_data'] = True
        client_group.list.assert_called_once_with(**expected_kwargs)


def _assert_tenants(tempdir, clients, unlink, zipfile):
    tenants = [tenant for tenant in MOCK_CLIENT_RESPONSES.keys()
               if tenant is not None]

    tenants_dir = os.path.join(tempdir, 'tenants')
    tenants_dir_content = set(os.listdir(tenants_dir))
    assert tenants_dir_content == set(tenants)

    for tenant in tenants:
        tenant_dir = os.path.join(tenants_dir, tenant)
        _check_tenant_dir_in_zip(tenant, zipfile, tempdir)

        for r_type, methods_data in MOCK_CLIENT_RESPONSES[tenant].items():
            if r_type == 'secrets':
                method = 'export'
            else:
                method = 'list'
            data = methods_data[method]
            if r_type == 'agents' or 'node' in r_type:
                dep_ids = [
                    dep['id']
                    for dep in MOCK_CLIENT_RESPONSES[tenant][
                       'deployments']['list']
                ]
                _check_deployment_entities(
                    r_type, data, dep_ids, tenant_dir, unlink, zipfile,
                )
                continue
            if r_type in ['events', 'tasks_graphs']:
                exc_ids = [
                    exc['id']
                    for exc in MOCK_CLIENT_RESPONSES[tenant][
                        'executions']['list']
                ]
                group_ids = [
                    group['id']
                    for group in MOCK_CLIENT_RESPONSES[tenant][
                        'execution_groups']['list']
                ]
                _check_exec_entities(
                    r_type, data, exc_ids, group_ids, tenant_dir,
                    unlink, zipfile,
                    operations=MOCK_CLIENT_RESPONSES[tenant][
                        'operations']['list'],
                )
                continue
            if r_type == 'operations':
                # The stored data on these is checked within tasks_graphs
                continue
            sub_dir = os.path.join(tenant_dir, f'{r_type}_archives')
            expected_files = []
            if r_type == 'plugins':
                plugin_files = [
                    os.path.join(sub_dir, entity['id'] + '.zip')
                    for entity in data
                ]
                # Make sure we add the plugin zip to the snapshot
                _check_zip_and_delete(plugin_files, unlink, zipfile,
                                      tempdir)
            elif r_type == 'blueprints':
                stored_blueprints = set(os.listdir(sub_dir))
                expected_blueprints = {blueprint['id'] + '.zip'
                                       for blueprint in data}
                expected_files = [
                    os.path.join(sub_dir, entity)
                    for entity in expected_blueprints
                ]
                assert stored_blueprints == expected_blueprints
            elif r_type == 'deployments':
                dep_workdirs = methods_data['get']
                stored_dep_workdirs = set(os.listdir(sub_dir))
                expected_dep_workdirs = set()
                for idx in range(len(dep_workdirs)):
                    if dep_workdirs[idx]['workdir_zip'] == EMPTY_B64_ZIP:
                        # We don't save empty workdirs.
                        continue
                    expected_dep_workdirs.add(data[idx]['id'] + '.b64zip')
                expected_files = [
                    os.path.join(sub_dir, entity)
                    for entity in expected_dep_workdirs
                ]
                assert stored_dep_workdirs == expected_dep_workdirs

            if expected_files:
                _check_zip_and_delete(expected_files, unlink, zipfile,
                                      tempdir)

            for group in range(0, ceil(len(data) / ENTITIES_PER_GROUP)):
                data_start = group * ENTITIES_PER_GROUP
                data_end = data_start + ENTITIES_PER_GROUP

                expected = []
                if r_type.endswith('_filters'):
                    for item in data[data_start:data_end]:
                        if item['is_system_filter']:
                            # We don't expect to copy system filters
                            continue
                        item = deepcopy(item)
                        item.pop('is_system_filter')
                        expected.append(item)
                else:
                    expected = data[data_start:data_end]

                _check_resource_type(r_type, group, expected, tenant_dir,
                                     unlink, zipfile)

        _check_tenant_calls(tenant, MOCK_CLIENT_RESPONSES[tenant],
                            clients[tenant], tenant_dir)


def _check_resource_type(r_type, group, expected, tenant_dir,
                         unlink, zipfile):
    resource_file = os.path.join(tenant_dir, r_type, f'{group}.json')
    with open(resource_file) as stored_handle:
        stored = json.load(stored_handle)
    assert stored == expected
    tempdir = os.path.dirname(os.path.dirname(tenant_dir))
    _check_zip_and_delete([resource_file], unlink, zipfile, tempdir)


def _check_deployment_entities(r_type, data, dep_ids, tenant_dir, unlink,
                               zipfile):
    entities_path = os.path.join(tenant_dir, r_type)
    stored_dep_entities = set(os.listdir(entities_path))
    expected_entities = {dep_id + '.json' for dep_id in dep_ids}
    assert stored_dep_entities == expected_entities
    _check_stored_dependents(entities_path, dep_ids, data)
    tempdir = os.path.dirname(os.path.dirname(tenant_dir))
    _check_zip_and_delete([
        os.path.join(entities_path, entity)
        for entity in stored_dep_entities
    ], unlink, zipfile, tempdir)


def _check_exec_entities(r_type, data, exc_ids, group_ids, tenant_dir,
                         unlink, zipfile, operations=None):
    if r_type == 'events':
        execs_path = os.path.join(tenant_dir, 'executions_events')
        groups_path = os.path.join(tenant_dir, 'execution_groups_events')

        stored_exec_events = set(os.listdir(execs_path))
        stored_group_events = set(os.listdir(groups_path))

        expected_exec_events = {exc_id + '.json' for exc_id in exc_ids}
        expected_group_events = {group_id + '.json' for group_id in group_ids}

        assert stored_exec_events == expected_exec_events
        assert stored_group_events == expected_group_events

        expected_files = [
            os.path.join(execs_path, entity)
            for entity in expected_exec_events
        ] + [
            os.path.join(groups_path, entity)
            for entity in expected_group_events
        ]

        _check_stored_dependents(execs_path, exc_ids, data)
        _check_stored_dependents(groups_path, group_ids, data)
    elif r_type == 'tasks_graphs':
        graphs_path = os.path.join(tenant_dir, r_type)

        stored_graphs = set(os.listdir(graphs_path))
        expected_graphs = {exc_id + '.json' for exc_id in exc_ids}

        assert stored_graphs == expected_graphs

        expected_files = [
            os.path.join(graphs_path, entity)
            for entity in expected_graphs
        ]

        _check_stored_dependents(graphs_path, exc_ids, data, operations)
    tempdir = os.path.dirname(os.path.dirname(tenant_dir))
    _check_zip_and_delete(expected_files, unlink, zipfile, tempdir)


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
            if command == 'download':
                dest = os.path.join(
                    tenant_dir, f'{entity_type}_archives', '{}.zip')
                kwargs = {}
                if entity_type == 'plugins':
                    kwargs = {'full_archive': True}
                expected_calls = {
                    _Call((entity['id'], dest.format(entity['id'])), kwargs,
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
