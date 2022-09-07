import os

from mock import patch

from cloudify.snapshots import STATES
from cloudify_rest_client.exceptions import CloudifyClientError

from .test_utils import generate_progress_func
from manager_rest.test.base_test import BaseServerTestCase


class SnapshotsTest(BaseServerTestCase):
    def test_create_snapshot_illegal_id(self):
        # try id with whitespace
        self.assertRaisesRegex(CloudifyClientError,
                               'contains illegal characters',
                               self.client.snapshots.create,
                               'illegal id',
                               False,
                               False)
        # try id that starts with a number
        self.assertRaisesRegex(CloudifyClientError,
                               'must begin with a letter',
                               self.client.snapshots.create,
                               '0',
                               False,
                               False)

    def test_snapshot_upload_progress(self):
        tmp_file_path = os.path.join(self.tmpdir, 'bigfile')
        with open(tmp_file_path, 'w') as f:
            for _ in range(1000):
                f.write('abcdef')
        total_size = os.path.getsize(tmp_file_path)

        progress_func = generate_progress_func(total_size=total_size)

        try:
            self.client.snapshots.upload(tmp_file_path,
                                         snapshot_id='0',
                                         progress_callback=progress_func)
        finally:
            self.quiet_delete(tmp_file_path)

    def test_snapshot_download_progress(self):
        tmp_file_path = os.path.join(self.tmpdir, 'bigfile')
        with open(tmp_file_path, 'w') as f:
            for _ in range(1000):
                f.write('abcdef')
        total_size = os.path.getsize(tmp_file_path)
        tmp_local_path = '/tmp/snapshot.sn'

        try:
            self.client.snapshots.upload(tmp_file_path, '0')

            progress_func = generate_progress_func(total_size=total_size)
            self.client.snapshots.download('0',
                                           tmp_local_path,
                                           progress_callback=progress_func)
        finally:
            self.quiet_delete(tmp_file_path)
            self.quiet_delete(tmp_local_path)


class SnapshotStatusTest(BaseServerTestCase):
    def test_snapshot_status_reports_not_running(self):
        status = self.client.snapshots.get_status()
        self.assertIn('status', status)
        self.assertEqual(status['status'], STATES.NOT_RUNNING)

    def test_snapshot_status_reports_running(self):
        with patch('manager_rest.rest.resources_v3_1.snapshots'
                   '.is_system_in_snapshot_restore_process',
                   return_value=True):
            status = self.client.snapshots.get_status()
            self.assertIn('status', status)
            self.assertEqual(status['status'], STATES.RUNNING)
