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

from collections import Counter

from cloudify_rest_client.exceptions import CloudifyClientError

from . import DeploymentUpdateBase, BLUEPRINT_ID
from integration_tests.tests.utils import wait_for_blueprint_upload
from integration_tests.tests.utils import get_resource as resource

pytestmark = pytest.mark.group_deployments


class TestDeploymentUpdateModification(DeploymentUpdateBase):
    def test_scale(self):
        # this test is WIP; it will be checking more things than just
        # the declared numbers.
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('scale_instance')

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)

        expected_instances = {
            'site1': 1,
            'site2': 3,
        }
        nodes = self.client.nodes.list(deployment_id=deployment.id)
        instance_counts = Counter(
            ni['node_id'] for ni in self.client.node_instances.list()
        )
        assert expected_instances == {
            n['id']: n['deploy_number_of_instances'] for n in nodes
        }
        assert instance_counts == expected_instances
        self._do_update(deployment.id, BLUEPRINT_ID)
        nodes = self.client.nodes.list(deployment_id=deployment.id)
        instance_counts = Counter(
            ni['node_id'] for ni in self.client.node_instances.list()
        )
        expected_instances = {
            'site1': 3,
            'site2': 1,
        }
        assert expected_instances == {
            n['id']: n['deploy_number_of_instances'] for n in nodes
        }
        assert instance_counts == expected_instances

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

    def test_modify_idd(self):
        shared_bp_path = resource(
            'dsl/deployment_update/modify_idd/shared.yaml')
        self.deploy_application(shared_bp_path, 240, 'shared1', 'shared1')
        self.deploy_application(shared_bp_path, 240, 'shared2', 'shared2')
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('modify_idd')
        idds = self.client.inter_deployment_dependencies.list(
            source_deployment_id=deployment.id)
        assert len(idds) == 2  # sharedresource + get_capability

        self.client.inter_deployment_dependencies.create(
            dependency_creator='custom.idd',
            source_deployment=idds[0].source_deployment_id,
            target_deployment=idds[0].target_deployment_id,
        )
        idds = self.client.inter_deployment_dependencies.list(
            source_deployment_id=deployment.id)
        assert len(idds) == 3  # sharedresource + get_capability + custom

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        self._do_update(deployment.id, BLUEPRINT_ID)

        idds = self.client.inter_deployment_dependencies.list(
            source_deployment_id=deployment.id)
        assert len(idds) == 3
        assert any(idd.dependency_creator == 'custom.idd' for idd in idds)

    def test_modify_capability(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('modify_capability')

        deployment = self.client.deployments.get(deployment.id)
        self.assertEqual(deployment.capabilities, {
            'cap1': {'value': 0},
            'cap2': {'value': 0},
        })

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        self._do_update(deployment.id, BLUEPRINT_ID)

        deployment = self.client.deployments.get(deployment.id)
        self.assertEqual(deployment.capabilities, {
            'cap1': {'value': 1},
            'cap3': {'value': 1},
        })

    def test_modify_labels(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('modify_labels')

        deployment = self.client.deployments.get(deployment.id)
        self.assertEqual(
            {(lab.key, lab.value) for lab in deployment.labels},
            {('label1', 'value1'), ('label1', 'value2'), ('label2', 'value1')}
        )

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        self._do_update(deployment.id, BLUEPRINT_ID)

        deployment = self.client.deployments.get(deployment.id)
        self.assertEqual(
            {(lab.key, lab.value) for lab in deployment.labels},
            # we're keeping the labels that disappeared from the new blueprint
            # as well - we don't know if maybe the user added them explicitly
            {('label1', 'value1'), ('label1', 'value2'), ('label1', 'value3'),
             ('label2', 'value1'), ('label3', 'value1')}
        )

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
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('modify_inputs')
        self.assertEqual(deployment['inputs'], {
            'test_list': 'initial_input',
            'test_string_toremove': 'xxx'
        })

        new_test_list = ['update_input3', 'update_input4']
        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        dep_update = self._do_update(
            deployment.id, BLUEPRINT_ID, inputs={'test_list': new_test_list})

        execution = self.client.executions.get(dep_update.execution_id)
        self.assertEqual(execution.status, 'terminated')

        # verify if inputs have been updated
        deployment = self.client.deployments.get(deployment.id)
        self.assertEqual(deployment['inputs'], {
            'test_list': new_test_list,
            'test_string_new': 'xxx',
            # test_string_toremove was removed!
        })

        # verify reinstall-(un)install tasks graphs were generated
        self.assertEqual(len(self.client.tasks_graphs.list(
            execution.id, 'reinstall-uninstall')), 1)
        self.assertEqual(len(self.client.tasks_graphs.list(
            execution.id, 'reinstall-install')), 1)

        # verify steps that have been logged
        event_messages = [re.match(r'^(\ ?\w+)+', et['message']).
                          group() for et in self.client.events.list(
            execution_id=execution.id,
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

    def test_enable_workflow(self):
        bp_template = """
tosca_definitions_version: cloudify_dsl_1_4

imports:
    - cloudify/types/types.yaml

workflows:
    wf1:
        mapping: file:///dev/null
        availability_rules:
            available: {available}
"""
        base_bp_path = \
            self.make_yaml_file(bp_template.format(available=False))
        modified_bp_path = \
            self.make_yaml_file(bp_template.format(available=True))
        deployment, _ = self.deploy_application(base_bp_path)

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        with self.assertRaises(CloudifyClientError) as cm:
            self.execute_workflow('wf1', deployment.id)
        assert cm.exception.error_code == 'unavailable_workflow_error'
        self._do_update(deployment.id, BLUEPRINT_ID)
        self.execute_workflow('wf1', deployment.id)  # doesn't throw
