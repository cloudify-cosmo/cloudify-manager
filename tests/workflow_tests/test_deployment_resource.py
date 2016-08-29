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

import os
import tempfile
import uuid

import sh

from testenv import TestCase
from testenv.utils import get_resource as resource
from testenv.utils import deploy_application as deploy


RESOURCE_PATH = 'resources/resource.txt'
RESOURCE_CONTENT = 'this is a deployment resource'


class DeploymentResourceTest(TestCase):

    def get_and_download_deployment_resource_test(self):
        blueprint_id = str(uuid.uuid4())
        deployment_id = blueprint_id
        blueprint_path = resource('dsl/deployment_resource.yaml')
        deployment_folder_on_manager = \
            '/opt/manager/resources/deployments/{0}'.format(deployment_id)
        full_resource_path = os.path.join(deployment_folder_on_manager,
                                          RESOURCE_PATH)
        self.execute_on_manager('mkdir -p {0}/resources'.format(
            deployment_folder_on_manager))

        with tempfile.NamedTemporaryFile() as f:
            f.write(RESOURCE_CONTENT)
            f.flush()
            self.copy_file_to_manager(source=f.name,
                                      target=full_resource_path)
            self.execute_on_manager('chmod +r {0}'.format(full_resource_path))

        deployment, _ = deploy(
            blueprint_path,
            blueprint_id=blueprint_id,
            deployment_id=deployment_id,
            inputs={'resource_path': RESOURCE_PATH})

        plugin_data = self.get_plugin_data(plugin_name='testmockoperations',
                                           deployment_id=deployment.id)

        get_resource_content = plugin_data['get_resource']
        download_resource_path = plugin_data['download_resource']

        self.assertEquals(RESOURCE_CONTENT, get_resource_content)
        self.assertEquals(RESOURCE_CONTENT,
                          self.read_manager_file(download_resource_path))

        self.client.deployments.delete(deployment_id, ignore_live_nodes=True)
        self.assertRaises(
            sh.ErrorReturnCode,
            self.execute_on_manager,
            'test -d {0}'.format(deployment_folder_on_manager))
