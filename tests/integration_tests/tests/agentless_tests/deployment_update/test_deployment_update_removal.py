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
from pytest import mark

from cloudify_rest_client.exceptions import CloudifyClientError

from . import DeploymentUpdateBase, BLUEPRINT_ID
from integration_tests.tests.utils import wait_for_blueprint_upload

pytestmark = mark.group_deployments


class TestDeploymentUpdateRemoval(DeploymentUpdateBase):

    def test_uninstall_execution_order(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('uninstall_execution_order')
        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        self.client.deployment_updates.update_with_existing_blueprint(
            deployment.id, BLUEPRINT_ID)
        self._wait_for_execution_to_terminate(deployment.id, 'update')

        self.assertFalse(self.client.node_instances.list(
                node_id='site1').items[0].runtime_properties['is_op_started'],
                         'Site2 operations were executed '
                         'before/simultaneously with Site3 operations, '
                         'although site3 connected_to site2')

    def test_remove_node(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('remove_node')

        node_mapping = {
            'remove_related': 'site1',
            'removed': 'site2'
        }

        base_nodes, base_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)

        # an update preview should have no effect
        self.client.deployment_updates.update_with_existing_blueprint(
            deployment.id, BLUEPRINT_ID, preview=True)

        unmodified_nodes, unmodified_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)

        # assert all unaffected nodes and node instances remained intact
        self._assert_equal_entity_dicts(
            base_nodes,
            unmodified_nodes,
            keys=['remove_related', 'removed'],
            excluded_items=['runtime_properties']
        )

        self._assert_equal_entity_dicts(
            base_node_instances,
            unmodified_node_instances,
            keys=['remove_related', 'removed'],
            excluded_items=['runtime_properties']
        )

        # assert that node and node instance were not removed from storage
        self.assertEqual(1, len(unmodified_nodes['removed']))
        self.assertEqual(1, len(unmodified_node_instances['removed']))

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
                keys=['remove_related', 'removed'],
                excluded_items=['runtime_properties']
        )

        self._assert_equal_entity_dicts(
                base_node_instances,
                modified_node_instances,
                keys=['remove_related', 'removed'],
                excluded_items=['runtime_properties']
        )

        # assert that node and node instance were removed from storage
        self.assertEqual(0, len(modified_nodes['removed']))
        self.assertEqual(0, len(modified_node_instances['removed']))

        # assert relationship target remained intact
        self.assertEqual(1, len(modified_nodes['remove_related']))
        self.assertEqual(1, len(modified_node_instances['remove_related']))

        # assert all operations in 'update' ('install') workflow
        # are executed by making them increment a runtime property
        remove_related_instance = modified_node_instances['remove_related'][0]
        self._assertDictContainsSubset(
                {'target_ops_counter': '1'},
                remove_related_instance['runtime_properties']
        )

    def test_remove_node_operation(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path(
                    'remove_node_operation')

        node_mapping = {'modified': 'site1'}

        operation_id = 'custom_lifecycle.custom_operation'

        # Execute the newly modified operation
        self.client.executions.start(
                deployment.id,
                'execute_operation',
                parameters={
                    'operation': operation_id
                }
        )
        self._wait_for_execution_to_terminate(deployment.id,
                                              'execute_operation')

        base_nodes, base_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)

        self._assertDictContainsSubset(
                {'source_ops_counter': '1'},
                base_node_instances['modified'][0]['runtime_properties']
        )

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        dep_update = \
            self.client.deployment_updates.update_with_existing_blueprint(
                deployment.id, BLUEPRINT_ID)

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

        modified_node = modified_nodes['modified'][0]
        modified_node_instance = modified_node_instances['modified'][0]

        affected_lifecycle_operation = \
            modified_node['operations'].get(operation_id)

        self.assertIsNone(affected_lifecycle_operation)

        # Execute the newly modified operation
        execution = self.client.executions.start(
                deployment_id=deployment.id,
                workflow_id='execute_operation',
                parameters={'operation': operation_id}
        )

        execution_state = self._wait_for_execution(execution)

        self.assertIn('{0} operation of node instance {1} does not exist'
                      .format(operation_id, modified_node_instance.id),
                      execution_state.error)

    def test_remove_relationship(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('remove_relationship')

        node_mapping = {
            'related': 'site1',
            'target': 'site2',
            'source': 'site3'
        }

        base_nodes, base_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        dep_update = \
            self.client.deployment_updates.update_with_existing_blueprint(
                deployment.id, BLUEPRINT_ID)

        # wait for 'update' workflow to finish
        self._wait_for_execution_to_terminate(deployment.id, 'update')
        self._wait_for_successful_state(dep_update.id)

        # Get all related and affected nodes and node instances
        modified_nodes, modified_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)

        # assert all unaffected nodes and node instances remained intact
        self._assert_equal_entity_dicts(
                base_nodes,
                modified_nodes,
                keys=['related', 'target', 'source'],
                excluded_items=['runtime_properties', 'relationships']
        )

        self._assert_equal_entity_dicts(
                base_node_instances,
                modified_node_instances,
                keys=['related', 'target', 'source'],
                excluded_items=['runtime_properties', 'relationships']
        )

        # Check that there is only 1 from each
        self.assertEqual(1, len(modified_nodes['related']))
        self.assertEqual(1, len(modified_node_instances['related']))
        self.assertEqual(1, len(modified_nodes['target']))
        self.assertEqual(1, len(modified_node_instances['target']))
        self.assertEqual(1, len(modified_nodes['source']))
        self.assertEqual(1, len(modified_node_instances['source']))

        # get the nodes and node instances
        target_node_instance = modified_node_instances['target'][0]
        source_node = modified_nodes['source'][0]
        source_node_instance = modified_node_instances['source'][0]

        # assert there are 2 relationships total
        self.assertEqual(1, len(source_node.relationships))
        self.assertEqual(1, len(source_node_instance.relationships))

        # check the relationship between site3 and site1 is intact
        self._assert_relationship(
                source_node_instance.relationships,
                target='site1',
                expected_type='cloudify.relationships.connected_to')

        # check the relationship between site3 and site2 was deleted
        self._assert_relationship(
                source_node_instance.relationships,
                target='site2',
                expected_type='new_relationship_type',
                exists=False)

        # check all operation have been executed
        self._assertDictContainsSubset(
                {'target_ops_counter': '1'},
                target_node_instance['runtime_properties']
        )

    def test_remove_workflow(self):
        workflow_id = 'my_custom_workflow'

        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('remove_workflow')
        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        dep_update = \
            self.client.deployment_updates.update_with_existing_blueprint(
                deployment.id, BLUEPRINT_ID)

        # assert that 'update' workflow was executed
        self._wait_for_execution_to_terminate(deployment.id, 'update')
        self._wait_for_successful_state(dep_update.id)

        self.assertRaisesRegexp(CloudifyClientError,
                                'Workflow {0} does not exist in deployment {1}'
                                .format(workflow_id, deployment.id),
                                callable_obj=self.client.executions.start,
                                deployment_id=deployment.id,
                                workflow_id=workflow_id,
                                parameters={'node_id': 'site1'})

        deployment = self.client.deployments.get(dep_update.deployment_id)
        self.assertNotIn('my_custom_workflow',
                         [w['name'] for w in deployment.workflows])

    def test_remove_relationship_operation(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path(
                    'remove_relationship_operation')

        node_mapping = {
            'target': 'site1',
            'source': 'site2'
        }

        operation_id = 'custom_lifecycle.custom_operation'

        base_nodes, base_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        dep_update = \
            self.client.deployment_updates.update_with_existing_blueprint(
                deployment.id, BLUEPRINT_ID)

        # wait for 'update' workflow to finish
        self._wait_for_execution_to_terminate(deployment.id, 'update')
        self._wait_for_successful_state(dep_update.id)

        execution = self.client.executions.start(
                deployment.id,
                'custom_workflow',
                parameters={'node_id': 'site2'}
        )
        self._wait_for_execution_to_terminate(deployment.id, 'custom_workflow')
        execution = self.client.executions.get(execution.id)
        self.assertEqual(execution.status, 'failed')
        self.assertIn('{0} operation of node instance {1} does not exist'
                      .format(operation_id,
                              base_node_instances['source'][0]['id']),
                      execution.error)

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
                excluded_items=['relationships']
        )

        # Check that there is only 1 from each
        self.assertEqual(1, len(modified_nodes['target']))
        self.assertEqual(1, len(modified_node_instances['target']))
        self.assertEqual(1, len(modified_nodes['source']))
        self.assertEqual(1, len(modified_node_instances['source']))

        # get the nodes and node instances
        source_node = modified_nodes['source'][0]
        source_node_instance = modified_node_instances['source'][0]

        # assert there are 0 relationships
        self.assertEqual(1, len(source_node.relationships))
        self.assertEqual(1, len(source_node_instance.relationships))

        # check the new relationship between site2 and site1 is in place
        self._assert_relationship(
                source_node_instance.relationships,
                target='site1',
                expected_type='new_relationship_type')
        self._assert_relationship(
                source_node.relationships,
                target='site1',
                expected_type='new_relationship_type')

        # check all operation have been executed
        source_operations = \
            source_node['relationships'][0]['source_operations']
        self.assertNotIn(operation_id, source_operations)

    def test_remove_property(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('remove_property')

        node_mapping = {'affected_node': 'site1'}

        base_nodes, base_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)
        base_node = base_nodes['affected_node'][0]

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        dep_update = \
            self.client.deployment_updates.update_with_existing_blueprint(
                deployment.id, BLUEPRINT_ID)

        # wait for 'update' workflow to finish
        self._wait_for_execution_to_terminate(deployment.id, 'update')
        self._wait_for_successful_state(dep_update.id)

        modified_nodes, modified_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)
        modified_node = modified_nodes['affected_node'][0]

        removed_property = modified_node['properties'].get('prop2')
        self.assertIsNone(removed_property)
        # assert nothing else changed
        self._assert_equal_dicts(base_node['properties'],
                                 modified_node['properties'],
                                 excluded_items=['prop2'])

        self._assert_equal_entity_dicts(base_nodes,
                                        modified_node,
                                        'affected_node',
                                        excluded_items=['properties'])

    def test_remove_output(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('remove_output')
        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        dep_update = \
            self.client.deployment_updates.update_with_existing_blueprint(
                deployment.id, BLUEPRINT_ID)

        # assert that 'update' workflow was executed
        self._wait_for_execution_to_terminate(deployment.id, 'update')
        self._wait_for_successful_state(dep_update.id)

        deployment = self.client.deployments.get(dep_update.deployment_id)
        self.assertNotIn('custom_output', deployment.outputs)

    @mark.skip
    def test_remove_description(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('remove_description')

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        dep_update = \
            self.client.deployment_updates.update_with_existing_blueprint(
                deployment.id, BLUEPRINT_ID)

        # assert that 'update' workflow was executed
        self._wait_for_execution_to_terminate(deployment.id, 'update')
        self._wait_for_successful_state(dep_update.id)

        deployment = self.client.deployments.get(dep_update.deployment_id)
        self.assertFalse(deployment.get('description'))
