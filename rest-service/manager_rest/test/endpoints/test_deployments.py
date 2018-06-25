#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

import errno
import os
import uuid
import exceptions

from nose.plugins.attrib import attr

from manager_rest.test import base_test
from manager_rest import manager_exceptions
from manager_rest.constants import DEFAULT_TENANT_NAME
from cloudify_rest_client.exceptions import CloudifyClientError
from manager_rest.constants import FILE_SERVER_DEPLOYMENTS_FOLDER


TEST_PACKAGE_NAME = 'cloudify-script-plugin'
TEST_PACKAGE_VERSION = '1.2'


@attr(client_min_version=1, client_max_version=base_test.LATEST_API_VERSION)
class DeploymentsTestCase(base_test.BaseServerTestCase):

    DEPLOYMENT_ID = 'deployment'

    def test_get_empty(self):
        result = self.client.deployments.list()
        self.assertEquals(0, len(result))

    def test_create_deployment_illegal_id(self):
        # try id with whitespace
        self.assertRaisesRegexp(CloudifyClientError,
                                'contains illegal characters',
                                self.client.deployments.create,
                                'blueprint_id',
                                'illegal deployment id')
        # try id that starts with a number
        self.assertRaisesRegexp(CloudifyClientError,
                                'must begin with a letter',
                                self.client.deployments.create,
                                'blueprint_id',
                                '0')

    def test_put(self):
        (blueprint_id,
         deployment_id,
         blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        self.assertEquals(deployment_id, self.DEPLOYMENT_ID)
        self.assertEquals(blueprint_id, deployment_response['blueprint_id'])
        self.assertIsNotNone(deployment_response['created_at'])
        self.assertIsNotNone(deployment_response['updated_at'])

    @attr(client_min_version=3,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_sort_list(self):
        self.put_deployment(deployment_id='d0', blueprint_id='b0')
        self.put_deployment(deployment_id='d1', blueprint_id='b1')

        deployments = self.client.deployments.list(sort='created_at')
        self.assertEqual(2, len(deployments))
        self.assertEqual('d0', deployments[0].id)
        self.assertEqual('d1', deployments[1].id)

        deployments = self.client.deployments.list(
            sort='created_at', is_descending=True)
        self.assertEqual(2, len(deployments))
        self.assertEqual('d1', deployments[0].id)
        self.assertEqual('d0', deployments[1].id)

    @attr(client_min_version=2.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_put_scaling_groups(self):
        _, _, _, deployment_response = self.put_deployment(
            self.DEPLOYMENT_ID,
            blueprint_file_name='modify3-scale-groups.yaml')
        self.assertIn('group', deployment_response['scaling_groups'])

    def test_delete_blueprint_which_has_deployments(self):
        (blueprint_id,
         deployment_id,
         blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)
        resp = self.delete('/blueprints/{0}'.format(blueprint_id))
        self.assertEqual(400, resp.status_code)
        self.assertTrue('There exist deployments for this blueprint' in
                        resp.json['message'])
        self.assertEquals(
            resp.json['error_code'],
            manager_exceptions.DependentExistsError
                .DEPENDENT_EXISTS_ERROR_CODE)

    def test_deployment_already_exists(self):
        (blueprint_id,
         deployment_id,
         blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)
        deployment_response = self.put(
            '/deployments/{0}'.format(self.DEPLOYMENT_ID),
            {'blueprint_id': blueprint_id})
        self.assertTrue('already exists' in
                        deployment_response.json['message'])
        self.assertEqual(409, deployment_response.status_code)
        self.assertEqual(deployment_response.json['error_code'],
                         manager_exceptions.ConflictError.CONFLICT_ERROR_CODE)

    def test_get_by_id(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        single_deployment = self.get('/deployments/{0}'
                                     .format(deployment_id)).json
        self.assertEquals(deployment_id, single_deployment['id'])
        self.assertEquals(deployment_response['blueprint_id'],
                          single_deployment['blueprint_id'])
        self.assertEquals(deployment_response['id'],
                          single_deployment['id'])
        self.assertEquals(deployment_response['created_at'],
                          single_deployment['created_at'])
        self.assertEquals(deployment_response['created_at'],
                          single_deployment['updated_at'])

    def test_get(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        get_deployments_response = self.client.deployments.list()
        self.assertEquals(1, len(get_deployments_response))
        single_deployment = get_deployments_response[0]
        self.assertEquals(deployment_id, single_deployment['id'])
        self.assertEquals(deployment_response['blueprint_id'],
                          single_deployment['blueprint_id'])
        self.assertEquals(deployment_response['id'],
                          single_deployment['id'])
        self.assertEquals(deployment_response['created_at'],
                          single_deployment['created_at'])
        self.assertEquals(deployment_response['created_at'],
                          single_deployment['updated_at'])

    def test_get_executions_of_deployment(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        execution = self.client.executions.start(deployment_id, 'install')
        self.assertEquals('install', execution.workflow_id)
        self.assertEquals(blueprint_id, execution['blueprint_id'])
        self.assertEquals(deployment_id, execution.deployment_id)
        self.assertIsNotNone(execution.created_at)
        executions = self.client.executions.list(deployment_id=deployment_id)
        # expecting two executions - 'install' and
        # 'create_deployment_environment'
        self.assertEquals(2, len(executions))
        self.assertIn(execution['id'],
                      [executions[0]['id'], executions[1]['id']])
        self.assertIn('create_deployment_environment',
                      [executions[1]['workflow_id'],
                       executions[0]['workflow_id']])

    def test_executing_nonexisting_workflow(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        try:
            self.client.executions.start(deployment_id,
                                         'nonexisting-workflow-id')
            self.fail()
        except CloudifyClientError, e:
            self.assertEqual(400, e.status_code)
            error = manager_exceptions.NonexistentWorkflowError
            self.assertEquals(error.NONEXISTENT_WORKFLOW_ERROR_CODE,
                              e.error_code)

    def test_listing_executions_for_nonexistent_deployment(self):
        try:
            self.client.executions.list(deployment_id='doesnotexist')
            self.fail()
        except CloudifyClientError, e:
            self.assertEqual(404, e.status_code)
            self.assertEquals(
                manager_exceptions.NotFoundError.NOT_FOUND_ERROR_CODE,
                e.error_code)

    def test_get_workflows_of_deployment(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(
             self.DEPLOYMENT_ID, 'blueprint_with_workflows.yaml')

        resource_path = '/deployments/{0}'.format(deployment_id)
        workflows = self.get(resource_path).json['workflows']
        self.assertEquals(12, len(workflows))
        workflow = next((workflow for workflow in workflows if
                        workflow['name'] == 'mock_workflow'), None)
        self.assertIsNotNone(workflow)
        self.assertTrue('created_at' in workflow)
        parameters = {
            'optional_param': {'default': 'test_default_value'},
            'mandatory_param': {},
            'mandatory_param2': {},
            'nested_param': {
                'default': {
                    'key': 'test_key',
                    'value': 'test_value'
                }
            }
        }
        self.assertEquals(parameters, workflow['parameters'])

    def test_delete_deployment_verify_nodes_deletion(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        nodes = self.client.node_instances.list(deployment_id=deployment_id)

        self.assertTrue(len(nodes) > 0)
        nodes_ids = [node['id'] for node in nodes]

        delete_deployment_response = self.delete(
            '/deployments/{0}'.format(deployment_id),
            query_params={'ignore_live_nodes': 'true'}).json
        self.assertEquals(deployment_id, delete_deployment_response['id'])

        # verifying deletion of deployment nodes and executions
        for node_id in nodes_ids:
            resp = self.get('/node-instances/{0}'.format(node_id))
            self.assertEquals(404, resp.status_code)

    def test_delete_deployment_with_live_nodes_without_ignore_flag(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        # modifying a node's state so there'll be a node in a state other
        # than 'uninitialized'
        nodes = self.client.node_instances.list(deployment_id=deployment_id)

        resp = self.patch('/node-instances/{0}'.format(nodes[0]['id']), {
            'version': 1,
            'state': 'started'
        })
        self.assertEquals(200, resp.status_code)

        # attempting to delete the deployment - should fail because there
        # are live nodes for the deployment
        delete_deployment_response = self.delete('/deployments/{0}'.format(
            deployment_id))
        self.assertEquals(400, delete_deployment_response.status_code)
        self.assertEquals(delete_deployment_response.json['error_code'],
                          manager_exceptions.DependentExistsError
                          .DEPENDENT_EXISTS_ERROR_CODE)

    def test_delete_deployment_with_uninitialized_nodes(self):
        # simulates a deletion of a deployment right after its creation
        # (i.e. all nodes are still in 'uninitialized' state because no
        # execution has yet to take place)
        self._test_delete_deployment_with_nodes_in_certain_state(
            'uninitialized')

    def test_delete_deployment_without_ignore_flag(self):
        # simulates a deletion of a deployment after the uninstall workflow
        # has completed (i.e. all nodes are in 'deleted' state)
        self._test_delete_deployment_with_nodes_in_certain_state('deleted')

    def _test_delete_deployment_with_nodes_in_certain_state(self, state):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        nodes = self.client.node_instances.list(deployment_id=deployment_id)

        # modifying nodes states
        for node in nodes:
            resp = self.patch('/node-instances/{0}'.format(node['id']), {
                'version': 1,
                'state': state
            })
            self.assertEquals(200, resp.status_code)

        # deleting the deployment
        delete_deployment_response = self.delete('/deployments/{0}'.format(
            deployment_id))
        self.assertEquals(200, delete_deployment_response.status_code)
        self.assertEquals(deployment_id,
                          delete_deployment_response.json['id'])
        # verifying deletion of deployment
        resp = self.get('/deployments/{0}'.format(deployment_id))
        self.assertEquals(404, resp.status_code)

    def test_delete_deployment_with_live_nodes_and_ignore_flag(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        delete_deployment_response = self.delete(
            '/deployments/{0}'.format(deployment_id),
            query_params={'ignore_live_nodes': 'true'}).json
        self.assertEquals(deployment_id, delete_deployment_response['id'])

        # verifying deletion of deployment
        resp = self.get('/deployments/{0}'.format(deployment_id))
        self.assertEquals(404, resp.status_code)

    def test_delete_nonexistent_deployment(self):
        # trying to delete a nonexistent deployment
        resp = self.delete('/deployments/nonexistent-deployment')
        self.assertEquals(404, resp.status_code)
        self.assertEquals(
            resp.json['error_code'],
            manager_exceptions.NotFoundError.NOT_FOUND_ERROR_CODE)

    def test_get_nodes_of_deployment(self):

        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        nodes = self.client.node_instances.list(deployment_id=deployment_id)

        self.assertEquals(2, len(nodes))

        def assert_node_exists(starts_with):
            self.assertTrue(any(map(
                lambda n: n['id'].startswith(starts_with), nodes)),
                'Failed finding node with prefix {0}'.format(starts_with))
        assert_node_exists('vm')
        assert_node_exists('http_web_server')

    def test_delete_deployment_folder_from_file_server(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)
        config = self.server_configuration
        deployment_folder = os.path.join(config.file_server_root,
                                         FILE_SERVER_DEPLOYMENTS_FOLDER,
                                         DEFAULT_TENANT_NAME,
                                         deployment_id)
        try:
            os.makedirs(deployment_folder)
        except OSError as exc:
            if exc.errno == errno.EEXIST and os.path.isdir(deployment_folder):
                pass
            else:
                raise
        deployment_resource_path = os.path.join(deployment_folder, 'test.txt')
        print('Creating deployment resource: {0}'.format(
            deployment_resource_path))
        with open(deployment_resource_path, 'w') as f:
            f.write('deployment resource')
        self.client.deployments.delete(deployment_id)
        self.assertFalse(os.path.exists(deployment_folder))

    def test_inputs(self):
        self.put_deployment(
            blueprint_file_name='blueprint_with_inputs.yaml',
            blueprint_id='b5566',
            deployment_id=self.DEPLOYMENT_ID,
            inputs={'http_web_server_port': '8080'})
        node = self.client.nodes.get(self.DEPLOYMENT_ID, 'http_web_server')
        self.assertEqual('8080', node.properties['port'])
        try:
            self.put_deployment(
                blueprint_file_name='blueprint_with_inputs.yaml',
                blueprint_id='b1122',
                deployment_id=self.DEPLOYMENT_ID,
                inputs='illegal')
        except CloudifyClientError, e:
            self.assertTrue('inputs parameter is expected' in str(e))
        try:
            self.put_deployment(
                blueprint_id='b3344',
                blueprint_file_name='blueprint_with_inputs.yaml',
                deployment_id=self.DEPLOYMENT_ID,
                inputs={'some_input': '1234'})
        except CloudifyClientError, e:
            self.assertIn('were not specified', str(e))
        try:
            self.put_deployment(
                blueprint_id='b7788',
                blueprint_file_name='blueprint_with_inputs.yaml',
                deployment_id=self.DEPLOYMENT_ID,
                inputs={
                    'http_web_server_port': '1234',
                    'unknown_input': 'yey'
                })
        except CloudifyClientError, e:
            self.assertTrue('Unknown input' in str(e))

    def test_outputs(self):
        id_ = 'i{0}'.format(uuid.uuid4())
        self.put_deployment(
            blueprint_file_name='blueprint_with_outputs.yaml',
            blueprint_id=id_,
            deployment_id=id_)
        instances = self.client.node_instances.list(deployment_id=id_)

        vm = [x for x in instances if x.node_id == 'vm'][0]
        vm_props = {'ip': '10.0.0.1'}
        self.client.node_instances.update(vm.id, runtime_properties=vm_props)

        ws = [x for x in instances if x.node_id == 'http_web_server'][0]
        ws_props = {'port': 8080}
        self.client.node_instances.update(ws.id, runtime_properties=ws_props)

        response = self.client.deployments.outputs.get(id_)
        self.assertEqual(id_, response.deployment_id)
        outputs = response.outputs

        self.assertTrue('ip_address' in outputs)
        self.assertTrue('port' in outputs)
        self.assertEqual('10.0.0.1', outputs['ip_address'])
        self.assertEqual(80, outputs['port'])

        dep = self.client.deployments.get(id_)
        self.assertEqual('Web site IP address.',
                         dep.outputs['ip_address']['description'])
        self.assertEqual('Web site port.', dep.outputs['port']['description'])

        endpoint = outputs['endpoint']

        self.assertEqual('http', endpoint['type'])
        self.assertEqual('10.0.0.1', endpoint['ip'])
        self.assertEqual(8080, endpoint['port'])
        self.assertEqual(81, outputs['port2'])

    def test_illegal_output(self):
        id_ = 'i{0}'.format(uuid.uuid4())
        self.put_deployment(
            blueprint_file_name='blueprint_with_illegal_output.yaml',
            blueprint_id=id_,
            deployment_id=id_)
        try:
            self.client.deployments.outputs.get(id_)
            self.fail()
        except CloudifyClientError, e:
            self.assertEqual(400, e.status_code)
            self.assertEqual(
                manager_exceptions.DeploymentOutputsEvaluationError.ERROR_CODE,
                e.error_code)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_creation_failure_when_plugin_not_found_central_deployment(self):
        from cloudify_rest_client.exceptions import DeploymentPluginNotFound
        id_ = 'i{0}'.format(uuid.uuid4())
        try:
            self.put_deployment(
                blueprint_file_name='deployment_with_source_plugin.yaml',
                blueprint_id=id_,
                deployment_id=id_)
            raise exceptions.AssertionError(
                "Expected DeploymentPluginNotFound error")
        except DeploymentPluginNotFound, e:
            self.assertEqual(400, e.status_code)
            self.assertEqual(manager_exceptions.DeploymentPluginNotFound.
                             ERROR_CODE,
                             e.error_code)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_creation_failure_when_plugin_not_found_host_agent(self):
        from cloudify_rest_client.exceptions import DeploymentPluginNotFound
        id_ = 'i{0}'.format(uuid.uuid4())
        try:
            self.put_deployment(
                blueprint_file_name='deployment_'
                                    'with_source_plugin_host_agent.yaml',
                blueprint_id=id_,
                deployment_id=id_)
            raise exceptions.AssertionError(
                "Expected DeploymentPluginNotFound error")
        except DeploymentPluginNotFound, e:
            self.assertEqual(400, e.status_code)
            self.assertEqual(manager_exceptions.DeploymentPluginNotFound.
                             ERROR_CODE,
                             e.error_code)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_creation_success_when_source_plugin_exists_on_manager(self):
        self.upload_plugin(TEST_PACKAGE_NAME, TEST_PACKAGE_VERSION).json
        id_ = 'i{0}'.format(uuid.uuid4())
        self.put_deployment(
            blueprint_file_name='deployment_with_'
                                'existing_plugin_on_manager.yaml',
            blueprint_id=id_,
            deployment_id=id_)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_creation_success_when_source_plugin_with_address_exists(self):
        self.upload_plugin(TEST_PACKAGE_NAME, TEST_PACKAGE_VERSION).json
        id_ = str(uuid.uuid4())
        self.put_deployment(
            blueprint_file_name='deployment_with_source_address.yaml',
            blueprint_id=id_,
            deployment_id=id_)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_creation_success_when_plugin_not_found_with_new_flag(self):
        id_ = 'i{0}'.format(uuid.uuid4())
        self.put_deployment(
            blueprint_file_name='deployment_with_source_plugin.yaml',
            blueprint_id=id_,
            deployment_id=id_,
            skip_plugins_validation=True)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_creation_failure_with_invalid_flag_argument(self):
        id_ = 'i{0}'.format(uuid.uuid4())
        try:
            self.put_deployment(
                blueprint_file_name='deployment_with_source_plugin.yaml',
                blueprint_id=id_,
                deployment_id=id_,
                skip_plugins_validation='invalid_arg')
            raise exceptions.AssertionError("Expected CloudifyClientError")
        except CloudifyClientError, e:
            self.assertEqual(400, e.status_code)
            self.assertEqual(manager_exceptions.BadParametersError.
                             BAD_PARAMETERS_ERROR_CODE,
                             e.error_code)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_creation_failure_without_skip_plugins_validation_argument(self):
        id_ = 'i{0}'.format(uuid.uuid4())
        self.put_blueprint('mock_blueprint',
                           'deployment_with_source_plugin.yaml', id_)
        response = self.put('/deployments/{}'.format(id_),
                            {'blueprint_id': id_})
        self.assertEqual('deployment_plugin_not_found',
                         response.json['error_code'])
        self.assertEqual('400 BAD REQUEST', response.status)
        self.assertEqual(400, response.status_code)

    @attr(client_min_version=1, client_max_version=3)
    def test_creation_success_when_plugin_not_found_central_deployment_agent(
            self):
        id_ = 'i{0}'.format(uuid.uuid4())
        self.put_deployment(
             blueprint_file_name='deployment_with_source_plugin.yaml',
             blueprint_id=id_,
             deployment_id=id_)

    @attr(client_min_version=1, client_max_version=3)
    def test_creation_success_when_plugin_not_found_host_agent(self):
        id_ = 'i{0}'.format(uuid.uuid4())
        self.put_deployment(
             blueprint_file_name='deployment_with'
                                 '_source_plugin_host_agent.yaml',
             blueprint_id=id_,
             deployment_id=id_)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_creation_success_when_diamond_plugin_in_blueprint(self):
        id_ = 'i{0}'.format(uuid.uuid4())
        self.put_deployment(
             blueprint_file_name='deployment_with_'
                                 'diamond_as_source_plugin.yaml',
             blueprint_id=id_,
             deployment_id=id_)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_creation_success_when_diamond_as_host_agent_in_blueprint(self):
        id_ = 'i{0}'.format(uuid.uuid4())
        self.put_deployment(
             blueprint_file_name='deployment_with_'
                                 'diamond_as_host_agent.yaml',
             blueprint_id=id_,
             deployment_id=id_)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_creation_success_when_install_plugin_is_False(self):
        id_ = 'i{0}'.format(uuid.uuid4())
        self.put_deployment(
             blueprint_file_name='deployment_with_'
                                 'install_plugin_False.yaml',
             blueprint_id=id_,
             deployment_id=id_)
