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
class TestDeploymentNodes(AgentlessTestCase):

    def test_get_deployment_nodes(self):
        dsl_path = resource("dsl/deployment_nodes_three_nodes.yaml")
        deployment, _ = self.deploy_application(dsl_path)
        deployment_id = deployment.id

        def assert_node_state(node_id_infix, nodes):
            self.assertTrue(
                any(
                    node_id_infix in n.id and n.state == 'started'
                    for n in nodes),
                'Failed finding node {0} state'.format(node_id_infix))

        def assert_node_states():
            nodes = self.client.node_instances.list(
                deployment_id=deployment_id)
            self.assertEqual(3, len(nodes))
            assert_node_state('containing_node', nodes)
            assert_node_state('contained_in_node1', nodes)
            assert_node_state('contained_in_node2', nodes)

        self.do_assertions(assert_node_states, timeout=30)

    def test_partial_update_node_instance(self):
        dsl_path = resource("dsl/set_property.yaml")
        deployment, _ = self.deploy_application(dsl_path)

        node_id = self.client.node_instances.list(
            deployment_id=deployment.id)[0].id
        node_instance = self.client.node_instances.get(node_id)

        # Initial assertions
        self.assertEqual('started', node_instance.state)
        self.assertIsNotNone(node_instance.version)
        self.assertEqual(3, len(node_instance.runtime_properties))

        # Updating only the state
        node_instance = self.client.node_instances.update(
            node_id,
            version=node_instance.version,
            state='new_state')

        # Verifying the node's state has changed
        self.assertEqual('new_state', node_instance.state)
        # Verifying the node's runtime properties remained without a change
        self.assertEqual(3, len(node_instance.runtime_properties))

        # Updating only the runtime properties
        node_instance = self.client.node_instances.update(
            node_id,
            version=node_instance.version,
            runtime_properties={'new_key': 'new_value'})

        # Verifying the node's state remained the same despite the update to
        #  the runtime_properties
        self.assertEqual('new_state', node_instance.state)
        # Verifying the new property is in the node's runtime properties
        self.assertTrue('new_key' in node_instance.runtime_properties)
        self.assertEqual('new_value',
                         node_instance.runtime_properties['new_key'])
        # Verifying the older runtime properties no longer exist
        self.assertEqual(1, len(node_instance.runtime_properties))

        # Updating both state and runtime properties (updating an existing
        # key in runtime properties)
        node_instance = self.client.node_instances.update(
            node_id,
            version=node_instance.version,
            runtime_properties={'new_key': 'another_value'},
            state='final_state')

        # Verifying state has updated
        self.assertEqual('final_state', node_instance.state)
        # Verifying the update to the runtime properties
        self.assertEqual(1, len(node_instance.runtime_properties))
        self.assertEqual('another_value',
                         node_instance.runtime_properties['new_key'])

        # Updating neither state nor runtime properties (empty update)
        node_instance = self.client.node_instances.update(
            node_id,
            version=node_instance.version)

        # Verifying state hasn't changed
        self.assertEqual('final_state', node_instance.state)
        # Verifying the runtime properties haven't changed
        self.assertEqual(1, len(node_instance.runtime_properties))
        self.assertEqual('another_value',
                         node_instance.runtime_properties['new_key'])

    def test_update_node_instance_runtime_properties(self):
        dsl_path = resource('dsl/set_property.yaml')
        deployment, _ = self.deploy_application(dsl_path)

        node_id = self.client.node_instances.list(
            deployment_id=deployment.id)[0].id
        node_instance = self.client.node_instances.get(node_id)

        # Initial assertions
        self.assertIsNotNone(node_instance.version)
        self.assertEqual(3, len(node_instance.runtime_properties))

        # Updating the runtime properties with a new key
        node_instance = self.client.node_instances.update(
            node_id,
            version=node_instance.version,
            runtime_properties={'new_key': 'new_value'})

        # Verifying the new property is in the node's runtime properties
        self.assertTrue('new_key' in node_instance.runtime_properties)
        self.assertEqual('new_value',
                         node_instance.runtime_properties['new_key'])
        # Verifying the older runtime properties no longer exist
        self.assertEqual(1, len(node_instance.runtime_properties))

        # Updating an existing key in runtime properties
        node_instance = self.client.node_instances.update(
            node_id,
            version=node_instance.version,
            runtime_properties={'new_key': 'another_value'})

        # Verifying the update to the runtime properties
        self.assertEqual(1, len(node_instance.runtime_properties))
        self.assertEqual('another_value',
                         node_instance.runtime_properties['new_key'])

        # Cleaning up the runtime properties
        node_instance = self.client.node_instances.update(
            node_id,
            version=node_instance.version,
            runtime_properties={})

        # Verifying the node no longer has any runtime properties
        self.assertEqual(0, len(node_instance.runtime_properties))
