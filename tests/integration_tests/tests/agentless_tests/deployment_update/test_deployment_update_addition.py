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

import os
import shutil
import pytest
import tempfile

from pytest import mark

from integration_tests.tests.utils import (tar_blueprint,
                                           wait_for_blueprint_upload)
from . import DeploymentUpdateBase, BLUEPRINT_ID


pytestmark = pytest.mark.group_deployments


class TestDeploymentUpdateAddition(DeploymentUpdateBase):

    def test_add_node_bp(self):
        self._test_add_node(archive_mode=False)

    def test_add_node_archive(self):
        self._test_add_node(archive_mode=True)

    def _test_add_node(self, archive_mode=False):
        """
        add a node (type exists) which is contained in an existing node
        - assert that both node and node instance have been created
        - assert the node/instance relationships have been created
        - assert the 'update' workflow has been executed and
          all related operations were executed as well
        """

        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('add_node')

        node_mapping = {
            'intact': 'site1',
            'added': 'site2'
        }

        base_nodes, base_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)

        tempdir = tempfile.mkdtemp()
        try:
            if archive_mode:
                tar_path = tar_blueprint(modified_bp_path, tempdir)
                self.client.blueprints.publish_archive(tar_path,
                                                       BLUEPRINT_ID,
                                                       os.path.basename(
                                                           modified_bp_path))
            else:
                self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
            wait_for_blueprint_upload(BLUEPRINT_ID, self.client)

            # an update preview should have no effect
            self._do_update(deployment.id, BLUEPRINT_ID, preview=True)

            unmodified_nodes, unmodified_node_instances = \
                self._map_node_and_node_instances(deployment.id, node_mapping)

            # assert all unaffected nodes and node instances remained intact
            self._assert_equal_entity_dicts(
                base_nodes,
                unmodified_nodes,
                keys=['intact', 'added'],
                excluded_items=['runtime_properties', 'plugins']
            )

            self._assert_equal_entity_dicts(
                base_node_instances,
                unmodified_node_instances,
                keys=['intact', 'added'],
                excluded_items=['runtime_properties']
            )

            # assert that node and node instance were not added to storage
            self.assertEqual(0, len(unmodified_nodes['added']))
            self.assertEqual(0, len(unmodified_node_instances['added']))

            self._do_update(deployment.id, BLUEPRINT_ID)

            modified_nodes, modified_node_instances = \
                self._map_node_and_node_instances(deployment.id, node_mapping)

            # assert all unaffected nodes and node instances remained intact
            self._assert_equal_entity_dicts(
                    base_nodes,
                    modified_nodes,
                    keys=['intact', 'added'],
                    excluded_items=['runtime_properties', 'plugins']
            )

            self._assert_equal_entity_dicts(
                    base_node_instances,
                    modified_node_instances,
                    keys=['intact', 'added'],
                    excluded_items=['runtime_properties']
            )

            # assert that node and node instance were added to storage
            self.assertEqual(1, len(modified_nodes['added']))
            self.assertEqual(1, len(modified_node_instances['added']))

            # assert that node has a relationship
            node = modified_nodes['added'][0]
            self.assertEqual(1, len(node.relationships))
            self._assert_relationship(
                    node.relationships,
                    target='site1',
                    expected_type='cloudify.relationships.contained_in')
            self.assertEqual(node.type, 'cloudify.nodes.WebServer')

            # assert that node instance has a relationship
            added_instance = modified_node_instances['added'][0]
            self.assertEqual(1, len(added_instance.relationships))
            self._assert_relationship(
                    added_instance.relationships,
                    target='site1',
                    expected_type='cloudify.relationships.contained_in')

            # assert all operations in 'update' ('install') workflow
            # are executed by making them increment a runtime property
            self._assertDictContainsSubset(
                {'source_ops_counter': '6'},
                added_instance['runtime_properties'])

            # assert operations affected the target node as well
            add_related_instance = \
                self.client.node_instances.list(deployment_id=deployment.id,
                                                node_id='site1')[0]
            self._assertDictContainsSubset(
                    {'target_ops_counter': '3'},
                    add_related_instance['runtime_properties']
            )
        finally:
            shutil.rmtree(tempdir, ignore_errors=True)

    def test_install_execution_order(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('install_execution_order')
        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        self._do_update(deployment.id, BLUEPRINT_ID)

        self.assertFalse(self.client.node_instances.list(
                node_id='site2').items[0].runtime_properties['is_op_started'],
                         'Site3 operations were executed '
                         'before/simultaneously with Site2 operations, '
                         'although site3 connected_to site2')

    def test_add_node_operation(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('add_node_operation')

        node_mapping = {'modified': 'site1'}

        operation_id = 'custom_lifecycle.custom_operation'

        base_nodes, base_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        self._do_update(deployment.id, BLUEPRINT_ID)

        # assert nothing changed except for plugins and operations
        modified_nodes, modified_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)

        self._assert_equal_entity_dicts(
                base_nodes,
                modified_nodes,
                keys=['modified'],
                excluded_items=['plugins', 'operations']
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
                parameters={'operation': operation_id}
        )
        self.wait_for_execution_to_end(execution)

        # Check again for the nodes and node instances and check
        # their runtime properties
        modified_nodes, modified_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)

        self.assertEqual(len(modified_nodes['modified']), 1)
        added_node = modified_nodes['modified'][0]
        self.assertEqual(len(modified_node_instances['modified']), 1)
        added_node_instance = modified_node_instances['modified'][0]

        self._assert_equal_entity_dicts(
                base_nodes,
                modified_nodes,
                keys=['modified'],
                excluded_items=['plugins', 'operations']
        )

        self._assert_equal_entity_dicts(
                base_node_instances,
                modified_node_instances,
                keys=['modified'],
                excluded_items=['runtime_properties']
        )

        affected_lifecycle_operation = \
            added_node['operations'].get(operation_id)
        self.assertIsNotNone(affected_lifecycle_operation)

        self._assertDictContainsSubset(
                {'source_ops_counter': '1'},
                added_node_instance['runtime_properties']
        )

    def test_add_node_with_multiple_instances(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('add_node_'
                                                  'with_multiple_instances')

        node_mapping = {
            'intact': 'site1',
            'added': 'site2'
        }

        base_nodes, base_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        self._do_update(deployment.id, BLUEPRINT_ID)

        modified_nodes, modified_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)

        # assert all unaffected nodes and node instances remained intact
        self._assert_equal_entity_dicts(
                base_nodes,
                modified_nodes,
                keys=['intact'],
        )

        self._assert_equal_entity_dicts(
                base_node_instances,
                modified_node_instances,
                keys=['intact'],
                excluded_items=['runtime_properties']
        )

        # assert that node and node instance were added to storage
        self.assertEqual(1, len(modified_nodes['added']))
        self.assertEqual(3, len(modified_node_instances['added']))

        # assert that node has a relationship
        for node in modified_nodes['added']:
            self.assertEqual(1, len(node.relationships))
            self._assert_relationship(
                    node.relationships,
                    target='site1',
                    expected_type='cloudify.relationships.contained_in')
            self.assertEqual(node.type, 'cloudify.nodes.WebServer')

        # assert that node instance has a relationship
        for added_instance in modified_node_instances['added']:
            self.assertEqual(1, len(added_instance.relationships))
            self._assert_relationship(
                    added_instance.relationships,
                    target='site1',
                    expected_type='cloudify.relationships.contained_in')

            # assert all operations in 'update' ('install') workflow
            # are executed by making them increment a runtime property
            self._assertDictContainsSubset(
                {'source_ops_counter': '6'},
                added_instance['runtime_properties'])

    def test_add_relationship(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('add_relationship')

        node_mapping = {
            'related': 'site1',
            'target': 'site2',
            'source': 'site3'
        }

        base_nodes, base_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)

        # check that the relationship operation between site3 and site 1
        # ran only once (at bp)
        self._assertDictContainsSubset(
                {'target_ops_counter': '1'},
                base_node_instances['related'][0]['runtime_properties']
        )

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        self._do_update(deployment.id, BLUEPRINT_ID)

        modified_nodes, modified_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)

        # assert all unaffected nodes and node instances remained intact
        self._assert_equal_entity_dicts(
                base_nodes,
                modified_nodes,
                keys=['related', 'target', 'source'],
                excluded_items=['runtime_properties',
                                'plugins',
                                'relationships']
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
        related_node_instance = modified_node_instances['related'][0]
        target_node_instance = modified_node_instances['target'][0]
        source_node = modified_nodes['source'][0]
        source_node_instance = modified_node_instances['source'][0]

        # assert there are 2 relationships total
        self.assertEqual(2, len(source_node.relationships))
        self.assertEqual(2, len(source_node_instance.relationships))

        # check the relationship between site2 and site0 is intact
        self._assert_relationship(
                source_node_instance.relationships,
                target='site1',
                expected_type='cloudify.relationships.connected_to')
        self._assert_relationship(
                source_node.relationships,
                target='site1',
                expected_type='cloudify.relationships.connected_to')

        # check the new relationship between site2 and site1 is in place
        self._assert_relationship(
                source_node_instance.relationships,
                target='site2',
                expected_type='new_relationship_type')
        self._assert_relationship(
                source_node.relationships,
                target='site2',
                expected_type='new_relationship_type')

        # check that the relationship operation between site3 and site 1
        # ran only once (at bp)
        self._assertDictContainsSubset(
                {'target_ops_counter': '1'},
                related_node_instance['runtime_properties']
        )

        # check all operation have been executed
        self._assertDictContainsSubset(
                {'source_ops_counter': '1'},
                source_node_instance['runtime_properties']
        )

        self._assertDictContainsSubset(
                {'target_ops_counter': '1'},
                target_node_instance['runtime_properties']
        )

    def test_add_relationship_operation(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('add_relationship_operation')

        operation_id = 'custom_lifecycle.custom_operation'
        node_mapping = {
            'target': 'site1',
            'source': 'site2'
        }
        base_nodes, base_node_instances = \
            self._map_node_and_node_instances(
                    deployment.id, node_mapping)

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        self._do_update(deployment.id, BLUEPRINT_ID)

        execution = self.client.executions.start(
            deployment.id, 'custom_workflow', parameters={'node_id': 'site2'})
        self.wait_for_execution_to_end(execution)

        modified_nodes, modified_node_instances = \
            self._map_node_and_node_instances(
                    deployment.id, node_mapping)

        # assert all unaffected nodes and node instances remained intact
        self._assert_equal_entity_dicts(
                base_nodes,
                modified_nodes,
                keys=['target', 'source'],
                excluded_items=['relationships', 'plugins']
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
                                           'increment.sh'])

        # check all operation have been executed
        source_operations = \
            source_node['relationships'][0]['source_operations']
        self._assertDictContainsSubset(dict_to_check,
                                       source_operations[operation_id])
        self._assertDictContainsSubset(
                dict_to_check,
                source_operations[operation_id]
        )

        self._assertDictContainsSubset(
                {'source_ops_counter': '1'},
                modified_node_instances['source'][0]['runtime_properties']
        )

    def test_add_property(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('add_property')

        node_mapping = {
            'affected_node': 'site1'
        }

        base_nodes, base_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)
        base_node = base_nodes['affected_node'][0]

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        self._do_update(deployment.id, BLUEPRINT_ID)

        modified_nodes, modified_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)
        modified_node = modified_nodes['affected_node'][0]

        added_property = modified_node['properties'].get('prop2')
        self.assertIsNotNone(added_property)
        self.assertEqual(added_property, 'value2')

        # assert nothing else changed
        self._assert_equal_dicts(base_node['properties'],
                                 modified_node['properties'],
                                 excluded_items=['prop2'])
        self._assert_equal_entity_dicts(base_nodes,
                                        modified_node,
                                        'affected_node',
                                        excluded_items=['properties'])

    def test_add_workflow(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('add_workflow')
        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        dep_update = self._do_update(deployment.id, BLUEPRINT_ID)

        execution = self.client.executions.start(
            dep_update.deployment_id,
            workflow_id='my_custom_workflow',
            parameters={
                'node_id': 'site1',
                'delta': 2
            }
        )
        self.wait_for_execution_to_end(execution)

        affected_node = self.client.node_instances.list(
            deployment_id=dep_update.deployment_id,
            node_id='site1'
        )
        self.assertEqual(len(affected_node), 3)
        deployment = self.client.deployments.get(dep_update.deployment_id)
        self.assertIn('my_custom_workflow',
                      [w['name'] for w in deployment.workflows])

    def test_add_output(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('add_output')
        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        dep_update = self._do_update(deployment.id, BLUEPRINT_ID)
        deployment = self.client.deployments.get(dep_update.deployment_id)
        self._assertDictContainsSubset({'custom_output': {'value': 0}},
                                       deployment.outputs)

    @mark.skip
    def test_add_description(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('add_description')

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        dep_update = self._do_update(deployment.id, BLUEPRINT_ID)

        deployment = self.client.deployments.get(dep_update.deployment_id)
        self.assertRegexpMatches(deployment['description'], 'new description')
