
import os

from nose.plugins.attrib import attr

from manager_rest.test import base_test
from .test_utils import generate_progress_func
from manager_rest.test.base_test import BaseServerTestCase
from cloudify_rest_client.exceptions import CloudifyClientError


@attr(client_min_version=2, client_max_version=base_test.LATEST_API_VERSION)
class SnapshotsTest(BaseServerTestCase):
    def test_create_snapshot_illegal_id(self):
        # try id with whitespace
        self.assertRaisesRegexp(CloudifyClientError,
                                'contains illegal characters',
                                self.client.snapshots.create,
                                'illegal id',
                                False,
                                False)
        # try id that starts with a number
        self.assertRaisesRegexp(CloudifyClientError,
                                'must begin with a letter',
                                self.client.snapshots.create,
                                '0',
                                False,
                                False)

    @attr(client_min_version=3,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_snapshot_upload_progress(self):
        tmp_file_path = self.create_wheel('wagon', '0.6.2')
        total_size = os.path.getsize(tmp_file_path)

        progress_func = generate_progress_func(
            total_size=total_size,
            assert_equal=self.assertEqual,
            assert_almost_equal=self.assertAlmostEqual)

        try:
            self.client.snapshots.upload(tmp_file_path,
                                         snapshot_id='0',
                                         progress_callback=progress_func)
        finally:
            self.quiet_delete(tmp_file_path)

    @attr(client_min_version=3,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_snapshot_download_progress(self):
        tmp_file_path = self.create_wheel('wagon', '0.6.2')
        total_size = os.path.getsize(tmp_file_path)
        tmp_local_path = '/tmp/snapshot.sn'

        try:
            self.client.snapshots.upload(tmp_file_path, '0')

            progress_func = generate_progress_func(
                total_size=total_size,
                assert_equal=self.assertEqual,
                assert_almost_equal=self.assertAlmostEqual)
            self.client.snapshots.download('0',
                                           tmp_local_path,
                                           progress_callback=progress_func)
        finally:
            self.quiet_delete(tmp_file_path)
            self.quiet_delete(tmp_local_path)
