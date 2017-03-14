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
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import uuid

from integration_tests import AgentTestCase
from integration_tests.tests.utils import get_resource as resource


class SecretAgentKeyTest(AgentTestCase):
    def setUp(self):
        super(SecretAgentKeyTest, self).setUp()
        self.setup_deployment_id = str(uuid.uuid4())
        dsl_path = resource("dsl/existing-vm-setup.yaml")
        self.deploy_application(dsl_path,
                                deployment_id=self.setup_deployment_id)

    def _get_ssh_key_content(self):
        ssh_key_path = self.get_host_key_path(
            node_id='setup_host',
            deployment_id=self.setup_deployment_id
        )
        return self.read_manager_file(ssh_key_path)

    def test_secret_ssh_key_in_existing_vm(self):
        ssh_key_content = self._get_ssh_key_content()
        self.client.secrets.create('agent_key', ssh_key_content)
        dsl_path = resource("dsl/secret-ssh-key-in-existing-vm.yaml")
        host_ip = self.get_host_ip(
            node_id='setup_host',
            deployment_id=self.setup_deployment_id
        )
        inputs = {'ip': host_ip}
        deployment, _ = self.deploy_application(dsl_path, inputs=inputs)

        invocations = self.get_plugin_data(
            plugin_name='testmockoperations',
            deployment_id=deployment.id)['mock_operation_invocation']

        self.assertEqual(1, len(invocations))
