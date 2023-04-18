import shutil
import tempfile
from queue import Queue
from unittest import mock

import pytest

from cloudify_system_workflows.tests.snapshots.mock_client import MockClient
from cloudify_system_workflows.snapshots.audit_listener import AuditLogListener
from cloudify_system_workflows.snapshots.snapshot_create import SnapshotCreate


FAKE_MANAGER_VERSION = 'THIS_MANAGER_VERSION'


@pytest.fixture(scope='function')
def auditlog_listener() -> AuditLogListener:
    queue = Queue()
    client = MockClient()
    listener = AuditLogListener(client.auditlog, queue)
    yield listener
    listener.stop()


def _get_rest_client():
    class AuditLogResponse:
        def __init__(self, content: list[bytes]):
            self.content = self.async_iterator(content)

        @staticmethod
        async def async_iterator(iterable):
            for i in iterable:
                yield i

    mock_client = mock.Mock()
    mock_client.auditlog.stream = mock.AsyncMock(
            side_effect=[
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
            ]
    )
    return mock_client


@pytest.fixture
def mock_get_client():
    with mock.patch(
        'cloudify_system_workflows.snapshots.snapshot_create'
        '.get_rest_client',
        side_effect=_get_rest_client,
    ):
        yield


@pytest.fixture()
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


@pytest.mark.skip(reason="causes some kind of OOM, presumably needs fixing "
                         "AuditLogResponse")
def test_reconnect(
        auditlog_listener,
        mock_ctx,
        mock_get_client,
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
    snap_cre._get_tenants = mock.Mock(return_value=['tenant1', 'tenant2'])
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
            'ref_identifier': {
                'id': '0',
                'manager_id': 'manager_id'
            },
            'operation': 'update',
            'creator_name': '',
            'execution_id': '',
            'created_at': '2023-04-05T09:27:57.927'
        }),
    ])

    shutil.rmtree(tempdir)
