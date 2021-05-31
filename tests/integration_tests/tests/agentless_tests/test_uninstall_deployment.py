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

import pytest

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource

pytestmark = pytest.mark.group_deployments


@pytest.mark.usefixtures('testmockoperations_plugin')
@pytest.mark.usefixtures('cloudmock_plugin')
class TestUninstallDeployment(AgentlessTestCase):

    def test_uninstall_application_single_node_no_host(self):
        dsl_path = resource("dsl/single_node_no_host.yaml")
        deployment, _ = self.deploy_application(dsl_path)
        deployment_id = deployment.id
        self.undeploy_application(deployment_id)

        node_id = self.client.node_instances.list(
            deployment_id=deployment_id)[0].id
        node_instance = self.client.node_instances.get(node_id)
        unreachable_call_order = node_instance.runtime_properties[
            'unreachable_call_order'
        ]

        unreachable_called = is_unreachable_called(
            node_id,
            unreachable_call_order)
        self.assertTrue(unreachable_called)

        self.assertEqual('deleted', node_instance['state'])

    def test_uninstall_application_single_host_node(self):
        dsl_path = resource("dsl/basic.yaml")

        deployment, _ = self.deploy_application(dsl_path)
        deployment_id = deployment.id

        self.undeploy_application(deployment_id)
        node_id = self.client.node_instances.list(
            deployment_id=deployment_id)[0].id
        node_instance = self.client.node_instances.get(node_id)
        machines = node_instance.runtime_properties[
            'machines'
        ]
        self.assertEqual(0, len(machines))

    def test_uninstall_with_dependency_order(self):
        dsl_path = resource(
            "dsl/uninstall_dependencies-order-with-three-nodes.yaml")
        deployment, _ = self.deploy_application(dsl_path)
        deployment_id = deployment.id
        self.undeploy_application(deployment_id)

        node1 = self.client.node_instances.list(
            deployment_id=deployment.id,
            node_id='containing_node')[0]
        node2 = self.client.node_instances.list(
            deployment_id=deployment.id,
            node_id='contained_in_node1')[0]
        node3 = self.client.node_instances.list(
            deployment_id=deployment.id,
            node_id='contained_in_node2')[0]

        # The installation order for node instances based on timestamp
        self.assertLess(
            node1.runtime_properties['time'],
            node2.runtime_properties['time']
        )
        self.assertLess(
            node1.runtime_properties['time'],
            node3.runtime_properties['time']
        )
        self.assertLess(
            node2.runtime_properties['time'],
            node3.runtime_properties['time']
        )

        # The un-installation order for node instances based on timestamp
        self.assertLess(
            node3.runtime_properties['unreachable_call_order'][0]['time'],
            node2.runtime_properties['unreachable_call_order'][0]['time']
        )
        self.assertLess(
            node3.runtime_properties['unreachable_call_order'][0]['time'],
            node1.runtime_properties['unreachable_call_order'][0]['time']
        )
        self.assertLess(
            node2.runtime_properties['unreachable_call_order'][0]['time'],
            node1.runtime_properties['unreachable_call_order'][0]['time']
        )

    def test_stop_monitor_node_operation(self):
        dsl_path = resource(
            "dsl/hardcoded_operation_properties.yaml")
        deployment, _ = self.deploy_application(dsl_path)
        deployment_id = deployment.id
        self.undeploy_application(deployment_id)
        # test monitor invocations
        node_id = self.client.node_instances.list(
            deployment_id=deployment_id)[0].id
        node_instance = self.client.node_instances.get(node_id)
        invocations = node_instance.runtime_properties[
            'monitoring_operations_invocation'
        ]
        self.assertEqual(2, len(invocations))
        self.assertTrue('single_node' in invocations[0]['id'])
        self.assertEqual('start_monitor', invocations[0]['operation'])
        self.assertTrue('single_node' in invocations[1]['id'])
        self.assertEqual('stop_monitor', invocations[1]['operation'])

    def test_failed_uninstall_task(self):
        dsl_path = resource('dsl/basic_stop_error.yaml')
        deployment, _ = self.deploy_application(dsl_path)
        deployment_id = deployment.id
        self.undeploy_application(deployment_id,
                                  parameters={'ignore_failure': True})

        node_id = self.client.node_instances.list(
            deployment_id=deployment_id)[0].id
        node_instance = self.client.node_instances.get(node_id)
        machines = node_instance.runtime_properties[
            'machines'
        ]

        self.assertEqual(0, len(machines))


def is_unreachable_called(node_id,
                          unreachable_call_order):
    return next((x for x in
                 unreachable_call_order if x['id'] == node_id), None)
