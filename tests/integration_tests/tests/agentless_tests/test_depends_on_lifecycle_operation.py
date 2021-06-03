########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import uuid
import pytest

from integration_tests import AgentlessTestCase
from integration_tests.tests import utils

pytestmark = pytest.mark.group_workflows


@pytest.mark.usefixtures('mock_workflows_plugin')
class DependsOnLifecycleOperationTest(AgentlessTestCase):

    @staticmethod
    def generate_blueprint(depended_on_operation):
        return """
tosca_definitions_version: cloudify_dsl_1_3

imports:
    - cloudify/types/types.yaml
    - wf--blueprint:mock_workflows

node_templates:
      node:
        type: cloudify.nodes.Root
        interfaces:
          cloudify.interfaces.lifecycle:
            precreate: wf--mock_workflows.mock_workflows.workflows.do_nothing
            configure: wf--mock_workflows.mock_workflows.workflows.do_nothing
            create: wf--mock_workflows.mock_workflows.workflows.do_nothing
            start: wf--mock_workflows.mock_workflows.workflows.do_nothing

      depends_on_operation_node:
        type: cloudify.nodes.Root
        relationships:
          - type: cloudify.relationships.depends_on_lifecycle_operation
            target: node
            properties:
              operation: {0}
        interfaces:
          cloudify.interfaces.lifecycle:
            precreate: wf--mock_workflows.mock_workflows.workflows.do_nothing
            configure: wf--mock_workflows.mock_workflows.workflows.do_nothing
            create: wf--mock_workflows.mock_workflows.workflows.do_nothing
            start: wf--mock_workflows.mock_workflows.workflows.do_nothing
""".format(depended_on_operation)

    def _test_full_flow(self, expected_info, tested_operation):
        self.assertIsInstance(expected_info, list)

        base_blueprint_path = utils.get_resource('dsl/mock_workflows.yaml')
        self.client.blueprints.upload(base_blueprint_path, 'mock_workflows')
        utils.wait_for_blueprint_upload('mock_workflows', self.client)

        deployment_id = 'd{0}'.format(uuid.uuid4())
        main_blueprint = self.generate_blueprint(tested_operation)
        main_blueprint_path = self.make_yaml_file(main_blueprint)
        _, execution_id = self.deploy_application(main_blueprint_path,
                                                  deployment_id=deployment_id)

        task_graphs = self.client.tasks_graphs.list(execution_id, 'install')
        operations_info = {}
        operations_id = {}

        for graph in task_graphs:
            operations = self.client.operations.list(graph.id)
            for op in operations:
                operations_id[op.id] = {}
                operations_id[op.id]['dependencies'] = op.dependencies
                operations_id[op.id]['info'] = op.info

                try:
                    cloudify_context = op.parameters['task_kwargs'][
                        'kwargs']['__cloudify_context']
                except KeyError:
                    continue
                op_name = cloudify_context['operation']['name']
                node_name = cloudify_context['node_name']
                operations_info[(op_name, node_name)] = op.containing_subgraph

        # Doest not matter from what operation the node's main subgraph id
        # will be taken from.
        install_depends_id = operations_info[
            ('cloudify.interfaces.lifecycle.configure',
             'depends_on_operation_node')]
        next_tasks_info = [operations_id[dep]['info']
                           for dep in
                           operations_id[install_depends_id]['dependencies']]
        self.assertCountEqual(expected_info, next_tasks_info)

    def test_depends_on_precreate_operation(self):
        self._test_full_flow(['Node instance precreated'], 'precreate')

    def test_depends_on_configure_operation(self):
        self._test_full_flow(['Node instance configured', 'configured'],
                             'configure')

    def test_depends_on_create_operation(self):
        self._test_full_flow(['Node instance created', 'created'], 'create')

    def test_scaled_relationships(self):
        deployment_id = 'd{0}'.format(uuid.uuid4())
        main_blueprint = self.generate_blueprint('create') + """

groups:
  group1:
    members: [node, depends_on_operation_node]

policies:
  policy:
    type: cloudify.policies.scaling
    targets: [group1]
    properties:
      default_instances: 2
"""
        base_blueprint_path = utils.get_resource('dsl/mock_workflows.yaml')
        self.client.blueprints.upload(base_blueprint_path, 'mock_workflows')
        utils.wait_for_blueprint_upload('mock_workflows', self.client)

        main_blueprint_path = self.make_yaml_file(main_blueprint)
        _, execution_id = self.deploy_application(main_blueprint_path,
                                                  deployment_id=deployment_id)

        task_graphs = self.client.tasks_graphs.list(execution_id, 'install')
        operations_info = {}
        operations_id = {}

        for graph in task_graphs:
            operations = self.client.operations.list(graph.id)
            for op in operations:
                operations_id[op.id] = {}
                operations_id[op.id]['dependencies'] = op.dependencies
                operations_id[op.id]['info'] = op.info
                try:
                    cloudify_context = op.parameters['task_kwargs'][
                        'kwargs']['__cloudify_context']
                except KeyError:
                    continue
                op_name = cloudify_context['operation']['name']
                node_id = cloudify_context['node_id']
                operations_info[(op_name, node_id)] = {}
                operations_info[(op_name, node_id)]['containing_subgraph']\
                    = op.containing_subgraph
                operations_info[(op_name, node_id)]['op_name'] = op_name

        install_subgraph_ids = [v['containing_subgraph']
                                for (__, node), v in operations_info.items()
                                if ('depends_on_operation_node' in node and
                                    v['op_name'] ==
                                    'cloudify.interfaces.lifecycle.configure')]

        self.assertEqual(len(install_subgraph_ids), 2)
        for install_id in install_subgraph_ids:
            next_tasks_info = [operations_id[dep]['info']
                               for dep in
                               operations_id[install_id]['dependencies']]
            self.assertCountEqual(['Node instance created', 'created'],
                                  next_tasks_info)
