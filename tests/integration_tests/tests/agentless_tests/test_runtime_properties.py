########
# Copyright (c) 2013-2019 Cloudify Platform Ltd. All rights reserved
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

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource


class TestRuntimeProperties(AgentlessTestCase):

    def test_update_runtime_properties(self):
        # testing set property
        node_instance_id, _, dep_id = self._deploy_set_property_application()

        # testing delete property
        self.undeploy_application(dep_id)
        node_runtime_props = self.client.node_instances.get(
            node_instance_id).runtime_properties
        self.assertNotIn('property_name', node_runtime_props)

    def test_no_update_runtime_properties(self):
        dsl_path = resource("dsl/update_node_state.yaml")
        # simply expecting workflow execution to succeed
        self.deploy_application(dsl_path)

    def test_update_runtime_properties_cli(self):
        """Basic end to end test for update-runtime cli command.
        Most of the tests are in the cli repo.
        """
        instance_id, runtime_props, _ = self._deploy_set_property_application()
        self.assertNotIn('test_key', runtime_props)

        self.cfy(['node-instances', 'update-runtime', instance_id, '-p',
                  {'test_key': 'test_value'}])
        runtime_props = self.client.node_instances.get(instance_id) \
            .runtime_properties
        self.assertEqual('test_value', runtime_props['test_key'])

    def test_delete_runtime_properties_cli(self):
        """Basic end to end test for delete-runtime cli command.
        Most of the tests are in the cli repo.
        """
        node_instance_id, _, _ = self._deploy_set_property_application()
        self.cfy(['node-instances', 'delete-runtime', node_instance_id, '-p',
                  'property_name'])
        node_runtime_props = self.client.node_instances.get(
            node_instance_id).runtime_properties
        self.assertNotIn('property_name', node_runtime_props)

    def _deploy_set_property_application(self):
        dsl_path = resource("dsl/set_property.yaml")
        deployment, _ = self.deploy_application(dsl_path)
        node_instance_id = self.client.node_instances.list(
            deployment_id=deployment.id)[0].id
        node_runtime_props = self.client.node_instances.get(
            node_instance_id).runtime_properties
        self.assertEqual('property_value', node_runtime_props['property_name'])
        return node_instance_id, node_runtime_props, deployment.id
