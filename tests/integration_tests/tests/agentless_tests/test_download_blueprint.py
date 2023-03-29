########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import filecmp
import os
import pytest
import shutil
import subprocess
import tarfile
import uuid

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource
from integration_tests.tests.utils import wait_for_blueprint_upload

pytestmark = pytest.mark.group_deployments


class DownloadBlueprintTest(AgentlessTestCase):
    """
    CFY-196: Tests downloading of a previously uploaded blueprint.
    CFY-995: Added a large (50MB) file to the blueprint
    """

    def setUp(self):
        super(DownloadBlueprintTest, self).setUp()
        self.blueprint_id = 'b{0}'.format(uuid.uuid4())
        self.blueprint_file = '{0}.tar.gz'.format(self.blueprint_id)
        self.downloaded_archive_path = str(self.workdir / self.blueprint_file)
        self.downloaded_extracted_dir = str(self.workdir / 'extracted')
        self.test_blueprint_dir = str(self.workdir / 'blueprint')
        os.mkdir(self.test_blueprint_dir)
        self.large_file_location = os.path.join(self.test_blueprint_dir,
                                                'just_a_large_file.img')
        blueprint_src = resource('dsl/empty_blueprint.yaml')
        self.original_blueprint_file = os.path.join(self.test_blueprint_dir,
                                                    'blueprint.yaml')
        shutil.copy(blueprint_src, self.original_blueprint_file)
        self._create_file('50M', self.large_file_location)

    def test_download_blueprint(self):
        self.client.blueprints.upload(self.original_blueprint_file,
                                      self.blueprint_id)
        wait_for_blueprint_upload(self.blueprint_id, self.client)
        self.client.blueprints.download(
            self.blueprint_id,
            output_file=self.downloaded_archive_path)
        self.assertTrue(os.path.exists(self.downloaded_archive_path))
        self._extract_tar_file()
        downloaded_blueprint_file = os.path.join(
            self.downloaded_extracted_dir, 'blueprint/blueprint.yaml')
        self.assertTrue(os.path.exists(downloaded_blueprint_file))
        self.assertTrue(filecmp.cmp(self.original_blueprint_file,
                                    downloaded_blueprint_file))

    def _extract_tar_file(self):
        with tarfile.open(self.downloaded_archive_path) as tar:
            for item in tar:
                tar.extract(item, self.downloaded_extracted_dir)

    @staticmethod
    def _create_file(file_size, file_location):
        subprocess.run(['fallocate', '-l', file_size, file_location])
