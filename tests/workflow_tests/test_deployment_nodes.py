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

__author__ = 'ran'

from testenv import TestCase
from testenv import get_resource as resource
from testenv import deploy_application as deploy


class TestDeploymentNodes(TestCase):

    def test_get_deployment_nodes(self):
        dsl_path = resource("dsl/deployment-nodes-three-nodes.yaml")
        deployment, _ = deploy(dsl_path)
        deployment_id = deployment.id
        nodes = self.client.node_instances.list(deployment_id=deployment_id)
        self.assertEqual(deployment_id, nodes.deploymentId)
        self.assertEqual(3, len(nodes.nodes))

        def assert_node_state(node_id_infix):
            self.assertTrue(any(map(
                lambda n: node_id_infix in n.id and n.state == 'started',
                nodes.nodes
            )), 'Failed finding node {0} state'.format(node_id_infix))

        assert_node_state('containing_node')
        assert_node_state('contained_in_node1')
        assert_node_state('contained_in_node2')

    def test_partial_update_node_instance(self):
        dsl_path = resource("dsl/set-property.yaml")
        deployment, _ = deploy(dsl_path)

        node_id = self.client.node_instances.list(
            deployment_id=deployment.id).id
        node_instance = self.client.node_instances.get(node_id)

        # Initial assertions
        self.assertEquals('started', node_instance.state)
        self.assertIsNotNone(node_instance.version)
        self.assertEquals(2, len(node_instance.runtime_properties))

        # Updating only the state
        node_instance = self.client.node_instances.update(
            node_id,
            version=node_instance.version,
            state='new_state')

        # Verifying the node's state has changed
        self.assertEquals('new_state', node_instance.state)
        # Verifying the node's runtime properties remained without a change
        self.assertEquals(2, len(node_instance.runtime_properties))

        # Updating only the runtime properties
        node_instance = self.client.node_instances.update(
            node_id,
            version=node_instance.version,
            runtime_properties={'new_key': 'new_value'})

        # Verifying the node's state remained the same despite the update to
        #  the runtime_properties
        self.assertEquals('new_state', node_instance.state)
        # Verifying the new property is in the node's runtime properties
        self.assertTrue('new_key' in node_instance.runtime_properties)
        self.assertEquals('new_value',
                          node_instance.runtime_properties['new_key'])
        # Verifying the older properties are still there too (partial update)
        self.assertEquals(3, len(node_instance.runtime_properties))

        # Updating both state and runtime properties (updating an existing
        # key in runtime properties)
        node_instance = self.client.node_instances.update(
            node_id,
            version=node_instance.version,
            runtime_properties={'new_key': 'another_value'},
            state='final_state')

        # Verifying state has updated
        self.assertEquals('final_state', node_instance.state)
        # Verifying the update to the runtime properties
        self.assertEquals(3, len(node_instance.runtime_properties))
        self.assertEquals('another_value',
                          node_instance.runtime_properties['new_key'])

        # Updating neither state nor runtime properties (empty update)
        node_instance = self.client.node_instances.update(
            node_id,
            version=node_instance.version)

        # Verifying state hasn't changed
        self.assertEquals('final_state', node_instance.state)
        # Verifying the runtime properties haven't changed
        self.assertEquals(3, len(node_instance.runtime_properties))
        self.assertEquals('another_value',
                          node_instance.runtime_properties['new_key'])
