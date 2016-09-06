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
from integration_tests.utils import get_resource as resource
from integration_tests.utils import deploy_application as deploy


class ExistingVMTest(AgentTestCase):

    def setUp(self):
        super(ExistingVMTest, self).setUp()
        self.setup_deployment_id = str(uuid.uuid4())
        dsl_path = resource("dsl/existing-vm-setup.yaml")
        deploy(dsl_path, deployment_id=self.setup_deployment_id)

    def test_existing_vm(self):
        dsl_path = resource("dsl/existing-vm.yaml")
        deployment, _ = deploy(dsl_path, inputs={
            'ip': self.get_host_ip(
                node_id='setup_host',
                deployment_id=self.setup_deployment_id),
            'agent_key': self.get_host_key_path(
                node_id='setup_host',
                deployment_id=self.setup_deployment_id),
        })

        invocations = self.get_plugin_data(
            plugin_name='testmockoperations',
            deployment_id=deployment.id)['mock_operation_invocation']

        self.assertEqual(1, len(invocations))
