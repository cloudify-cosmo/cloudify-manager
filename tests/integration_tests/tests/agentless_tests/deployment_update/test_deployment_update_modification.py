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

from . import DeploymentUpdateBase, BLUEPRINT_ID


class TestDeploymentUpdateModification(DeploymentUpdateBase):

    def test_modify_relationships(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('modify_relationship')

        node_mapping = {
            'target': 'site1',
            'frozen': 'site2',
            'modified': 'site3'
        }

        base_nodes, base_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)
        base_source_node = base_nodes['modified'][0]
        base_source_node_instance = base_node_instances['modified'][0]

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        dep_update = \
            self.client.deployment_updates.update_with_existing_blueprint(
                deployment.id, BLUEPRINT_ID)

        # wait for 'update' workflow to finish
        self._wait_for_execution_to_terminate(deployment.id, 'update')
        self._wait_for_successful_state(dep_update.id)

        modified_nodes, modified_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)

        # assert all unaffected nodes and node instances remained intact
        self._assert_equal_entity_dicts(
                base_nodes,
                modified_nodes,
                keys=['target', 'frozen', 'modified'],
                excluded_items=['relationships']
        )

        self._assert_equal_entity_dicts(
                base_node_instances,
                modified_node_instances,
                keys=['target', 'frozen', 'modified'],
                excluded_items=['relationships']
        )

        # get the nodes and node instances
        modified_source_node = modified_nodes['modified'][0]
        modified_source_node_instance = modified_node_instances['modified'][0]

        # assert there are 2 relationships total
        self.assertEquals(2, len(modified_source_node.relationships))
        self.assertEquals(2, len(modified_source_node_instance.relationships))

        self.assertEqual(modified_source_node.relationships[0],
                         base_source_node.relationships[1])
        self.assertEqual(modified_source_node.relationships[1],
                         base_source_node.relationships[0])

        self.assertEqual(modified_source_node_instance.relationships[0],
                         base_source_node_instance.relationships[1])
        self.assertEqual(modified_source_node_instance.relationships[1],
                         base_source_node_instance.relationships[0])

    def test_modify_node_operation(self):
        """
        The test sequence is as follows:
        The stop operation is set through the base blueprint to increment
        source_ops runtime_property
        1. execute the stop operation.
        2. check whether the increment indeed occur (i.e. source_ops=1).
        3. create a step which modified the the inputs field of the operation
        from increment to decrement and execute deployment update commit.
        4. execute the stop operation again.
        5. check if the source_ops is now 0.
        :return:
        """
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path(
                    'modify_node_operation')

        node_mapping = {
            'modified': 'site1'
        }

        # Execute the newly modified operation
        self.client.executions.start(
                deployment.id,
                'execute_operation',
                parameters={
                    'operation': 'cloudify.interfaces.lifecycle.stop'
                }
        )
        self._wait_for_execution_to_terminate(deployment.id,
                                              'execute_operation')

        base_nodes, base_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)

        self.assertDictContainsSubset(
                {'source_ops_counter': '1'},
                base_node_instances['modified'][0]['runtime_properties']
        )

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        dep_update = \
            self.client.deployment_updates.update_with_existing_blueprint(
                deployment.id, BLUEPRINT_ID, skip_reinstall=True)

        # wait for 'update' workflow to finish
        self._wait_for_execution_to_terminate(deployment.id, 'update')
        self._wait_for_successful_state(dep_update.id)

        # assert nothing changed except for plugins and operations
        modified_nodes, modified_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)

        self._assert_equal_entity_dicts(
                base_nodes,
                modified_nodes,
                keys=['modified'],
                excluded_items=['operations']
        )

        self._assert_equal_entity_dicts(
                base_node_instances,
                modified_node_instances,
                keys=['modified']
        )

        # Execute the newly modified operation
        self.client.executions.start(
                deployment.id,
                'execute_operation',
                parameters={
                    'operation': 'cloudify.interfaces.lifecycle.stop'
                }
        )
        self._wait_for_execution_to_terminate(deployment.id,
                                              'execute_operation')

        # Check again for the nodes and node instances and check
        # their runtime properties
        modified_nodes, modified_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)

        self.assertEqual(len(modified_nodes['modified']), 1)
        modified_node = modified_nodes['modified'][0]
        self.assertEqual(len(modified_node_instances['modified']), 1)
        modified_node_instance = modified_node_instances['modified'][0]

        self._assert_equal_entity_dicts(
                base_nodes,
                modified_nodes,
                keys=['modified'],
                excluded_items=['operations']
        )

        self._assert_equal_entity_dicts(
                base_node_instances,
                modified_node_instances,
                keys=['modified'],
                excluded_items=['runtime_properties']
        )

        affected_lifecycle_operation = modified_node['operations'].get(
                'cloudify.interfaces.lifecycle.create')
        self.assertIsNotNone(affected_lifecycle_operation)

        self.assertDictContainsSubset(
                {'source_ops_counter': '0'},
                modified_node_instance['runtime_properties']
        )

    def test_modify_relationship_operation(self):
        """
        In this test the script_path of the operation is modified from
        increment to decrement. this is tested on storage level (no operation
        is executed since this is a relationship operation, and currently we
        have no mechanism in place to execute relationship operation.
        :return:
        """
        deployment, modified_bp_path = self._deploy_and_get_modified_bp_path(
                'modify_relationship_operation')

        node_mapping = {
            'target': 'site1',
            'source': 'site2'
        }
        operation_id = 'custom_lifecycle.custom_operation'

        base_nodes, base_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        dep_update = \
            self.client.deployment_updates.update_with_existing_blueprint(
                deployment.id, BLUEPRINT_ID)

        # wait for 'update' workflow to finish
        self._wait_for_execution_to_terminate(deployment.id, 'update')
        self._wait_for_successful_state(dep_update.id)

        self.client.executions.start(deployment.id, 'custom_workflow',
                                     parameters={'node_id': 'site2'})
        self._wait_for_execution_to_terminate(deployment.id, 'custom_workflow')

        modified_nodes, modified_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)

        # assert all unaffected nodes and node instances remained intact
        self._assert_equal_entity_dicts(
                base_nodes,
                modified_nodes,
                keys=['target', 'source'],
                excluded_items=['relationships']
        )

        self._assert_equal_entity_dicts(
                base_node_instances,
                modified_node_instances,
                keys=['target', 'source'],
                excluded_items=['relationships', 'runtime_properties']
        )

        # Check that there is only 1 from each
        self.assertEquals(1, len(modified_nodes['target']))
        self.assertEquals(1, len(modified_node_instances['target']))
        self.assertEquals(1, len(modified_nodes['source']))
        self.assertEquals(1, len(modified_node_instances['source']))

        # get the nodes and node instances
        source_node = modified_nodes['source'][0]
        source_node_instance = modified_node_instances['source'][0]

        # assert there are 1 relationships
        self.assertEquals(1, len(source_node.relationships))
        self.assertEquals(1, len(source_node_instance.relationships))

        # check the new relationship between site2 and site1 is in place
        self._assert_relationship(
                source_node_instance.relationships,
                target='site1',
                expected_type='new_relationship_type')
        self._assert_relationship(
                source_node.relationships,
                target='site1',
                expected_type='new_relationship_type')

        dict_to_check = self._create_dict(['inputs', 'script_path',
                                           'decrement.sh'])

        self.assertDictContainsSubset(
                {'source_ops_counter': '-1'},
                source_node_instance['runtime_properties']
        )

        # check all operation have been executed
        source_operations = \
            source_node['relationships'][0]['source_operations']
        self.assertDictContainsSubset(dict_to_check,
                                      source_operations[operation_id])

    def test_modify_property(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('modify_property')

        node_mapping = {'affected_node': 'site1'}

        base_nodes, base_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)
        base_node = base_nodes['affected_node'][0]

        base_properties = base_node['properties']
        modified_property = \
            base_properties.get('custom_prop', {}).get('inner_prop')
        self.assertEqual(modified_property, 1)

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        dep_update = \
            self.client.deployment_updates.update_with_existing_blueprint(
                deployment.id, BLUEPRINT_ID)

        # wait for 'update' workflow to finish
        self._wait_for_execution_to_terminate(deployment.id, 'update')
        self._wait_for_successful_state(dep_update.id)

        modified_nodes, modified_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)
        modified_node = modified_nodes['affected_node'][0]
        modified_properties = modified_node['properties']
        modified_property = \
            modified_properties.get('custom_prop', {}).get('inner_prop')
        self.assertIsNotNone(modified_property)
        self.assertEqual(modified_property, 2)

        # assert nothing else changed
        self._assert_equal_dicts(
            base_node['properties'],
            modified_node['properties'],
            excluded_items=['custom_prop', 'blueprint_id']
        )

    def test_modify_workflow(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('modify_workflow')
        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        dep_update = \
            self.client.deployment_updates.update_with_existing_blueprint(
                deployment.id, BLUEPRINT_ID)

        # assert that 'update' workflow was executed
        self._wait_for_execution_to_terminate(deployment.id,
                                              'update')

        self.client.executions.start(dep_update.deployment_id,
                                     workflow_id='my_custom_workflow',
                                     parameters={'node_id': 'site1'})

        # assert that 'update' workflow was executed
        self._wait_for_execution_to_terminate(deployment.id,
                                              'my_custom_workflow')
        affected_node = self.client.node_instances.list(
            deployment_id=dep_update.deployment_id,
            node_id='site1'
        )
        self.assertEqual(len(affected_node), 6)
        deployment = self.client.deployments.get(dep_update.deployment_id)
        self.assertIn('my_custom_workflow',
                      [w['name'] for w in deployment.workflows])

    def test_modify_output(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('modify_output')

        deployment = self.client.deployments.get(deployment.id)
        self.assertDictContainsSubset({'custom_output': {'value': 0}},
                                      deployment.outputs)

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        dep_update = \
            self.client.deployment_updates.update_with_existing_blueprint(
                deployment.id, BLUEPRINT_ID)

        # assert that 'update' workflow was executed
        self._wait_for_execution_to_terminate(deployment.id, 'update')
        self._wait_for_successful_state(dep_update.id)

        deployment = self.client.deployments.get(dep_update.deployment_id)
        self.assertDictContainsSubset({'custom_output': {'value': 1}},
                                      deployment.outputs)

    def test_modify_description(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('modify_description')

        self.assertRegexpMatches(deployment['description'], 'old description')

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        dep_update = \
            self.client.deployment_updates.update_with_existing_blueprint(
                deployment.id, BLUEPRINT_ID)

        # assert that 'update' workflow was executed
        self._wait_for_execution_to_terminate(deployment.id, 'update')
        self._wait_for_successful_state(dep_update.id)

        deployment = self.client.deployments.get(dep_update.deployment_id)
        self.assertRegexpMatches(deployment['description'], 'new description')
