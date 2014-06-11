########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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

__author__ = 'idanmo'

import uuid

from workflow_tests.testenv import TestCase
from workflow_tests.testenv import get_resource as resource


class RestAPITest(TestCase):

    def setUp(self):
        super(RestAPITest, self).setUp()
        dsl_path = resource('dsl/basic.yaml')
        self.node_id = 'webserver_host'
        self.blueprint_id = 'blueprint-' + str(uuid.uuid4())
        self.deployment_id = 'deployment-' + str(uuid.uuid4())
        self.client.blueprints.upload(dsl_path, self.blueprint_id)
        self.client.deployments.create(self.blueprint_id, self.deployment_id)

    def test_nodes(self):
        def assert_nodes():
            nodes = self.client.nodes.list(deployment_id=self.deployment_id)
            self.assertEqual(1, len(nodes))
        TestCase.do_assertions(assert_nodes, timeout=30)

        all_nodes = self.client.nodes.list()
        self.assertEqual(1, len(all_nodes))

        node = all_nodes[0]
        self.assertTrue(len(node.operations) > 0)
        self.assertIsNone(node.relationships)
        self.assertEqual(self.blueprint_id, node.blueprint_id)
        self.assertTrue(len(node.plugins) > 0)
        self.assertEqual(self.node_id, node.id)
        self.assertEqual(1, node.number_of_instances)
        self.assertEqual(self.node_id, node.host_id)
        self.assertEqual(2, len(node.type_hierarchy))
        self.assertEqual(self.deployment_id, node.deployment_id)
        self.assertEqual('cloudify.types.host', node.type)
        self.assertTrue(len(node.properties) > 0)

    def test_node_instances(self):
        def assert_instances():
            instances = self.client.node_instances.list(
                deployment_id=self.deployment_id)
            self.assertEqual(1, len(instances))
        TestCase.do_assertions(assert_instances, timeout=30)

        all_instances = self.client.node_instances.list()
        self.assertEqual(1, len(all_instances))

        instance = all_instances[0]
        self.assertIsNotNone(instance.id)
        self.assertEqual(self.deployment_id, instance.deployment_id)
        self.assertIsNone(instance.runtime_properties)
        self.assertEqual('uninitialized', instance.state)

        instance = self.client.node_instances.get(instance.id)
        self.assertIsNotNone(instance.id)
        self.assertEqual(self.deployment_id, instance.deployment_id)
        self.assertIsNone(instance.runtime_properties)
        self.assertEqual('uninitialized', instance.state)
        self.assertEqual(1, instance.version)
