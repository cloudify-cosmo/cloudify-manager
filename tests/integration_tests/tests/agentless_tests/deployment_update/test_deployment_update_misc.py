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
import pytest
from uuid import uuid4

from integration_tests.tests.utils import (
    wait_for_blueprint_upload,
    wait_for_deployment_deletion_to_complete
)
from . import DeploymentUpdateBase, BLUEPRINT_ID

pytestmark = pytest.mark.group_deployments


class TestDeploymentUpdateMisc(DeploymentUpdateBase):

    def test_deployment_updated_twice(self):
        base_bp_path = self._get_blueprint_path(
            'update_deployment_twice',
            'deployment_updated_twice_base.yaml')
        modification_bp_path = self._get_blueprint_path(
            'update_deployment_twice',
            'deployment_updated_twice_modification.yaml')
        remodification_bp_path = self._get_blueprint_path(
            'update_deployment_twice',
            'deployment_updated_twice_remodification.yaml')

        deployment, _ = self.deploy_application(base_bp_path,
                                                blueprint_id='start')
        # assert initial deployment state
        deployment = self.client.deployments.get(deployment.id)
        self._assertDictContainsSubset({'custom_output': {'value': 0}},
                                       deployment.outputs)
        self.assertNotIn('modified description', deployment.description)

        def update_deployment_wait_and_assert(dep,
                                              bp_path,
                                              expected_output_value,
                                              is_description_modified,
                                              blueprint_id):
            self.client.blueprints.upload(bp_path, blueprint_id)
            wait_for_blueprint_upload(blueprint_id, self.client)
            self._do_update(dep.id, blueprint_id)

            # verify deployment output
            dep = self.client.deployments.get(deployment.id)
            self._assertDictContainsSubset(
                {'custom_output': {'value': expected_output_value}},
                dep.outputs)
            # verify deployment description
            self.assertEqual('modified description' in dep.description,
                             is_description_modified)

        self.assertEqual(
            self.client.deployments.get(deployment.id).blueprint_id, 'start')

        # modify output and verify
        update_deployment_wait_and_assert(
            deployment, modification_bp_path, 1, False, 'first')
        self.assertEqual(
            self.client.deployments.get(deployment.id).blueprint_id, 'first')

        # modify output again and modify description
        update_deployment_wait_and_assert(
            deployment, remodification_bp_path, 2, True, 'second')
        self.assertEqual(
            self.client.deployments.get(deployment.id).blueprint_id, 'second')

    def test_modify_deployment_update_schema(self):
        # this test verifies that storage (elasticsearch) can deal with
        # deployment update objects with varying schema
        base_bp_path = self._get_blueprint_path(
            'modify_deployment_update_schema',
            'modify_deployment_update_schema_base.yaml')
        modification_bp_path = self._get_blueprint_path(
            'modify_deployment_update_schema',
            'modify_deployment_update_schema_modification.yaml')
        remodification_bp_path = self._get_blueprint_path(
            'modify_deployment_update_schema',
            'modify_deployment_update_schema_remodification.yaml')

        deployment, _ = self.deploy_application(base_bp_path)
        # assert initial deployment state
        deployment = self.client.deployments.get(deployment.id)
        self._assertDictContainsSubset({'custom_output': {'value': '0.0.0.0'}},
                                       deployment.outputs)

        def update_deployment_wait_and_assert(dep,
                                              bp_path,
                                              expected_output_definition,
                                              expected_output_value):
            blueprint_id = 'b{0}'.format(uuid4())
            self.client.blueprints.upload(bp_path, blueprint_id)
            wait_for_blueprint_upload(blueprint_id, self.client)
            self._do_update(dep.id, blueprint_id)

            # verify deployment output value
            outputs = self.client.deployments.outputs.get(
                deployment.id).outputs
            self.assertDictEqual(
                {'custom_output': expected_output_value},
                outputs)
            # verify deployment output definition
            dep = self.client.deployments.get(deployment.id)
            self.assertDictEqual(
                {'custom_output': {'value': expected_output_definition}},
                dep.outputs)

        # modify once to create a DeploymentUpdate object with one
        # outputs schema
        update_deployment_wait_and_assert(
            deployment, modification_bp_path, '1.1.1.1', '1.1.1.1')
        # modify again to create a DeploymentUpdate object with a different
        # outputs schema
        update_deployment_wait_and_assert(
            deployment, remodification_bp_path,
            {'get_attribute': ['site1', 'ip']}, '2.2.2.2')

    def test_add_and_override_resource(self):
        """
        In order to test the resources mechanism
         1. we first upload the local_modification resource which
         increments the source_ops_counter each relationships operation
         executed between site2->site1
         2. we also upload the increment resource for future use.

            after this step we check that indeed the
            site2.source_ops_counter == 3

         2. after uploading the new blueprint (with its resources), the
         local_modification script decrements the same counter for each
         relationship operation executed between site2->site3 (since pre
         and post configure already ran, it should be ran only once)

         3. we set the increment script to be used for each operation
         between site3->site1

            after both of these steps we check that indeed the
            site2.source_ops_counter == 2
            and
            site3.source_ops_counter == 3
        :return:
        """
        deployment, modified_bp_path = self._deploy_and_get_modified_bp_path(
            'add_and_override_resource')

        node_mapping = {
            'stagnant': 'site1',
            'added_relationship': 'site2',
            'new': 'site3'
        }

        base_nodes, base_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)

        # check all operation have been executed
        self._assertDictContainsSubset(
            {'source_ops_counter': '3'},
            base_node_instances['added_relationship'][0]
            ['runtime_properties']
        )

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        self._do_update(deployment.id, BLUEPRINT_ID)

        # Get all related and affected nodes and node instances
        modified_nodes, modified_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)

        # get the nodes and node instances
        added_relationship_node_instance = \
            modified_node_instances['added_relationship'][0]
        new_node_instance = modified_node_instances['new'][0]

        # check all operation have been executed.
        # source_ops_counter was increased for each operation between site2 and
        # site1, and another site2.source_ops_counter should have
        # decreased once because of the resource override
        self._assertDictContainsSubset(
            {'source_ops_counter': '2'},
            added_relationship_node_instance['runtime_properties']
        )

        self._assertDictContainsSubset(
            {'source_ops_counter': '3'},
            new_node_instance['runtime_properties']
        )

    def test_use_new_and_old_inputs(self):
        """
        We first provide the os_family_input at the initial deployment
        creation. Then we add the ip_input. we use both only in the final
        blueprint. Note that it's not possible to overwrite inputs (and it
        wasn't tested).
        :return:
        """
        deployment, modified_bp_path = self._deploy_and_get_modified_bp_path(
            'use_new_and_old_inputs',
            inputs={'input_prop1': 'custom_input1',
                    'input_prop2': 'custom_input2'}
        )
        node_mapping = {'affected_node': 'site1'}

        base_nodes, base_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)
        base_node = base_nodes['affected_node'][0]
        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        self._do_update(deployment.id, BLUEPRINT_ID,
                        inputs={'input_prop3': 'custom_input3'})

        modified_nodes, modified_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)
        modified_node = modified_nodes['affected_node'][0]

        # Checking that get_property works correctly
        outputs_to_check = {
            'output_prop1': {
                'value': 'custom_input1'
            },
            'output_prop2': {
                'value': 'custom_input2'
            },
            'output_prop3': {
                'value': 'custom_input3'
            }
        }
        outputs = self.client.deployments.get(deployment.id).outputs
        self.assertEqual(outputs_to_check, outputs)

        # assert nothing else changed
        self._assert_equal_dicts(base_node,
                                 modified_node,
                                 excluded_items=['properties', 'blueprint_id'])
        self._assert_equal_dicts(
            base_node['properties'],
            modified_node['properties'],
            excluded_items=['prop1', 'prop2', 'prop3', 'blueprint_id']
        )

    def test_execute_custom_workflow(self):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('execute_custom_workflow')

        node_mapping = {'intact': 'site1'}

        base_nodes, base_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        dep_update = self._do_update(deployment.id, BLUEPRINT_ID,
                                     workflow_id='custom_workflow')

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

        intact_node_instance = modified_node_instances['intact'][0]

        self._assertDictContainsSubset(
            {'update_id': dep_update.id},
            intact_node_instance.runtime_properties
        )

        workflows = [e['workflow_id'] for e in
                     self.client.executions.list(deployment_id=deployment.id,
                                                 _include=['workflow_id'])]

        self.assertNotIn('update', workflows)
        self.assertIn('custom_workflow', workflows)

    def _test_skip_install(self, skip):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('skip_install')

        node_mapping = {
            'intact': 'site1',
            'removed': 'site2',
            'added': 'site3'
        }

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        self._do_update(deployment.id, BLUEPRINT_ID, skip_install=skip)

        modified_nodes, modified_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)

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

        # assert all operations in 'update' ('install') haven't ran
        self.assertNotIn('source_ops_counter',
                         added_instance['runtime_properties'])

        # assert not operation has affected target node
        add_related_instance = modified_node_instances['intact'][0]

        self._assertDictContainsSubset(
            {'uninstall_op_counter': '1'},
            add_related_instance['runtime_properties']
        )

        return add_related_instance

    def test_skip_install_true(self):
        instance_to_check = self._test_skip_install(skip=True)
        self.assertNotIn('install_op_counter',
                         instance_to_check['runtime_properties'])

    def test_skip_install_false(self):
        instance_to_check = self._test_skip_install(skip=False)
        self._assertDictContainsSubset(
            {'install_op_counter': '3'},
            instance_to_check['runtime_properties']
        )

    def _test_skip_uninstall(self, skip):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('skip_uninstall')

        node_mapping = {
            'remove_related': 'site1',
            'removed': 'site2',
            'added': 'site3'
        }

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        self._do_update(deployment.id, BLUEPRINT_ID, skip_uninstall=skip)

        modified_nodes, modified_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)

        # assert all operations in 'update' ('install') workflow
        # are executed by making them increment a runtime property
        related_instance = modified_node_instances['remove_related'][0]
        self._assertDictContainsSubset({'install_op_counter': '1'},
                                       related_instance['runtime_properties'])
        return related_instance

    def test_skip_uninstall_true(self):
        instance_to_check = self._test_skip_uninstall(skip=True)
        self.assertNotIn('uninstall_op_counter',
                         instance_to_check['runtime_properties'])

    def test_skip_uninstall_false(self):
        instance_to_check = self._test_skip_uninstall(skip=False)
        self._assertDictContainsSubset(
            {'uninstall_op_counter': '1'},
            instance_to_check['runtime_properties']
        )

    def _test_skip_install_and_uninstall(self, skip):
        deployment, modified_bp_path = \
            self._deploy_and_get_modified_bp_path('skip_install_and_uninstall')

        node_mapping = {
            'removed': 'site1',
            'modified': 'site2',
            'added': 'site3'
        }

        self.client.blueprints.upload(modified_bp_path, BLUEPRINT_ID)
        wait_for_blueprint_upload(BLUEPRINT_ID, self.client)
        self._do_update(deployment.id, BLUEPRINT_ID,
                        skip_install=skip, skip_uninstall=skip)

        modified_nodes, modified_node_instances = \
            self._map_node_and_node_instances(deployment.id, node_mapping)

        # assert not operation has affected target node
        return modified_node_instances['modified'][0]

    def test_skip_install_and_uninstall_true(self):

        modified_instance = self._test_skip_install_and_uninstall(skip=True)
        self.assertNotIn('install_op_counter',
                         modified_instance['runtime_properties'])
        self.assertNotIn('uninstall_op_counter',
                         modified_instance['runtime_properties'])

    def test_skip_install_and_uninstall_false(self):
        modified_instance = self._test_skip_install_and_uninstall(skip=False)
        self._assertDictContainsSubset(
            {'install_op_counter': '1'},
            modified_instance['runtime_properties']
        )
        self._assertDictContainsSubset(
            {'uninstall_op_counter': '1'},
            modified_instance['runtime_properties']
        )

    def test_remove_deployment(self):
        """
        Tests whether deployment updates are deleted together with the
        deployment.
        :return:
        """
        del_deployment, mod_del_dep_bp1 = \
            self._deploy_and_get_modified_bp_path('remove_deployment',
                                                  deployment_id='del_dep')

        undel_deployment, mod_undel_dep_bp1 = \
            self._deploy_and_get_modified_bp_path('remove_deployment',
                                                  deployment_id='undel_dep')

        blu_id = BLUEPRINT_ID + '-del-1'
        self.client.blueprints.upload(mod_del_dep_bp1, blu_id)
        wait_for_blueprint_upload(blu_id, self.client)
        del_dep_update1 = self._do_update(del_deployment.id, blu_id)

        blu_id = BLUEPRINT_ID + '-undel-1'
        self.client.blueprints.upload(mod_undel_dep_bp1, blu_id)
        wait_for_blueprint_upload(blu_id, self.client)
        undel_dep_update = self._do_update(undel_deployment.id, blu_id)

        mod_del_dep_bp2 = self._get_blueprint_path(
            os.path.join('remove_deployment', 'modification2'),
            'remove_deployment_modification2.yaml')
        blu_id = BLUEPRINT_ID + '-del-2'
        self.client.blueprints.upload(mod_del_dep_bp2, blu_id)
        wait_for_blueprint_upload(blu_id, self.client)
        del_dep_update2 = self._do_update(del_deployment.id, blu_id)

        deployment_update_list = self.client.deployment_updates.list(
            deployment_id=del_deployment.id,
            _include=['id']
        )

        self.assertEqual(len(deployment_update_list.items), 2)
        self.assertEqual(
            {d['id'] for d in deployment_update_list},
            {del_dep_update1.id, del_dep_update2.id}
        )

        # Delete deployment and assert deployment updates were removed
        uninstall = self.client.executions.start(
            del_deployment.id, 'uninstall')
        self.wait_for_execution_to_end(uninstall)

        self.client.deployments.delete(del_deployment.id)
        wait_for_deployment_deletion_to_complete(
            del_deployment.id, self.client
        )
        deployment_update_list = self.client.deployment_updates.list(
            deployment_id=del_deployment.id,
            _include=['id']
        )
        self.assertEqual(len(deployment_update_list.items), 0)

        # Assert no other deployment updates were deleted
        deployment_update_list = self.client.deployment_updates.list(
            deployment_id=undel_deployment.id,
            _include=['id']
        )
        self.assertEqual(len(deployment_update_list), 1)
        self.assertEqual(deployment_update_list[0]['id'], undel_dep_update.id)

    def test_update_group(self):
        self.upload_blueprint_resource(
            'dsl/deployment_update/add_description/base/'
            'add_description_base.yaml',
            'bp1'
        )
        self.upload_blueprint_resource(
            'dsl/deployment_update/add_description/modification/'
            'add_description_modification.yaml',
            'bp2'
        )
        group = self.client.deployment_groups.put(
            'g1',
            blueprint_id='bp1',
            new_deployments=[{}] * 5
        )
        self.assertEqual(len(group.deployment_ids), 5)
        create_dep_env_group = self.client.execution_groups.list(
            deployment_group_id='g1',
            workflow_id='create_deployment_environment'
        )[0]
        self.wait_for_execution_to_end(create_dep_env_group, is_group=True)
        update_group = self.client.execution_groups.start(
            deployment_group_id='g1',
            workflow_id='csys_update_deployment',
            default_parameters={
                'blueprint_id': 'bp2',
            }
        )
        self.wait_for_execution_to_end(update_group, is_group=True)
        update_group = self.client.execution_groups.get(update_group['id'])
        self.assertEqual(len(update_group.execution_ids), 10)
        for deployment_id in group.deployment_ids:
            dep = self.client.deployments.get(deployment_id)
            self.assertIn('description', dep.description)


class NewTestDeploymentUpdateMisc(DeploymentUpdateBase):
    test_deployment_updated_twice = TestDeploymentUpdateMisc.test_deployment_updated_twice
    test_modify_deployment_update_schema = TestDeploymentUpdateMisc.test_modify_deployment_update_schema
    test_add_and_override_resource = TestDeploymentUpdateMisc.test_add_and_override_resource

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
