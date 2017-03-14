########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

from integration_tests import AgentTestCase
from integration_tests.tests.utils import get_resource as resource


class PluginWorkdirTest(AgentTestCase):

    def test_plugin_workdir(self):
        filename = 'test_plugin_workdir.txt'
        host_content = 'HOST_CONTENT'
        central_content = 'CENTRAL_CONTENT'
        dsl_path = resource("dsl/plugin_workdir.yaml")
        deployment, _ = self.deploy_application(
                dsl_path,
                inputs={
                    'filename': filename,
                    'host_content': host_content,
                    'central_content': central_content
                    })
        central_file = os.path.join(
            '/opt/mgmtworker/work', 'deployments', 'default_tenant',
            deployment.id, 'plugins', 'testmockoperations', filename)
        host_instance_id = self.client.node_instances.list(
            deployment_id=deployment.id,
            node_id='host')[0].id
        host_file = os.path.join(
            '/root', host_instance_id, 'work/plugins/testmockoperations',
            filename)
        out = self.read_manager_file(central_file)
        self.assertEqual(central_content, out)
        out = self.read_host_file(host_file,
                                  deployment_id=deployment.id,
                                  node_id='host')
        self.assertEqual(host_content, out)
