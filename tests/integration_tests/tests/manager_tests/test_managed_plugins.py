########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import os
import uuid
import filecmp
import tarfile
import tempfile

import wagon

from integration_tests import ManagerTestCase
from integration_tests.tests.utils import get_resource as resource

TEST_PACKAGE_NAME = 'mock-wagon-plugin'


class DownloadInstallPluginTest(ManagerTestCase):

    def setUp(self):
        super(DownloadInstallPluginTest, self).setUp()
        self.run_manager()
        self.wagon_path = self._create_test_wagon()
        self.downloaded_archive_path = os.path.join(
            self.workdir, os.path.basename(self.wagon_path))
        self.plugin = self.client.plugins.upload(self.wagon_path)

    def test_install_and_download_managed_plugin(self):
        # verify plugin was indeed properly installed
        self._verify_plugin_can_be_used_in_blueprint()

        # check download
        self.cfy.plugins.download(self.plugin.id,
                                  output_path=self.downloaded_archive_path)
        self.assertTrue(os.path.exists(self.downloaded_archive_path))

        # assert plugin metadata integrity
        package_json = self._extract_package_json(self.wagon_path)
        new_package_json = self._extract_package_json(
            self.downloaded_archive_path)
        self.assertTrue(filecmp.cmp(package_json, new_package_json))

    def test_create_snapshot_with_plugin(self):
        snapshot_id = str(uuid.uuid4())
        execution = self.client.snapshots.create(snapshot_id=snapshot_id,
                                                 include_metrics=False,
                                                 include_credentials=False)
        self.wait_for_execution_to_end(execution, timeout_seconds=1000)
        self.client.plugins.delete(self.plugin.id)
        execution = self.client.snapshots.restore(snapshot_id)
        self.wait_for_execution_to_end(execution, timeout_seconds=1000)

        self._verify_plugin_can_be_used_in_blueprint()

    def _create_test_wagon(self):
        source_dir = resource('plugins/{0}'.format(TEST_PACKAGE_NAME))
        target_dir = tempfile.mkdtemp(dir=self.workdir)
        return wagon.create(
            source=source_dir,
            archive_destination_dir=target_dir,
            force=True,
            archive_format='tar.gz')

    def _verify_plugin_can_be_used_in_blueprint(self):
        blueprint_path = resource('dsl/managed_plugins.yaml')
        test_input_value = 'MY_TEST_INPUT'
        inputs = {'test_input': test_input_value}
        deployment, _ = self.deploy_application(blueprint_path, inputs=inputs)
        outputs = self.client.deployments.outputs.get(deployment.id)
        self.assertEqual(outputs.outputs['test_output'], test_input_value)

    def _extract_package_json(self, tar_location):
        tar = tarfile.open(tar_location)
        member = tar.getmember('{0}/package.json'.format(TEST_PACKAGE_NAME))
        member.name = os.path.basename(member.name)
        dest = tempfile.mkdtemp(dir=self.workdir)
        tar.extract(member, dest)
        return '{0}/{1}'.format(dest, os.path.basename(member.name))
