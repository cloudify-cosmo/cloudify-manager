"""Snapshot related test cases."""

import os
import shutil
import subprocess
import unittest
import tempfile

from cloudify_system_workflows.snapshot import make_zip64_archive


class MakeZip64Test(unittest.TestCase):

    """Ensure huge zip files can be created."""

    def setUp(self):
        """Create temporary directory with long files."""
        base_dir = tempfile.mkdtemp(prefix='make_zip_test_')
        data_dir = os.path.join(base_dir, 'data')
        os.mkdir(data_dir)

        dir_count = 5
        file_count = 5

        for dir_number in range(dir_count):
            directory = os.path.join(data_dir, 'dir_{}'.format(dir_number))
            os.mkdir(directory)

            for file_number in range(file_count):
                path = os.path.join(directory, 'file_{}'.format(file_number))
                self._create_random_file(path)

        self.base_dir = base_dir
        self.data_dir = data_dir

        self.addCleanup(shutil.rmtree, base_dir)

    def _create_random_file(
            self, filename, chunk_size=2**20, chunk_count=100):
        """Create random file efficiently

        The size of the random file (100 MB by default) can be controlled by
        setting `chunk_size` (1 MB by default) and `chunk_count` (100 by
        default).

        This functionality could be implemented with python code, but it won't
        be as fast as the `dd` binary.

        """
        subprocess.call([
            'dd',
            'if=/dev/urandom',
            'of={}'.format(filename),
            'bs={}'.format(chunk_size),
            'count={}'.format(chunk_count),
        ])

    def test_huge_file(self):
        """Size should not be be a problem with zip64 enabled."""
        zip_filename = os.path.join(self.base_dir, 'snapshot.zip')
        make_zip64_archive(zip_filename, self.data_dir)

        # When zip64 extensions are not enabled, zip fails around 2.1 GB,
        # so if the file size is greater than 2.2 GB it should be
        self.assertGreater(
            os.path.getsize(zip_filename),
            2.2 * 2**30,  # 2.2GB
        )
