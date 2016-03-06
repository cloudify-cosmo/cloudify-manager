# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.
import time

from dsl_parser.parser import parse_from_path
from manager_rest.models import Execution
from testenv import TestCase
from testenv.utils import get_resource as resource
from testenv.utils import deploy_application as deploy
# from manager_rest.blueprints_manager import get_blueprints_manager


class TestDeploymentUpdate(TestCase):

    def _wait_for_execution(self, execution, timeout=900):
        # Poll for execution status until execution ends
        deadline = time.time() + timeout
        while True:
            if time.time() > deadline:
                raise Exception(
                    'execution of operation {0} for deployment {1} timed out'.
                    format(execution.workflow_id, execution.deployment_id))

            execution = self.client.executions.get(execution.id)
            if execution.status in Execution.END_STATES:
                return execution
            time.sleep(3)

    def test_add_node(self):
        """
        add a node (type exists) which is contained in an existing node
        - assert that both node and node instance have been created
        - assert the node/instance relationships have been created
        - assert the 'update' workflow has been executed and
          all related operations were executed as well
        """
        initial_blueprint_path = \
            resource('dsl/deployment_update/dep_up_initial.yaml')
        deployment, _ = deploy(initial_blueprint_path)

        new_blueprint_path = \
            resource('dsl/deployment_update/dep_up_add_node.yaml')
        blueprint = parse_from_path(new_blueprint_path)

        dep_update = \
            self.client.deployment_updates.stage(deployment.id,
                                                 blueprint)
        self.client.deployment_updates.add(dep_update.id,
                                           entity_type='node',
                                           entity_id='site_1')
        self.client.deployment_updates.commit(dep_update.id)

        # assert that 'update' workflow was executed
        executions = self.client.executions.list(deployment_id=deployment.id,
                                                 workflow_id='update')
        execution = self._wait_for_execution(executions[0])
        self.assertEquals('terminated', execution['status'], execution.error)

        added_nodes = self.client.nodes.list(deployment_id=deployment.id,
                                             node_id='site_1')
        added_instances = \
            self.client.node_instances.list(deployment_id=deployment.id,
                                            node_id='site_1')

        # assert that node and node instance were added to storage
        self.assertEquals(1, len(added_nodes))
        self.assertEquals(1, len(added_instances))

        # assert that node has a relationship
        node = added_nodes[0]
        self.assertEquals(1, len(node.relationships))
        self._assert_relationship_exists(node.relationships,
                                         target='server')

        # assert that node instance has a relationship
        added_instance = added_instances[0]
        self.assertEquals(1, len(added_instance.relationships))
        self._assert_relationship_exists(added_instance.relationships,
                                         target='server')

        # assert all operations in 'update' ('install') workflow
        # are executed by making them increment a runtime property
        self.assertDictContainsSubset({'ops_counter': '6'},
                                      added_instance['runtime_properties'])

    def _assert_relationship_exists(self, relationships, target,
                                    expected_type=None):
        """
        assert that a node/node instance has a specific relationship
        :param relationships: node/node instance relationships list
        :param target: target name (node id, not instance id)
        :param expected_type: expected relationship type
        """
        expected_type = expected_type or 'cloudify.relationships.contained_in'
        for relationship in relationships:
            relationship_type = relationship['type']
            relationship_target = (relationship.get('target_name') or
                                   relationship.get('target_id'))

        if (relationship_type == expected_type and
                relationship_target == target):
                return

        self.fail('relationship of target "{}" and type "{}" is missing'
                  .format(target, expected_type))
