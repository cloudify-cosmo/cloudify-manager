#########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

import unittest

from os import path
from nose.plugins.attrib import attr

from cloudify_rest_client.exceptions import UserUnauthorizedError

from manager_rest.storage import models
from manager_rest.test.base_test import LATEST_API_VERSION

from .test_base import SecurityTestBase

RUNNING_EXECUTIONS_MESSAGE = 'There are running executions for this deployment'
UNAUTHORIZED_ERROR_MESSAGE = '401: User unauthorized'
NOT_FOUND_ERROR_MESSAGE = '404: Requested Blueprint with ID ' \
                          '`blueprint_id` was not found'


@attr(client_min_version=1, client_max_version=LATEST_API_VERSION)
class AuthorizationTests(SecurityTestBase):

    def setUp(self):
        super(AuthorizationTests, self).setUp()
        self.blueprint_path = path.join(
            self.get_blueprint_path('mock_blueprint'), 'empty_blueprint.yaml')

        self.admin_client = self.get_secured_client(
            username='alice', password='alice_password'
        )
        self.default_client = self.get_secured_client(
            username='bob', password='bob_password'
        )
        self.suspended_client = self.get_secured_client(
            username='clair', password='clair_password'
        )

    def test_blueprint_operations(self):
        # test
        self._test_upload_blueprints()
        self._test_list_blueprints()
        self._test_get_blueprints()
        self._test_delete_blueprints()

    def test_deployment_operations(self):
        # setup
        self.admin_client.blueprints.upload(
            self.blueprint_path, 'bp_example_1')
        # test
        self._test_create_deployments()
        self._test_list_deployments()
        self._test_get_deployments()
        self._test_delete_deployments()

    def test_execution_operations(self):
        # setup
        self.admin_client.blueprints.upload(
            self.blueprint_path, 'blueprint_1')
        self.admin_client.deployments.create('blueprint_1', 'deployment_1')
        self.admin_client.blueprints.upload(
            self.blueprint_path, 'blueprint_2')
        self.admin_client.deployments.create('blueprint_2', 'deployment_2')

        # test
        self._test_list_executions()
        execution1_id, execution2_id = self._test_start_executions()
        self._test_get_executions(execution1_id, execution2_id)
        self._test_update_executions(execution1_id)
        self._test_cancel_executions(execution1_id, execution2_id)

    def test_node_operations(self):
        # setup
        self.admin_client.blueprints.upload(
            self.blueprint_path, 'blueprint_1')
        self.admin_client.deployments.create('blueprint_1', 'deployment_1')

        # test
        self._test_list_nodes()
        self._test_get_nodes()

    def test_node_instance_operations(self):
        # setup
        self.admin_client.blueprints.upload(
            self.blueprint_path, 'blueprint_1')
        self.admin_client.deployments.create('blueprint_1', 'deployment_1')

        # test
        node_instances = self._test_list_node_instances()
        instance_id = self._test_get_node_instance(node_instances[0]['id'])
        self._test_update_node_instances(instance_id)

    def test_token_client_is_not_breaching(self):
        admin_token_client, default_token_client = self._test_get_token()
        self._test_blueprint_upload_with_token(admin_token_client,
                                               default_token_client)
        self._test_get_blueprint_with_token(admin_token_client,
                                            default_token_client)
        self._test_blueprint_list_with_token(admin_token_client,
                                             default_token_client)
        self._test_blueprint_delete_with_token(admin_token_client,
                                               default_token_client)

    @attr(client_min_version=2.1,
          client_max_version=LATEST_API_VERSION)
    # todo: mt: handle authorization
    @unittest.skip("temporarily disabled")
    def test_maintenance_mode(self):
        self._test_get_status_maintenance_mode()
        self._test_activate_maintenance_mode()
        self._test_deactivate_maintenance_mode()

    ##################
    # token methods
    ##################
    def _test_blueprint_upload_with_token(self,
                                          admin_token_client,
                                          default_token_client):
        # admins and default users should be able to upload blueprints...
        token_bp_example_1 = admin_token_client.blueprints.upload(
            self.blueprint_path, 'token_bp_example_1')
        self._assert_resource_id(token_bp_example_1, 'token_bp_example_1')
        token_bp_example_2 = default_token_client.blueprints.upload(
            self.blueprint_path, 'token_bp_example_2')
        self._assert_resource_id(token_bp_example_2, 'token_bp_example_2')

    def _test_get_token(self):
        # admins and default users should be able to get a token...
        admin_token = self.admin_client.tokens.get().value
        admin_token_client = self.get_secured_client(token=admin_token)
        default_token = self.default_client.tokens.get().value
        default_token_client = self.get_secured_client(token=default_token)

        # ... but suspended users should not be able to get a token
        self._assert_unauthorized(self.suspended_client.tokens.get)

        return admin_token_client, default_token_client

    def _test_blueprint_list_with_token(self,
                                        admin_token_client,
                                        default_token_client):
        # admins and default users should be able so list blueprints
        expected_ids = {'token_bp_example_1', 'token_bp_example_2'}
        blueprints_list = admin_token_client.blueprints.list()
        self._assert_resources_list_ids(blueprints_list, expected_ids)
        blueprints_list = default_token_client.blueprints.list()
        self._assert_resources_list_ids(blueprints_list, expected_ids)

    def _test_get_blueprint_with_token(self,
                                       admin_token_client,
                                       default_token_client):
        # admins and default users should be able so list blueprints
        blueprint = admin_token_client.blueprints.get('token_bp_example_1')
        self._assert_resource_id(blueprint, 'token_bp_example_1')
        blueprint = default_token_client.blueprints.get('token_bp_example_1')
        self._assert_resource_id(blueprint, 'token_bp_example_1')

    @staticmethod
    def _test_blueprint_delete_with_token(admin_token_client,
                                          default_token_client):
        # admins and default users should be able to delete a blueprint...
        admin_token_client.blueprints.delete('token_bp_example_1')
        default_token_client.blueprints.delete('token_bp_example_2')

    ####################
    # blueprint methods
    ####################
    def _test_upload_blueprints(self):
        # admins and default users should be able to upload blueprints...
        blueprint_1 = self.admin_client.blueprints.upload(
            self.blueprint_path, 'blueprint_1')
        self._assert_resource_id(blueprint_1, 'blueprint_1')

        blueprint_2 = self.default_client.blueprints.upload(
            self.blueprint_path, 'blueprint_2')
        self._assert_resource_id(blueprint_2, 'blueprint_2')

        # ...but suspended users should not
        self._assert_unauthorized(self.suspended_client.blueprints.upload,
                                  self.blueprint_path, 'dummy_bp')

    def _test_list_blueprints(self):
        # admins and default users should be able so list blueprints...
        blueprints_list = self.admin_client.blueprints.list()
        expected_ids = {'blueprint_1', 'blueprint_2'}
        self._assert_resources_list_ids(blueprints_list, expected_ids)
        blueprints_list = self.default_client.blueprints.list()
        self._assert_resources_list_ids(blueprints_list, expected_ids)

        # ...but suspended users should not
        self._assert_unauthorized(self.suspended_client.blueprints.list)

    def _test_get_blueprints(self):
        # admins and default users should be able to get blueprints
        self._assert_resource_id(
            self.admin_client.blueprints.get('blueprint_1'),
            expected_id='blueprint_1')
        self._assert_resource_id(
            self.default_client.blueprints.get('blueprint_1'),
            expected_id='blueprint_1')

        # suspended users should not be able to get any blueprint
        self._assert_unauthorized(self.suspended_client.blueprints.get,
                                  'blueprint_1')

    def _test_delete_blueprints(self):
        # admins and default users should be able to delete blueprints...
        self.admin_client.blueprints.delete('blueprint_1')
        self.default_client.blueprints.delete('blueprint_2')

        # ...but suspended users should not
        self._assert_unauthorized(self.suspended_client.blueprints.delete,
                                  'dummpy_bp')

    #####################
    # deployment methods
    #####################
    def _test_delete_deployments(self):
        # admins and default users should be able to delete deployments...
        self.wait_for_deployment_creation(self.admin_client, 'dp_example_1')
        self.admin_client.deployments.delete('dp_example_1')

        self.wait_for_deployment_creation(self.default_client, 'dp_example_2')
        self.default_client.deployments.delete('dp_example_2')

        # ...but suspended users should not
        self._assert_unauthorized(self.suspended_client.deployments.delete,
                                  'dp_example_1')

    def _test_get_deployments(self):
        # admins and default users should be able to get
        # deployments...
        dp_example_1 = self.admin_client.deployments.get('dp_example_1')
        self._assert_resource_id(dp_example_1, expected_id='dp_example_1')
        dp_example_1 = self.default_client.deployments.get('dp_example_1')
        self._assert_resource_id(dp_example_1, expected_id='dp_example_1')

        # ...but suspended users should not
        self._assert_unauthorized(self.suspended_client.deployments.get,
                                  'dp_example_1')

    def _test_list_deployments(self):
        # admins and default users should be able so list deployments
        deployments_list = self.admin_client.deployments.list()
        expected_ids = {'dp_example_1', 'dp_example_2'}
        self._assert_resources_list_ids(deployments_list, expected_ids)
        deployments_list = self.default_client.deployments.list()
        self._assert_resources_list_ids(deployments_list, expected_ids)

        # ...but suspended users should not
        self._assert_unauthorized(self.suspended_client.deployments.list)

    def _test_create_deployments(self):
        # admins and default users should be able to create deployments...
        self.admin_client.deployments.create('bp_example_1', 'dp_example_1')
        self.default_client.deployments.create('bp_example_1', 'dp_example_2')

        # ...but suspended users should not
        self._assert_unauthorized(self.suspended_client.deployments.create,
                                  'dummy_bp', 'dummy_dp')

    ####################
    # execution methods
    ####################

    def _test_cancel_executions(self, execution1_id, execution2_id):
        # preparing executions for delete
        self._reset_execution_status_in_db(execution1_id)
        self._reset_execution_status_in_db(execution2_id)
        self.default_client.executions.update(execution1_id, 'pending')
        self.default_client.executions.update(execution2_id, 'pending')

        # admins and default users should be able to cancel executions...
        self.admin_client.executions.cancel(execution1_id)
        self.default_client.executions.cancel(execution2_id)

        # ...but suspended users should not
        self._assert_unauthorized(self.suspended_client.executions.cancel,
                                  execution2_id)

    def _test_update_executions(self, execution_id):
        # admins and default users should be able to update executions...
        self._reset_execution_status_in_db(execution_id)
        execution = self.admin_client.executions.update(
            execution_id, 'pending')
        self._assert_execution(execution,
                               expected_blueprint_id='blueprint_1',
                               expected_deployment_id='deployment_1',
                               expected_workflow_name='install',
                               expected_status='pending')
        execution = self.admin_client.executions.update(
            execution_id, 'cancelling')
        self._assert_execution(execution,
                               expected_blueprint_id='blueprint_1',
                               expected_deployment_id='deployment_1',
                               expected_workflow_name='install',
                               expected_status='cancelling')
        execution = self.default_client.executions.update(
            execution_id, 'cancelled')
        self._assert_execution(execution,
                               expected_blueprint_id='blueprint_1',
                               expected_deployment_id='deployment_1',
                               expected_workflow_name='install',
                               expected_status='cancelled')

        # ...but suspended users should not
        self._assert_unauthorized(self.suspended_client.executions.update,
                                  execution_id, 'dummy-status')

    def _test_get_executions(self, execution1_id, execution2_id):
        # admins and default users should be able to get executions...
        execution_1 = self.admin_client.executions.get(execution1_id)
        self._assert_execution(execution_1,
                               expected_blueprint_id='blueprint_1',
                               expected_deployment_id='deployment_1',
                               expected_workflow_name='install')
        execution_2 = self.default_client.executions.get(execution2_id)
        self._assert_execution(execution_2,
                               expected_blueprint_id='blueprint_2',
                               expected_deployment_id='deployment_2',
                               expected_workflow_name='install')

        # ...but suspended users should not
        self._assert_unauthorized(self.suspended_client.executions.get,
                                  'dp_example_1')

    def _test_start_executions(self):
        # admins and default users should be able to start executions...
        execution1 = self.admin_client.executions.start(
            deployment_id='deployment_1', workflow_id='install')
        execution2 = self.default_client.executions.start(
            deployment_id='deployment_2', workflow_id='install')

        # ...but suspended users should not
        self._assert_unauthorized(self.suspended_client.executions.start,
                                  'dummy_dp', 'install')

        self.wait_for_deployment_creation(self.admin_client, 'deployment_1')
        self.wait_for_deployment_creation(self.admin_client, 'deployment_2')

        return execution1['id'], execution2['id']

    def _test_list_executions(self):
        # admins and default users should be able so list executions
        executions_list = self.admin_client.executions.list()
        self.assertEqual(len(executions_list), 2)
        executions_list = self.default_client.executions.list()
        self.assertEqual(len(executions_list), 2)

        # ...but suspended users should not
        self._assert_unauthorized(self.suspended_client.executions.list)

    #################
    # node methods
    #################
    def _test_get_nodes(self):
        # admins and default users should be able to get nodes
        node1 = self.admin_client.nodes.get(deployment_id='deployment_1',
                                            node_id='mock_node')
        self._assert_node(node1, 'mock_node', 'blueprint_1', 'deployment_1',
                          'cloudify.nodes.Root', 1)
        node1 = self.default_client.nodes.get(deployment_id='deployment_1',
                                              node_id='mock_node')
        self._assert_node(node1, 'mock_node', 'blueprint_1', 'deployment_1',
                          'cloudify.nodes.Root', 1)

        # but suspended users should not
        self._assert_unauthorized(self.suspended_client.nodes.get,
                                  'deployment_1', 'mock_node')

    def _test_list_nodes(self):
        # admins and default users should be able to list nodes...
        nodes_list = self.admin_client.nodes.list()
        self.assertEqual(len(nodes_list), 1)
        nodes_list = self.default_client.nodes.list()
        self.assertEqual(len(nodes_list), 1)

        # ...but suspended users should not
        self._assert_unauthorized(self.suspended_client.nodes.list)

    #########################
    # node instance methods
    #########################
    def _test_update_node_instances(self, instance_id):
        # admins and default users should be able to update nodes instances
        node_instance = self.admin_client.node_instances.update(
            instance_id, state='testing_state',
            runtime_properties={'prop1': 'value1'},
            version=1)
        self._assert_node_instance(node_instance, 'mock_node',
                                   'deployment_1', 'testing_state',
                                   {'prop1': 'value1'})
        node_instance = self.default_client.node_instances.update(
            instance_id, state='testing_state',
            runtime_properties={'prop1': 'value1'},
            version=2)
        self._assert_node_instance(node_instance, 'mock_node',
                                   'deployment_1', 'testing_state',
                                   {'prop1': 'value1'})

        # ...but suspended users should not
        self._assert_unauthorized(
            self.suspended_client.node_instances.update, instance_id,
            'testing_state')

    def _test_get_node_instance(self, instance_id):
        # admins and default users should be able to get
        # nodes instances..
        node_instance = self.admin_client.node_instances.get(instance_id)
        self._assert_node_instance(node_instance, 'mock_node',
                                   'deployment_1', 'uninitialized')
        node_instance = self.default_client.node_instances.get(instance_id)
        self._assert_node_instance(node_instance, 'mock_node',
                                   'deployment_1', 'uninitialized')

        # ...but suspended users should not
        self._assert_unauthorized(self.suspended_client.node_instances.get,
                                  instance_id)
        return instance_id

    def _test_list_node_instances(self):
        # admins and default users should be able to list
        # node instances..
        node_instances = self.admin_client.node_instances.list()
        self.assertEqual(len(node_instances), 1)
        node_instances = self.default_client.node_instances.list()
        self.assertEqual(len(node_instances), 1)

        # ...but suspended users should not
        self._assert_unauthorized(self.suspended_client.node_instances.list)
        return node_instances

    ###########################
    # maintenance mode methods
    ###########################
    def _test_get_status_maintenance_mode(self):
        deactivating_status = 'deactivated'

        # admins and default users should be able to get the
        # maintenance mode status...
        state = self.admin_client.maintenance_mode.status()
        self.assertEqual(state.status, deactivating_status)
        state = self.default_client.maintenance_mode.status()
        self.assertEqual(state.status, deactivating_status)

        # ...but suspended users should not
        self._assert_unauthorized(
                self.suspended_client.maintenance_mode.status)

    def _test_activate_maintenance_mode(self):
        activated_status = 'activated'

        # admins should be able to activate maintenance mode...
        state = self.admin_client.maintenance_mode.activate()
        self.assertEqual(state.status, activated_status)
        self.admin_client.maintenance_mode.deactivate()

        # ...but default and suspended users should not
        self._assert_unauthorized(
                self.default_client.maintenance_mode.activate)
        self._assert_unauthorized(
                self.suspended_client.maintenance_mode.activate)

    def _test_deactivate_maintenance_mode(self):
        deactivating_status = 'deactivated'

        # admins should be able to deactivate maintenance mode...
        self.admin_client.maintenance_mode.activate()
        state = self.admin_client.maintenance_mode.deactivate()
        self.assertEqual(state.status, deactivating_status)

        # ...but default users and suspended users should not
        self._assert_unauthorized(
                self.default_client.maintenance_mode.deactivate)
        self._assert_unauthorized(
                self.suspended_client.maintenance_mode.deactivate)

    #############################
    # utility methods
    #############################
    def _assert_resource_id(self, resource, expected_id):
        self.assertEqual(expected_id, resource['id'])

    def _assert_resources_list_ids(self, resources_list, expected_ids):
        self.assertEquals(len(expected_ids), len(resources_list))
        resources_ids = set([resource.id for resource in resources_list])
        self.assertEquals(expected_ids, resources_ids)

    def _assert_execution(self, execution, expected_blueprint_id,
                          expected_deployment_id, expected_workflow_name,
                          expected_status=None):
        self.assertEqual(expected_blueprint_id, execution['blueprint_id'])
        self.assertEqual(expected_deployment_id, execution['deployment_id'])
        self.assertEqual(expected_workflow_name, execution['workflow_id'])
        if expected_status:
            self.assertEqual(expected_status, execution['status'])

    def _assert_node(self, node, expected_node_id, expected_blueprint_id,
                     expected_deployment_id, expected_node_type,
                     expected_num_of_instances):
        self.assertEqual(expected_node_id, node['id'])
        self.assertEqual(expected_blueprint_id, node['blueprint_id'])
        self.assertEqual(expected_deployment_id, node['deployment_id'])
        self.assertEqual(expected_node_type, node['type'])
        self.assertEqual(expected_num_of_instances,
                         node['number_of_instances'])

    def _assert_node_instance(self, node_instance, expected_node_id,
                              expected_deployment_id, expected_state,
                              expected_runtime_properties=None,
                              expected_version=None):
        self.assertEqual(expected_node_id, node_instance['node_id'])
        self.assertEqual(expected_deployment_id,
                         node_instance['deployment_id'])
        self.assertEqual(expected_state, node_instance['state'])
        if expected_runtime_properties:
            self.assertEqual(expected_runtime_properties,
                             node_instance.runtime_properties)
        if expected_version:
            self.assertEqual(expected_version, node_instance.version)

    def _assert_unauthorized(self, method, *args):
        self.assertRaisesRegexp(UserUnauthorizedError,
                                UNAUTHORIZED_ERROR_MESSAGE,
                                method,
                                *args)

    def _reset_execution_status_in_db(self, execution_id):
        execution = self.sm.get(models.Execution, execution_id)
        execution.status = models.Execution.STARTED
        execution.error = ''
        self.sm.update(execution)
        updated_execution = self.admin_client.executions.get(
            execution_id=execution_id)
        self.assertEqual(models.Execution.STARTED, updated_execution['status'])
