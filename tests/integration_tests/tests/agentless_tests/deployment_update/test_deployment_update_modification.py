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

import re
import pytest

from . import DeploymentUpdateBase, BLUEPRINT_ID
from integration_tests.tests.utils import wait_for_blueprint_upload

pytestmark = pytest.mark.group_deployments


class TestDeploymentUpdateModification(DeploymentUpdateBase):
    _workflow_name = 'update'

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
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)

        # an update preview should have no effect (many times)
        for _ in range(5):
            self._do_update(deployment.id, BLUEPRINT_ID, preview=True)

        self._do_update(deployment.id, BLUEPRINT_ID)

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
        self.assertEqual(2, len(modified_source_node.relationships))
        self.assertEqual(2, len(modified_source_node_instance.relationships))

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
        execution = self.client.executions.start(
                deployment.id,
                'execute_operation',
                parameters={
                    'operation': 'cloudify.interfaces.lifecycle.stop'
                }
        )
        self.wait_for_execution_to_end(execution)

        base_nodes, base_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)

        self._assertDictContainsSubset(
                {'source_ops_counter': '1'},
                base_node_instances['modified'][0]['runtime_properties']
        )

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        self._do_update(deployment.id, BLUEPRINT_ID, skip_reinstall=True)

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
        execution = self.client.executions.start(
                deployment.id,
                'execute_operation',
                parameters={
                    'operation': 'cloudify.interfaces.lifecycle.stop'
                }
        )
        self.wait_for_execution_to_end(execution)

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

        self._assertDictContainsSubset(
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
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        self._do_update(deployment.id, BLUEPRINT_ID)

        execution = self.client.executions.start(
            deployment.id, 'custom_workflow', parameters={'node_id': 'site2'})
        self.wait_for_execution_to_end(execution)

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
        self.assertEqual(1, len(modified_nodes['target']))
        self.assertEqual(1, len(modified_node_instances['target']))
        self.assertEqual(1, len(modified_nodes['source']))
        self.assertEqual(1, len(modified_node_instances['source']))

        # get the nodes and node instances
        source_node = modified_nodes['source'][0]
        source_node_instance = modified_node_instances['source'][0]

        # assert there are 1 relationships
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

        dict_to_check = self._create_dict(['inputs', 'script_path',
                                           'decrement.sh'])

        self._assertDictContainsSubset(
                {'source_ops_counter': '-1'},
                source_node_instance['runtime_properties']
        )

        # check all operation have been executed
        source_operations = \
            source_node['relationships'][0]['source_operations']
        self._assertDictContainsSubset(dict_to_check,
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
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        self._do_update(deployment.id, BLUEPRINT_ID)

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
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        self._do_update(deployment.id, BLUEPRINT_ID)

        execution = self.client.executions.start(
            deployment.id,
            workflow_id='my_custom_workflow',
            parameters={'node_id': 'site1'})
        self.wait_for_execution_to_end(execution)

        affected_node = self.client.node_instances.list(
            deployment_id=deployment.id,
            node_id='site1'
        )
        self.assertEqual(len(affected_node), 6)
        deployment = self.client.deployments.get(deployment.id)
        self.assertIn('my_custom_workflow',
                      [w['name'] for w in deployment.workflows])

    def test_modify_output(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('modify_output')

        deployment = self.client.deployments.get(deployment.id)
        self._assertDictContainsSubset({'custom_output': {'value': 0}},
                                       deployment.outputs)

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        self._do_update(deployment.id, BLUEPRINT_ID)

        deployment = self.client.deployments.get(deployment.id)
        self._assertDictContainsSubset({'custom_output': {'value': 1}},
                                       deployment.outputs)

    def test_modify_description(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('modify_description')

        self.assertRegexpMatches(deployment['description'], 'old description')

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        self._do_update(deployment.id, BLUEPRINT_ID)

        deployment = self.client.deployments.get(deployment.id)
        self.assertRegexpMatches(deployment['description'], 'new description')

    def test_modify_inputs_ops_order(self):
        """Verify that update workflow executes uninstall and install."""
        deployment, _ = \
            self._deploy_and_get_modified_bp_path('modify_inputs')
        self.assertEqual(deployment['inputs'], {
            u'test_list': u'initial_input'})

        new_test_list = [u'update_input1', u'update_input2']
        self._do_update(
            deployment.id, inputs={u'test_list': new_test_list})

        execution_ids = [en.id for en in self.client.executions.list(
            deployment_id=deployment.id,
            workflow_id=self._workflow_name,
            status='terminated',
        )]
        self.assertEqual(len(execution_ids), 1)

        # verify if inputs have been updated
        deployment = self.client.deployments.get(deployment.id)
        self.assertEqual(deployment['inputs'], {u'test_list': new_test_list})

        # verify reinstall-(un)install tasks graphs were generated
        self.assertEqual(len(self.client.tasks_graphs.list(
            execution_ids[0], 'reinstall-uninstall')), 1)
        self.assertEqual(len(self.client.tasks_graphs.list(
            execution_ids[0], 'reinstall-install')), 1)

        # verify steps that have been logged
        event_messages = [re.match(r'^(\ ?\w+)+', et['message']).
                          group() for et in self.client.events.list(
            execution_id=execution_ids[0],
            event_type='workflow_node_event',
            sort='reported_timestamp',
        )]
        self.assertIn(u'Stopping node instance', event_messages)
        self.assertIn(u'Deleted node instance', event_messages)
        self.assertIn(u'Node instance started', event_messages)
        self.assertLess(event_messages.index(u'Stopping node instance'),
                        event_messages.index(u'Deleted node instance'))
        self.assertLess(event_messages.index(u'Deleted node instance'),
                        event_messages.index(u'Node instance started'))


class NewTestDeploymentUpdateModification(TestDeploymentUpdateModification):
    _workflow_name = 'csys_new_deployment_update'
    def _do_update(self, deployment_id, blueprint_id=None,
                   preview=False, inputs=None, skip_reinstall=False, **kwargs):
        params = {
            'blueprint_id': blueprint_id,
        }
        if preview:
            params['preview'] = preview
        if inputs:
            params['inputs'] = inputs
        if skip_reinstall:
            params['skip_reinstall'] = skip_reinstall
        exc = self.client.executions.start(
            deployment_id, 'csys_new_deployment_update', parameters=params)
        self.wait_for_execution_to_end(exc)
