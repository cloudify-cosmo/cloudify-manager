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


from testenv import TestCase
from testenv.utils import get_resource as resource
from testenv.utils import deploy_application as deploy
from testenv.utils import undeploy_application as undeploy


class TestUninstallDeployment(TestCase):

    def test_uninstall_application_single_node_no_host(self):
        dsl_path = resource("dsl/single_node_no_host.yaml")
        deployment, _ = deploy(dsl_path)
        deployment_id = deployment.id
        undeploy(deployment_id)

        states = self.get_plugin_data(
            plugin_name='testmockoperations',
            deployment_id=deployment_id
        )['state']
        node_id = states[0]['id']
        unreachable_call_order = self.get_plugin_data(
            plugin_name='testmockoperations',
            deployment_id=deployment_id
        )['unreachable_call_order']

        unreachable_called = is_unreachable_called(
            node_id,
            unreachable_call_order)
        self.assertTrue(unreachable_called)

        node_instance = self.client.node_instances.get(node_id)
        self.assertEqual('deleted', node_instance['state'])

    def test_uninstall_application_single_host_node(self):
        dsl_path = resource("dsl/basic.yaml")

        deployment, _ = deploy(dsl_path)
        deployment_id = deployment.id

        undeploy(deployment_id)

        machines = self.get_plugin_data(
            plugin_name='cloudmock',
            deployment_id=deployment_id
        )['machines']

        self.assertEquals(0, len(machines))

    def test_uninstall_with_dependency_order(self):
        dsl_path = resource(
            "dsl/uninstall_dependencies-order-with-three-nodes.yaml")
        deployment, _ = deploy(dsl_path)
        deployment_id = deployment.id
        undeploy(deployment_id)
        # Checking that uninstall wasn't called on the contained node
        states = self.get_plugin_data(
            plugin_name='testmockoperations',
            deployment_id=deployment_id
        )['state']
        node1_id = states[0]['id']
        node2_id = states[1]['id']
        node3_id = states[2]['id']

        unreachable_call_order = self.get_plugin_data(
            plugin_name='testmockoperations',
            deployment_id=deployment_id
        )['unreachable_call_order']
        self.assertEquals(3, len(unreachable_call_order))
        self.assertEquals(node3_id, unreachable_call_order[0]['id'])
        self.assertEquals(node2_id, unreachable_call_order[1]['id'])
        self.assertEquals(node1_id, unreachable_call_order[2]['id'])

        configurer_state = self.get_plugin_data(
            plugin_name='connection_configurer_mock',
            deployment_id=deployment_id
        )['state']
        self.assertEquals(2, len(configurer_state))
        self.assertTrue(
            configurer_state[0]['id'].startswith('contained_in_node2'))
        self.assertTrue(
            configurer_state[0]['related_id'].startswith('contained_in_node1'))
        self.assertTrue(
            configurer_state[1]['id'].startswith('containing_node'))
        self.assertTrue(
            configurer_state[1]['related_id'].startswith('contained_in_node1'))

    def test_stop_monitor_node_operation(self):
        dsl_path = resource(
            "dsl/hardcoded_operation_properties.yaml")
        deployment, _ = deploy(dsl_path)
        deployment_id = deployment.id
        undeploy(deployment_id)
        # test stop monitor invocations
        invocations = self.get_plugin_data(
            plugin_name='testmockoperations',
            deployment_id=deployment_id
        )['monitoring_operations_invocation']
        self.assertEqual(2, len(invocations))
        self.assertTrue('single_node' in invocations[0]['id'])
        self.assertEquals('start_monitor', invocations[0]['operation'])
        self.assertTrue('single_node' in invocations[1]['id'])
        self.assertEquals('stop_monitor', invocations[1]['operation'])

    def test_failed_uninstall_task(self):
        dsl_path = resource('dsl/basic_stop_error.yaml')
        deployment, _ = deploy(dsl_path)
        deployment_id = deployment.id
        undeploy(deployment_id)

        machines = self.get_plugin_data(
            plugin_name='cloudmock',
            deployment_id=deployment_id
        )['machines']

        self.assertEquals(0, len(machines))


def is_unreachable_called(node_id,
                          unreachable_call_order):
    return next((x for x in
                 unreachable_call_order if x['id'] == node_id), None)
