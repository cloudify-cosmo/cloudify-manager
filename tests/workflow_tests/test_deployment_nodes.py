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
from testenv import get_deployment_nodes


class TestDeploymentNodes(TestCase):

    def test_get_deployment_nodes(self):
        dsl_path = resource("dsl/deployment-nodes-three-nodes.yaml")
        deployment, _ = deploy(dsl_path)
        deployment_id = deployment.id
        nodes = get_deployment_nodes(deployment_id, get_state=True)
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
