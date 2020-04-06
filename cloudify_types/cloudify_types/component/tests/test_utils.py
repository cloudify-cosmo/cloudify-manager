# Copyright (c) 2017-2019 Cloudify Platform Ltd. All rights reserved
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

import os
import tempfile

from cloudify.exceptions import NonRecoverableError
from cloudify_rest_client.exceptions import CloudifyClientError

from cloudify_types.component import utils
from .base_test_suite import ComponentTestBase


class TestUtils(ComponentTestBase):

    @staticmethod
    def generate_temp_file():
        fd, destination = tempfile.mkstemp()
        os.close(fd)
        return destination

    @staticmethod
    def cleaning_up_files(files_paths):
        for path in files_paths:
            os.remove(path)

    def test_zip_files(self):
        test_file = self.generate_temp_file()
        zip_file = utils.zip_files([test_file])
        self.assertTrue(zip_file)
        self.cleaning_up_files([zip_file, test_file])

    def test_get_local_path_local(self):
        test_file = self.generate_temp_file()
        copy_file = utils.get_local_path(test_file, create_temp=True)
        self.assertTrue(copy_file)
        self.cleaning_up_files([copy_file, test_file])

    def test_get_local_path_https(self):
        copy_file = utils.get_local_path(
            "http://www.getcloudify.org/spec/cloudify/4.5/types.yaml",
            create_temp=True)
        self.assertTrue(copy_file)
        self.cleaning_up_files([copy_file])

    def test_blueprint_id_exists_no_blueprint(self):
        output = utils.blueprint_id_exists(self.cfy_mock_client, 'blu_name')
        self.assertFalse(output)

    def test_blueprint_id_exists_with_existing_blueprint(self):
        blueprint_name = 'blu_name'
        self.cfy_mock_client.blueprints.set_existing_objects([1])

        output = utils.blueprint_id_exists(self.cfy_mock_client,
                                           blueprint_name)
        self.assertTrue(output)

    def test_deployment_id_exists_no_deployment(self):
        output = utils.deployment_id_exists(self.cfy_mock_client, 'dep_name')
        self.assertFalse(output)

    def test_deployment_id_exists_with_existing_deployment(self):
        self.cfy_mock_client.deployments.set_existing_objects([1])
        self.assertTrue(utils.deployment_id_exists(self.cfy_mock_client,
                                                   'test'))

    def test_find_blueprint_handle_client_error(self):

        def mock_return(*_, **__):
            raise CloudifyClientError('Mistake')

        self.cfy_mock_client.blueprints.list = mock_return
        with self.assertRaisesRegexp(
                NonRecoverableError, 'Blueprint search failed'):
            utils.blueprint_id_exists(self.cfy_mock_client, 'blu_name')

    def test_find_deployment_handle_client_error(self):

        def mock_return(*_, **__):
            raise CloudifyClientError('Mistake')

        self.cfy_mock_client.deployments.list = mock_return
        with self.assertRaisesRegexp(
                NonRecoverableError, 'Deployment search failed'):
            utils.deployment_id_exists(self.cfy_mock_client, 'dep_name')
