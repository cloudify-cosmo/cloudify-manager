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

from integration_tests import AgentTestWithPlugins
from integration_tests.tests.utils import get_resource as resource


class BaseExistingVMTest(AgentTestWithPlugins):
    def setUp(self):
        super(BaseExistingVMTest, self).setUp()
        self.setup_deployment_id = str(uuid.uuid4())
        self.setup_node_id = 'setup_host'
        dsl_path = resource("dsl/existing-vm-setup.yaml")
        self.deploy_application(dsl_path,
                                deployment_id=self.setup_deployment_id)

    def _get_ssh_key_content(self):
        ssh_key_path = self.get_host_key_path(
            node_id=self.setup_node_id,
            deployment_id=self.setup_deployment_id
        )
        return self.read_manager_file(ssh_key_path)

    def _get_host_ip(self):
        return self.get_host_ip(
            node_id=self.setup_node_id,
            deployment_id=self.setup_deployment_id
        )


class ExistingVMTest(BaseExistingVMTest):
    def test_existing_vm(self):
        dsl_path = resource("dsl/existing-vm.yaml")
        inputs = {
            'ip': self._get_host_ip(),
            'agent_key': self.get_host_key_path(
                node_id=self.setup_node_id,
                deployment_id=self.setup_deployment_id),
        }
        deployment, _ = self.deploy_application(dsl_path, inputs=inputs)
        plugin_data = self.get_plugin_data('testmockoperations', deployment.id)
        self.assertEqual(1, len(plugin_data['mock_operation_invocation']))


class SecretAgentKeyTest(BaseExistingVMTest):
    def test_secret_ssh_key_in_existing_vm(self):
        ssh_key_content = self._get_ssh_key_content()
        self.client.secrets.create('agent_key', ssh_key_content)
        dsl_path = resource("dsl/secret-ssh-key-in-existing-vm.yaml")
        inputs = {'ip': self._get_host_ip()}
        deployment, _ = self.deploy_application(dsl_path, inputs=inputs)
        plugin_data = self.get_plugin_data('testmockoperations', deployment.id)
        self.assertEqual(1, len(plugin_data['mock_operation_invocation']))
