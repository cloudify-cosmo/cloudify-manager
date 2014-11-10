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


import uuid

from testenv import TestCase
from testenv.utils import get_resource as resource
from testenv.utils import deploy_application
from testenv.utils import wait_for_deployment_creation_to_complete


class RestAPITest(TestCase):

    def setUp(self):
        super(RestAPITest, self).setUp()
        self.blueprint_id = 'blueprint-' + str(uuid.uuid4())
        self.deployment_id = 'deployment-' + str(uuid.uuid4())
        self.dsl_path = resource('dsl/basic.yaml')
        self.node_id = 'webserver_host'

    def _create_basic_deployment(self,
                                 dsl_path=None,
                                 blueprint_id=None,
                                 deployment_id=None):
        dsl_path = dsl_path or self.dsl_path
        blueprint_id = blueprint_id or self.blueprint_id
        deployment_id = deployment_id or self.deployment_id
        self.client.blueprints.upload(dsl_path, blueprint_id)
        self.client.deployments.create(blueprint_id, deployment_id)
        wait_for_deployment_creation_to_complete(
            deployment_id=deployment_id)

    def _deploy_basic_blueprint(self):
        deploy_application(self.dsl_path,
                           blueprint_id=self.blueprint_id,
                           deployment_id=self.deployment_id)

    def test_nodes(self):
        self._create_basic_deployment()
        nodes = self.client.nodes.list(deployment_id=self.deployment_id)
        self.assertEqual(1, len(nodes))

        all_nodes = self.client.nodes.list()
        self.assertEqual(1, len(all_nodes))

        node = all_nodes[0]
        self.assertTrue(len(node.operations) > 0)
        self.assertEqual(node.relationships, [])
        self.assertEqual(self.blueprint_id, node.blueprint_id)
        self.assertTrue(len(node.plugins) > 0)
        self.assertEqual(self.node_id, node.id)
        self.assertEqual(1, node.number_of_instances)
        self.assertEqual(self.node_id, node.host_id)
        self.assertEqual(2, len(node.type_hierarchy))
        self.assertEqual(self.deployment_id, node.deployment_id)
        self.assertEqual('cloudify.nodes.Compute', node.type)
        self.assertTrue(len(node.properties) > 0)

    def test_node_instances(self):
        self._create_basic_deployment()
        instances = self.client.node_instances.list(
            deployment_id=self.deployment_id)
        self.assertEqual(1, len(instances))

        all_instances = self.client.node_instances.list()
        self.assertEqual(1, len(all_instances))

        instance = all_instances[0]
        self.assertIsNotNone(instance.id)
        self.assertEqual(self.deployment_id, instance.deployment_id)
        self.assertEqual(instance.runtime_properties, {})
        self.assertEqual('uninitialized', instance.state)

        instance = self.client.node_instances.get(instance.id)
        self.assertIsNotNone(instance.id)
        self.assertEqual(self.deployment_id, instance.deployment_id)
        self.assertEqual(instance.runtime_properties, {})
        self.assertEqual('uninitialized', instance.state)
        self.assertEqual(1, instance.version)

    def test_node_instances2(self):
        dsl_path = resource('dsl/node_instances.yaml')
        blueprint_id1 = 'blueprint-{0}'.format(str(uuid.uuid4()))
        blueprint_id2 = 'blueprint-{0}'.format(str(uuid.uuid4()))
        deployment_id1 = 'deployment-{0}'.format(str(uuid.uuid4()))
        deployment_id2 = 'deployment-{0}'.format(str(uuid.uuid4()))
        self._create_basic_deployment(dsl_path, blueprint_id1, deployment_id1)
        self._create_basic_deployment(dsl_path, blueprint_id2, deployment_id2)

        all_instances = self.client.node_instances.list()
        dep1_instances = self.client.node_instances.list(deployment_id1)
        dep2_instances = self.client.node_instances.list(deployment_id2)
        dep1_n1_instances = self.client.node_instances.list(
            deployment_id1, 'node1')
        dep1_n2_instances = self.client.node_instances.list(
            deployment_id1, 'node2')
        dep2_n1_instances = self.client.node_instances.list(
            deployment_id2, 'node1')
        dep2_n2_instances = self.client.node_instances.list(
            deployment_id2, 'node2')

        self.assertEqual(8, len(all_instances))

        def assert_dep(expected_len, dep, instances):
            self.assertEqual(expected_len, len(instances))
            for instance in instances:
                self.assertEqual(instance.deployment_id, dep)

        assert_dep(4, deployment_id1, dep1_instances)
        assert_dep(4, deployment_id2, dep2_instances)

        def assert_dep_and_node(expected_len, dep, node_id, instances):
            self.assertEqual(expected_len, len(instances))
            for instance in instances:
                self.assertEqual(instance.deployment_id, dep)
                self.assertEqual(instance.node_id, node_id)

        assert_dep_and_node(2, deployment_id1, 'node1', dep1_n1_instances)
        assert_dep_and_node(2, deployment_id1, 'node2', dep1_n2_instances)
        assert_dep_and_node(2, deployment_id2, 'node1', dep2_n1_instances)
        assert_dep_and_node(2, deployment_id2, 'node2', dep2_n2_instances)

    def test_blueprints(self):
        self._create_basic_deployment()
        blueprints = self.client.blueprints.list()
        self.assertEqual(1, len(blueprints))
        blueprint_id = blueprints[0].id
        blueprint_by_id = self.client.blueprints.get(blueprint_id)
        self.assertDictContainsSubset(blueprint_by_id, blueprints[0])
        self.assertDictContainsSubset(blueprints[0], blueprint_by_id)

    def test_deployments(self):
        self._create_basic_deployment()
        deployments = self.client.deployments.list()
        self.assertEqual(1, len(deployments))
        deployment_id = deployments[0].id
        deployment_by_id = self.client.deployments.get(deployment_id)
        self.assertDictContainsSubset(deployment_by_id, deployments[0])
        self.assertDictContainsSubset(deployments[0], deployment_by_id)

    def test_executions(self):
        self._deploy_basic_blueprint()
        deployments = self.client.deployments.list()
        self.assertEqual(1, len(deployments))
        deployment_id = deployments[0].id
        deployment_by_id = self.client.deployments.get(deployment_id)
        executions = self.client.executions.list(
            deployment_by_id.id)

        self.assertEqual(len(executions),
                         2,
                         'There should be 2 executions but are: {0}'.format(
                             executions))
        execution_from_list = executions[0]
        execution_by_id = self.client.executions.get(execution_from_list.id)

        self.assertEqual(execution_from_list.id, execution_by_id.id)
        self.assertEqual(execution_from_list.workflow_id,
                         execution_by_id.workflow_id)
        self.assertEqual(execution_from_list['blueprint_id'],
                         execution_by_id['blueprint_id'])
