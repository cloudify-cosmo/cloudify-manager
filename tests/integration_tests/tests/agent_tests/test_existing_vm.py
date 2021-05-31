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
import pytest
from os.path import join

from integration_tests import AgentTestWithPlugins
from integration_tests.tests.utils import get_resource as resource

pytestmark = pytest.mark.group_plugins


class BaseExistingVMTest(AgentTestWithPlugins):
    def setUp(self):
        super(BaseExistingVMTest, self).setUp()
        self.setup_deployment_id = 'd{0}'.format(uuid.uuid4())
        self.setup_node_id = 'setup_host'
        dsl_path = resource("dsl/agent_tests/existing-vm-setup.yaml")
        self.deploy_application(dsl_path,
                                deployment_id=self.setup_deployment_id)


@pytest.mark.usefixtures('testmockoperations_plugin')
class ExistingVMTest(BaseExistingVMTest):
    def test_existing_vm(self):
        dsl_path = resource("dsl/agent_tests/existing-vm.yaml")
        self.deploy_application(dsl_path)
        plugin_ops_instance = [i for i in self.client.node_instances.list()
                               if i.node_id == 'middle'][0]
        plugin_data = plugin_ops_instance['runtime_properties']
        self.assertEqual(1, len(plugin_data['mock_operation_invocation']))


class HostPluginTest(BaseExistingVMTest):
    BLUEPRINTS = 'dsl/agent_tests/plugin-requires-old-package-blueprint'

    def test_source_plugin_requires_old_package(self):
        self._test_host_plugin_requires_old_package(
            join(self.BLUEPRINTS, 'source_plugin_blueprint.yaml')
        )

    def _test_host_plugin_requires_old_package(self, blueprint_path):
        dsl_path = resource(blueprint_path)
        deployment, _ = self.deploy_application(dsl_path)
        self.undeploy_application(deployment.id)
