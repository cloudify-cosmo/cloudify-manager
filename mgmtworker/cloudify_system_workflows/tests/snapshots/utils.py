import json
import pathlib
import shutil
import tempfile
import uuid
import zipfile
from collections import defaultdict, namedtuple
from contextlib import contextmanager
from typing import Type
from unittest import mock

from cloudify import constants
from cloudify.mocks import MockContext
from cloudify_rest_client import CloudifyClient
from cloudify_rest_client.responses import ListResponse
from cloudify_system_workflows.snapshots.snapshot_create import SnapshotCreate

FAKE_MANAGER_VERSION = 'THIS_MANAGER_VERSION'
FAKE_MGMTWORKER_TOKEN = 'FAKE_TOKEN'
FAKE_EXECUTION_ID = 'fake-snapshot-create-execution-id'

EMPTY_TENANTS_LIST_SE = [
    ListResponse(
        items=[],
        metadata={'pagination': {'offset': 0, 'size': 0, 'total': 0}}
    )
]
ONE_TENANTS_LIST_SE = [
    ListResponse(
        items=[{'name': 'tenant1'}],
        metadata={'pagination': {'offset': 0, 'size': 1, 'total': 1}}
    ),
]
TWO_TENANTS_LIST_SE = [
    ListResponse(
        items=[{'name': 'tenant1'}, {'name': 'tenant2'}],
        metadata={'pagination': {'offset': 0, 'size': 2, 'total': 2}}
    ),
]
ONE_BLUEPRINT_LIST_SE = [
    ListResponse(
            items=[{'id': 'bp1', 'tenant_name': 'tenant1'}],
            metadata={'pagination': {'offset': 0, 'size': 1, 'total': 1}}
    )
]
TWO_BLUEPRINTS_LIST_SE = [
    ListResponse(
        items=[
            {'id': 'bp1', 'tenant_name': 'tenant1'},
            {'id': 'bp2', 'tenant_name': 'tenant1'}
        ],
        metadata={'pagination': {'offset': 0, 'size': 2, 'total': 2}}
    )
]


class MockHTTPClient(CloudifyClient.client_class):
    """This is a carbon-copy of cloudify_rest_client.tests.MockHTTPClient
     which is not shipped as part of cloudify-common."""

    def __init__(self, *args, **kwargs):
        super(MockHTTPClient, self).__init__(*args, **kwargs)
        self._do_request = mock.Mock()


class MockClient(CloudifyClient):
    """This is a carbon-copy of cloudify_rest_client.tests.MockClient which
     is not shipped as part of cloudify-common."""
    client_class = MockHTTPClient

    def __init__(self, **kwargs):
        params = {
            'host': '192.0.2.4',
        }
        params.update(kwargs)
        super(MockClient, self).__init__(**params)
        # Default to make calls have a chance of working
        self.mock_do_request.return_value = {}

    @property
    def mock_do_request(self):
        return self._client._do_request

    def assert_last_mock_call(self, endpoint, data=None, params=None,
                              expected_status_code=200, stream=False,
                              expected_method='get'):
        if not params:
            params = {}

        _, kwargs = self.mock_do_request.call_args_list[-1]

        called_endpoint = kwargs['request_url'].rpartition('v3.1')[2]
        assert endpoint == called_endpoint

        assert data == kwargs['body']
        assert params == kwargs['params']
        assert expected_status_code == kwargs['expected_status_code']
        assert stream == kwargs['stream']

        assert expected_method == kwargs['requests_method'].__name__

    @property
    def last_mock_call_headers(self):
        return self.mock_do_request.call_args_list[-1][1]['headers']

    def check_last_auth_headers(self, auth=None, token=None):
        expected = {
            constants.CLOUDIFY_EXECUTION_TOKEN_HEADER: None,
            constants.CLOUDIFY_AUTHENTICATION_HEADER: auth,
            constants.CLOUDIFY_TOKEN_AUTHENTICATION_HEADER: token,
        }

        # We don't just do a set because content-type (and other headers) may
        # be on valid requests
        for header in expected:
            if expected[header] is not None:
                assert self.last_mock_call_headers[header] == expected[header]
            else:
                assert header not in self.last_mock_call_headers


class AuditLogResponse:
    def __init__(self, elements: list[dict]):
        content_iterable = []
        for element in elements:
            content_iterable.append(json.dumps(element).encode('utf-8'))
        self.content = self.async_iterator(content_iterable)

    @staticmethod
    async def async_iterator(iterable):
        for i in iterable:
            yield i


DeploymentResponse = namedtuple('Deployment', 'id blueprint_id')
ExecutionResponse = namedtuple('Execution', 'id deployment_id')
ExecutionGroupResponse = namedtuple('ExecutionGroup', 'id deployment_group_id')


def get_mocked_client(
        side_effects: list[tuple[Type[mock.Mock], tuple, list]]
):
    client = mock.Mock()
    for _mock, attrs, side_effect in side_effects:
        # Set up mock with a side_effect.  E.g. for _mock = mock.AsyncMock and
        # attrs = ('x', 'y', 'z'), the assignment is going to be like:
        # client.x.y.z = mock.AsyncMock(side_effect=side_effect)
        obj = client
        for attr in attrs[:-1]:
            obj = getattr(obj, attr)
        if isinstance(side_effect, list):
            setattr(obj, attrs[-1], _mock(side_effect=side_effect))
        else:
            setattr(obj, attrs[-1], _mock(return_value=side_effect))
    return client


def get_mocked_ui_client(
        side_effects: list[tuple[tuple, list]]
):
    return get_mocked_client([
        (mock.Mock, attrs, side_effect)
        for attrs, side_effect in side_effects
    ])


@contextmanager
def prepare_snapshot_create_with_mocks(
        snapshot_id: str,
        rest_mocks: list[tuple[Type[mock.Mock], tuple, list]] | None = None,
        composer_mocks: list[tuple[tuple, list]] | None = None,
        stage_mocks: list[tuple[tuple, list]] | None = None,
        **kwargs
):
    with mock.patch(
        'cloudify_system_workflows.snapshots.snapshot_create.ctx',
        new=MockContext({
            'execution_id': FAKE_EXECUTION_ID,
            'logger': mock.Mock(),
        }),
    ):
        with mock.patch(
            'cloudify_system_workflows.snapshots.snapshot_create'
            '.get_manager_version',
            return_value=FAKE_MANAGER_VERSION
        ):
            with mock.patch(
                'cloudify_system_workflows.snapshots.ui_clients'
                '.get_admin_api_token',
                return_value=FAKE_MGMTWORKER_TOKEN
            ):
                with mock.patch(
                    'cloudify_system_workflows.snapshots'
                    '.snapshot_create.get_composer_client',
                    side_effect=lambda **_:
                        get_mocked_ui_client(composer_mocks or [])
                ):
                    with mock.patch(
                        'cloudify_system_workflows.snapshots'
                        '.snapshot_create.get_stage_client',
                        side_effect=lambda **_:
                            get_mocked_ui_client(stage_mocks or [])
                    ):
                        with mock.patch(
                            'cloudify_system_workflows.snapshots'
                            '.snapshot_create.get_rest_client',
                            side_effect=lambda **_:
                                get_mocked_client(rest_mocks)
                        ):
                            temp_dir = tempfile.mkdtemp(suffix=snapshot_id)
                            snapshot_create = SnapshotCreate(
                                snapshot_id=snapshot_id,
                                config={
                                    'created_status': 'created',
                                    'failed_status': 'failed',
                                    'file_server_root': temp_dir,
                                },
                                **kwargs,
                            )
                            yield snapshot_create
                            shutil.rmtree(snapshot_create._temp_dir,
                                          ignore_errors=True)
                            shutil.rmtree(temp_dir, ignore_errors=True)


def load_snapshot_to_dict(
        snapshot_file_name: str,
        in_path: str | None = None
):
    result = {}
    with zipfile.ZipFile(snapshot_file_name, 'r') as zip_file:
        files = [
            zi.filename for zi in zip_file.filelist
            if (not in_path or (in_path and zi.filename.startswith(in_path)))
            and zi.filename.endswith('.json')
        ]
        for file_name in sorted(files):
            if file_name == 'metadata.json':
                result['metadata'] = json.loads(zip_file.read(file_name))
            else:
                _snapshot_part_store(
                        result,
                        pathlib.Path(file_name).parts[:-1],
                        json.loads(zip_file.read(file_name))
                )
    return result


def _snapshot_part_store(data: dict, keys: tuple[str], content):
    d = data
    for key in keys[:-1]:
        if key not in d:
            d[key] = {}
        d = d[key]
    last_key = keys[-1]
    if last_key not in d:
        d[last_key] = defaultdict(
                lambda: {'items': {}, 'latest_timestamp': None}
        )
    content_key = (
        content.get('type'),
        content.get('source'),
        content.get('source_id'),
    )
    d[last_key][content_key]['items'].update({
        item.get('id') or item.get('_storage_id') or uuid.uuid4(): item
        for item in content['items']
    })
    d[last_key][content_key]['latest_timestamp'] =\
        content.get('latest_timestamp')
    return data
