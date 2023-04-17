import shutil
import tempfile
from collections import namedtuple
from queue import Queue
from unittest import mock

import pytest

from cloudify_system_workflows.tests.snapshots.mock_client import MockClient
from cloudify_system_workflows.snapshots.audit_listener import AuditLogListener
from cloudify_system_workflows.snapshots.snapshot_create import SnapshotCreate


FAKE_MANAGER_VERSION = 'THIS_MANAGER_VERSION'


class AuditLogResponse:
    def __init__(self, content: list[bytes]):
        self.content = self.async_iterator(content)

    @staticmethod
    async def async_iterator(iterable):
        for i in iterable:
            yield i


DeploymentResponse = namedtuple('Deployment', 'id blueprint_id')


@pytest.fixture(scope='function')
def auditlog_listener() -> AuditLogListener:
    queue = Queue()
    client = MockClient()
    listener = AuditLogListener(client, queue)
    yield listener
    listener.stop()


def _get_rest_client(
        auditlog_stream_se=None,
        deployments_get_se=None,
):
    client = mock.Mock()
    if auditlog_stream_se:
        client.auditlog.stream = mock.AsyncMock(side_effect=auditlog_stream_se)
    if deployments_get_se:
        client.deployments.get = mock.Mock(side_effect=deployments_get_se)
    return client


@pytest.fixture
def mock_get_breaking_client(**_):
    with mock.patch(
        'cloudify_system_workflows.snapshots.snapshot_create.get_rest_client',
        side_effect=lambda **_: _get_rest_client(
            auditlog_stream_se=[
                AuditLogResponse([
                    b'{"id": "1192", "ref_table": "users", "ref_id": "0", '
                    b'"ref_identifier": {"username": "admin"}, '
                    b'"operation": "update", "creator_name": "", '
                    b'"execution_id": "", '
                    b'"created_at": "2023-04-05T09:27:57.926"}',
                ]),
                Exception('breaking connection'),
                AuditLogResponse([
                    b'{"id": "1193", "ref_table": "usage_collector", '
                    b'"ref_id": "0", "ref_identifier": {"id": "0", '
                    b'"manager_id": "manager_id"}, '
                    b'"operation": "update", "creator_name": "", '
                    b'"execution_id": "", '
                    b'"created_at": "2023-04-05T09:27:57.927"}',
                ]),
            ],
        ),
    ):
        yield


@pytest.fixture
def mock_get_standard_client(**_):
    with mock.patch(
        'cloudify_system_workflows.snapshots.snapshot_create.get_rest_client',
        side_effect=lambda **_: _get_rest_client(
            auditlog_stream_se=[
                AuditLogResponse([
                    b'{"id": "1292", "ref_table": "deployments", '
                    b'"ref_id": "1", "ref_identifier": {"id": "d1", '
                    b'"_tenant_id": "0", "tenant_name": "tenant1"}, '
                    b'"operation": "create", "creator_name": "admin", '
                    b'"execution_id": "", '
                    b'"created_at": "2023-04-05T10:27:57.926"}',
                ]),
                AuditLogResponse([
                    b'{"id": "1293", "ref_table": "blueprints", '
                    b'"ref_id": "2", "ref_identifier": {"id": "bp2", '
                    b'"_tenant_id": "0", "tenant_name": "tenant1"}, '
                    b'"operation": "create", "creator_name": "admin", '
                    b'"execution_id": "", '
                    b'"created_at": "2023-04-05T10:27:57.927"}',
                ]),
                AuditLogResponse([
                    b'{"id": "1294", "ref_table": "blueprints", '
                    b'"ref_id": "1", "ref_identifier": {"id": "bp1", '
                    b'"_tenant_id": "0", "tenant_name": "tenant1"}, '
                    b'"operation": "update", "creator_name": "admin", '
                    b'"execution_id": "", '
                    b'"created_at": "2023-04-05T10:27:57.928"}',
                ]),
                AuditLogResponse([
                    b'{"id": "1295", "ref_table": "deployments", '
                    b'"ref_id": "2", "ref_identifier": {"id": "d2", '
                    b'"_tenant_id": "0", "tenant_name": "tenant1"}, '
                    b'"operation": "create", "creator_name": "admin", '
                    b'"execution_id": "", '
                    b'"created_at": "2023-04-05T10:27:57.929"}',
                ]),
            ],
            deployments_get_se=[
                DeploymentResponse('d1', 'bp1'),
                DeploymentResponse('d2', 'bp2'),
            ],
        )
    ):
        yield


@pytest.fixture()
def mock_ctx():
    with mock.patch(
        'cloudify_system_workflows.snapshots.snapshot_create.ctx',
        new=mock.Mock(),
    ):
        yield


@pytest.fixture
def mock_get_manager_version():
    with mock.patch(
        'cloudify_system_workflows.snapshots.snapshot_create.utils'
        '.get_manager_version',
        return_value=FAKE_MANAGER_VERSION
    ):
        yield


def test_reconnect(
        auditlog_listener,
        mock_ctx,
        mock_get_breaking_client,
        mock_get_manager_version
):
    snap_id = 'testsnapshot'
    tempdir = tempfile.mkdtemp(prefix='snap-cre-auditlog-reconnect-test')
    snap_cre = SnapshotCreate(
        snapshot_id=snap_id,
        config={
            'created_status': 'created',
            'failed_status': 'failed',
            'file_server_root': tempdir,
        },
    )
    snap_cre._get_tenants = \
        mock.Mock(return_value={'tenant1': {}, 'tenant2': {}})
    snap_cre._blueprints_list = mock.Mock(return_value=[('tenant1', 'bp1')])
    snap_cre._plugins_list = mock.Mock(return_value=[])
    snap_cre._dump_management = mock.Mock()
    snap_cre._dump_composer = mock.Mock()
    snap_cre._dump_stage = mock.Mock()
    snap_cre._dump_tenant = mock.Mock()
    snap_cre._append_new_object_from_auditlog = mock.Mock()

    snap_cre.create(timeout=1)

    snap_cre._append_new_object_from_auditlog.assert_has_calls([
        mock.call({
            'id': '1192',
            'ref_table': 'users',
            'ref_id': '0',
            'ref_identifier': {'username': 'admin'},
            'operation': 'update',
            'creator_name': '', 'execution_id': '',
            'created_at': '2023-04-05T09:27:57.926'
        }),
        mock.call({
            'id': '1193',
            'ref_table': 'usage_collector',
            'ref_id': '0',
            'ref_identifier': {'id': '0', 'manager_id': 'manager_id'},
            'operation': 'update',
            'creator_name': '',
            'execution_id': '',
            'created_at': '2023-04-05T09:27:57.927'
        }),
    ])

    shutil.rmtree(tempdir)


def test_dont_append_new_blueprints(
        auditlog_listener,
        mock_ctx,
        mock_get_standard_client,
        mock_get_manager_version
):
    snap_id = 'testsnapshot'
    tempdir = tempfile.mkdtemp(prefix='snap-cre-auditlog-no-new-bps-test')
    snap_cre = SnapshotCreate(
        snapshot_id=snap_id,
        config={
            'created_status': 'created',
            'failed_status': 'failed',
            'file_server_root': tempdir,
        },
    )
    snap_cre._get_tenants = \
        mock.Mock(return_value={'tenant1': {}, 'tenant2': {}})
    snap_cre._blueprints_list = mock.Mock(return_value=[('tenant1', 'bp1')])

    snap_cre._plugins_list = mock.Mock(return_value=[])
    snap_cre._dump_management = mock.Mock()
    snap_cre._dump_composer = mock.Mock()
    snap_cre._dump_stage = mock.Mock()
    snap_cre._dump_tenant = mock.Mock()
    snap_cre._append_new_object_from_auditlog = mock.Mock()

    snap_cre.create(timeout=1)

    snap_cre._append_new_object_from_auditlog.assert_has_calls([
        mock.call({
            'id': '1292',
            'ref_table': 'deployments',
            'ref_id': '1',
            'ref_identifier': {
                'id': 'd1',
                '_tenant_id': '0',
                'tenant_name': 'tenant1'
            },
            'operation': 'create',
            'creator_name': 'admin',
            'execution_id': '',
            'created_at': '2023-04-05T10:27:57.926'
        }),
        mock.call({
            'id': '1294',
            'ref_table': 'blueprints',
            'ref_id': '1',
            'ref_identifier': {
                'id': 'bp1',
                '_tenant_id': '0',
                'tenant_name': 'tenant1'
            },
            'operation': 'update',
            'creator_name': 'admin',
            'execution_id': '',
            'created_at': '2023-04-05T10:27:57.928'
        }),
    ])

    shutil.rmtree(tempdir)
