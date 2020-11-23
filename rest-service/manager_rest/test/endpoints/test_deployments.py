#########
# Copyright (c) 2018 Cloudify Platform Ltd. All rights reserved
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

from cloudify.models_states import VisibilityState

from manager_rest.test import base_test
from manager_rest.test.attribute import attr
from manager_rest import manager_exceptions
from manager_rest.constants import (DEFAULT_TENANT_NAME,
                                    FILE_SERVER_DEPLOYMENTS_FOLDER)

from cloudify_rest_client.exceptions import CloudifyClientError


TEST_PACKAGE_NAME = 'cloudify-script-plugin'
TEST_PACKAGE_VERSION = '1.2'


@attr(client_min_version=1, client_max_version=base_test.LATEST_API_VERSION)
class DeploymentsTestCase(base_test.BaseServerTestCase):

    DEPLOYMENT_ID = 'deployment'
    SITE_NAME = 'test_site'
    LABELS = [{'env': 'aws'}, {'arch': 'k8s'}]
    UPDATED_LABELS = [{'env': 'gcp'}, {'arch': 'k8s'}]
    UPDATED_UPPERCASE_LABELS = [{'env': 'GCp'}, {'ArCh': 'k8s'}]
    UPPERCASE_LABELS = [{'EnV': 'aWs'}, {'aRcH': 'k8s'}]
    DUPLICATE_LABELS = [{'env': 'aws'}, {'env': 'aws'}]
    INVALID_LABELS = [{'env': 'aws', 'aRcH': 'k8s'}]

    def test_get_empty(self):
        result = self.client.deployments.list()
        self.assertEqual(0, len(result))

    def test_create_deployment_illegal_id(self):
        # try id with whitespace
        self.assertRaisesRegex(CloudifyClientError,
                               'contains illegal characters',
                               self.client.deployments.create,
                               'blueprint_id',
                               'illegal deployment id')
        # try id that starts with a number
        self.assertRaisesRegex(CloudifyClientError,
                               'must begin with a letter',
                               self.client.deployments.create,
                               'blueprint_id',
                               '0')

    def test_put(self):
        (blueprint_id,
         deployment_id,
         blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        self.assertEqual(deployment_id, self.DEPLOYMENT_ID)
        self.assertEqual(blueprint_id, deployment_response['blueprint_id'])
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
        with self.assertRaises(CloudifyClientError) as context:
            self.client.blueprints.delete(blueprint_id)
        self.assertEqual(400, context.exception.status_code)
        self.assertIn('There exist deployments for this blueprint',
                      str(context.exception))
        self.assertEqual(
            context.exception.error_code,
            manager_exceptions.DependentExistsError.
            DEPENDENT_EXISTS_ERROR_CODE)

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
        self.assertEqual(deployment_id, single_deployment['id'])
        self.assertEqual(deployment_response['blueprint_id'],
                         single_deployment['blueprint_id'])
        self.assertEqual(deployment_response['id'],
                         single_deployment['id'])
        self.assertEqual(deployment_response['created_at'],
                         single_deployment['created_at'])
        self.assertEqual(deployment_response['created_at'],
                         single_deployment['updated_at'])

    def test_get(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        get_deployments_response = self.client.deployments.list()
        self.assertEqual(1, len(get_deployments_response))
        single_deployment = get_deployments_response[0]
        self.assertEqual(deployment_id, single_deployment['id'])
        self.assertEqual(deployment_response['blueprint_id'],
                         single_deployment['blueprint_id'])
        self.assertEqual(deployment_response['id'],
                         single_deployment['id'])
        self.assertEqual(deployment_response['created_at'],
                         single_deployment['created_at'])
        self.assertEqual(deployment_response['created_at'],
                         single_deployment['updated_at'])

    def test_get_executions_of_deployment(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        execution = self.client.executions.start(deployment_id, 'install')
        self.assertEqual('install', execution.workflow_id)
        self.assertEqual(blueprint_id, execution['blueprint_id'])
        self.assertEqual(deployment_id, execution.deployment_id)
        self.assertIsNotNone(execution.created_at)
        executions = self.client.executions.list(deployment_id=deployment_id)
        # expecting two executions - 'install' and
        # 'create_deployment_environment'
        self.assertEqual(2, len(executions))
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
        except CloudifyClientError as e:
            self.assertEqual(400, e.status_code)
            error = manager_exceptions.NonexistentWorkflowError
            self.assertEqual(error.NONEXISTENT_WORKFLOW_ERROR_CODE,
                             e.error_code)

    def test_listing_executions_for_nonexistent_deployment(self):
        result = self.client.executions.list(deployment_id='doesnotexist')
        if not isinstance(result, list):
            result = result.items
        assert result == []

    def test_get_workflows_of_deployment(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(
             self.DEPLOYMENT_ID, 'blueprint_with_workflows.yaml')

        resource_path = '/deployments/{0}'.format(deployment_id)
        workflows = self.get(resource_path).json['workflows']
        self.assertEqual(12, len(workflows))
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
        self.assertEqual(parameters, workflow['parameters'])

    def test_delete_deployment_verify_nodes_deletion(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        nodes = self.client.node_instances.list(deployment_id=deployment_id)

        self.assertTrue(len(nodes) > 0)
        nodes_ids = [node['id'] for node in nodes]

        self.delete_deployment(deployment_id)

        # verifying deletion of deployment nodes and executions
        for node_id in nodes_ids:
            resp = self.get('/node-instances/{0}'.format(node_id))
            self.assertEqual(404, resp.status_code)

    def test_delete_deployment_with_live_nodes_without_force_flag(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        # modifying a node's state so there'll be a node in a state other
        # than 'uninitialized'
        nodes = self.client.node_instances.list(deployment_id=deployment_id)

        resp = self.patch('/node-instances/{0}'.format(nodes[0]['id']), {
            'version': 1,
            'state': 'started'
        })
        self.assertEqual(200, resp.status_code)

        # attempting to delete the deployment - should fail because there
        # are live nodes for the deployment

        try:
            self.client.deployments.delete(deployment_id)
        except CloudifyClientError as e:
            self.assertEqual(e.status_code, 400)
            self.assertEqual(e.error_code, manager_exceptions.
                             DependentExistsError.DEPENDENT_EXISTS_ERROR_CODE)

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
            self.assertEqual(200, resp.status_code)

        self.client.deployments.delete(deployment_id)

    def test_delete_deployment_with_live_nodes_and_force_flag(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        self.client.deployments.delete(deployment_id, force=True)

    def test_delete_nonexistent_deployment(self):
        # trying to delete a nonexistent deployment
        resp = self.delete('/deployments/nonexistent-deployment')
        self.assertEqual(404, resp.status_code)
        self.assertEqual(
            resp.json['error_code'],
            manager_exceptions.NotFoundError.NOT_FOUND_ERROR_CODE)

    def test_get_nodes_of_deployment(self):

        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        nodes = self.client.node_instances.list(deployment_id=deployment_id)

        self.assertEqual(2, len(nodes))

        def assert_node_exists(starts_with):
            self.assertTrue(
                any(n['id'].startswith(starts_with) for n in nodes),
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
        with open(deployment_resource_path, 'w') as f:
            f.write('deployment resource')

        self.delete_deployment(deployment_id)
        self.assertFalse(os.path.exists(deployment_folder))

    def test_inputs(self):
        self.put_deployment(
            blueprint_file_name='blueprint_with_inputs.yaml',
            blueprint_id='b5566',
            deployment_id=self.DEPLOYMENT_ID,
            inputs={'http_web_server_port': '8080',
                    'http_web_server_port2': {'a': ['9090']}})
        node = self.client.nodes.get(self.DEPLOYMENT_ID, 'http_web_server')
        self.assertEqual('8080', node.properties['port'])
        node2 = self.client.nodes.get(self.DEPLOYMENT_ID, 'http_web_server2')
        self.assertEqual('9090', node2.properties['port'])
        self.assertRaisesRegex(CloudifyClientError,
                               'inputs parameter is expected',
                               self.put_deployment,
                               blueprint_id='b1122',
                               blueprint_file_name='blueprint_with_inputs'
                                                   '.yaml',
                               deployment_id=self.DEPLOYMENT_ID,
                               inputs='illegal')
        self.assertRaisesRegex(CloudifyClientError,
                               'were not specified',
                               self.put_deployment,
                               blueprint_id='b3344',
                               blueprint_file_name='blueprint_with_inputs'
                                                   '.yaml',
                               deployment_id=self.DEPLOYMENT_ID,
                               inputs={'some_input': '1234'})
        self.assertRaisesRegex(CloudifyClientError,
                               'Unknown input',
                               self.put_deployment,
                               blueprint_id='b7788',
                               blueprint_file_name='blueprint_with_inputs'
                                                   '.yaml',
                               deployment_id=self.DEPLOYMENT_ID,
                               inputs={
                                   'http_web_server_port': '1234',
                                   'http_web_server_port2': {'a': ['9090']},
                                   'unknown_input': 'yay'
                               })
        self.assertRaisesRegex(CloudifyClientError,
                               "(Input attribute).+(doesn't exist)",
                               self.put_deployment,
                               blueprint_id='b7789',
                               blueprint_file_name='blueprint_with_inputs'
                                                   '.yaml',
                               deployment_id=self.DEPLOYMENT_ID,
                               inputs={
                                   'http_web_server_port': '1234',
                                   'http_web_server_port2': {
                                       'something_new': ['9090']}
                               })
        self.assertRaisesRegex(CloudifyClientError,
                               'is expected to be an int but got',
                               self.put_deployment,
                               blueprint_id='b7790',
                               blueprint_file_name='blueprint_with_inputs'
                                                   '.yaml',
                               deployment_id=self.DEPLOYMENT_ID,
                               inputs={
                                   'http_web_server_port': '1234',
                                   'http_web_server_port2': [1234]
                               })
        self.assertRaisesRegex(CloudifyClientError,
                               "(List size of).+(but index)",
                               self.put_deployment,
                               blueprint_id='b7791',
                               blueprint_file_name='blueprint_with_inputs'
                                                   '.yaml',
                               deployment_id=self.DEPLOYMENT_ID,
                               inputs={
                                   'http_web_server_port': '1234',
                                   'http_web_server_port2': {'a': []}
                               })

    def test_input_with_default_value_and_constraints(self):
        self.put_deployment(
            blueprint_file_name='blueprint_with_inputs_and_constraints.yaml',
            blueprint_id='b9700',
            deployment_id=self.DEPLOYMENT_ID)
        node = self.client.nodes.get(self.DEPLOYMENT_ID, 'http_web_server')
        self.assertEqual('8080', node.properties['port'])

    def test_input_with_constraints_and_value_provided(self):
        self.put_deployment(
            blueprint_file_name='blueprint_with_inputs_and_constraints.yaml',
            blueprint_id='b9701',
            deployment_id=self.DEPLOYMENT_ID,
            inputs={'http_web_server_port': '9090'})
        node = self.client.nodes.get(
            self.DEPLOYMENT_ID, 'http_web_server')
        self.assertEqual('9090', node.properties['port'])

    def test_input_violates_constraint(self):
        self.assertRaisesRegex(
            CloudifyClientError,
            "Value .+ of input .+ violates constraint length.+\\.",
            self.put_deployment,
            blueprint_id='b9702',
            blueprint_file_name='blueprint_with_inputs_and_constraints.yaml',
            deployment_id=self.DEPLOYMENT_ID,
            inputs={'http_web_server_port': '123'})

    def test_input_violates_constraint_data_type(self):
        self.assertRaisesRegex(
            CloudifyClientError,
            "Value's length could not be computed. Value type is 'int'\\.",
            self.put_deployment,
            blueprint_id='b9703',
            blueprint_file_name='blueprint_with_inputs_and_constraints.yaml',
            deployment_id=self.DEPLOYMENT_ID,
            inputs={'http_web_server_port': 123})

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
        outputs = self.client.deployments.outputs.get(id_)
        self.assertIn("More than one node instance found for node",
                      outputs['outputs']['ip_address'])

    def test_no_outputs(self):
        id_ = 'i{0}'.format(uuid.uuid4())
        self.put_deployment(
            blueprint_file_name='blueprint.yaml',
            blueprint_id=id_,
            deployment_id=id_)
        outputs = self.client.deployments.outputs.get(id_)
        self.assertEqual(outputs['outputs'], {})

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_creation_failure_when_plugin_not_found_central_deployment(self):
        from cloudify_rest_client.exceptions import DeploymentPluginNotFound
        id_ = 'i{0}'.format(uuid.uuid4())
        with self.assertRaises(DeploymentPluginNotFound) as cm:
            self.put_deployment(
                blueprint_file_name='deployment_with_source_plugin.yaml',
                blueprint_id=id_,
                deployment_id=id_)

        self.assertEqual(400, cm.exception.status_code)
        self.assertEqual(manager_exceptions.DeploymentPluginNotFound.
                         ERROR_CODE,
                         cm.exception.error_code)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_creation_failure_when_plugin_not_found_host_agent(self):
        from cloudify_rest_client.exceptions import DeploymentPluginNotFound
        id_ = 'i{0}'.format(uuid.uuid4())
        with self.assertRaises(DeploymentPluginNotFound) as cm:
            self.put_deployment(
                blueprint_file_name='deployment_'
                                    'with_source_plugin_host_agent.yaml',
                blueprint_id=id_,
                deployment_id=id_)
        self.assertEqual(400, cm.exception.status_code)
        self.assertEqual(manager_exceptions.DeploymentPluginNotFound.
                         ERROR_CODE,
                         cm.exception.error_code)

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
        id_ = 'i{0}'.format(uuid.uuid4())
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
        with self.assertRaises(CloudifyClientError) as cm:
            self.put_deployment(
                blueprint_file_name='deployment_with_source_plugin.yaml',
                blueprint_id=id_,
                deployment_id=id_,
                skip_plugins_validation='invalid_arg')
        self.assertEqual(400, cm.exception.status_code)
        self.assertEqual(manager_exceptions.BadParametersError.
                         BAD_PARAMETERS_ERROR_CODE,
                         cm.exception.error_code)

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
    def test_creation_success_without_site(self):
        self._put_deployment_without_site()

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_creation_success_with_site(self):
        self.client.sites.create(self.SITE_NAME)
        resource_id = 'i{0}'.format(uuid.uuid4())
        self.put_deployment(blueprint_file_name='blueprint.yaml',
                            blueprint_id=resource_id,
                            deployment_id=resource_id,
                            site_name=self.SITE_NAME)
        deployment = self.client.deployments.get(resource_id)
        self.assertEqual(deployment.site_name, self.SITE_NAME)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_creation_success_with_different_site_visibility(self):
        self.client.sites.create(self.SITE_NAME,
                                 visibility=VisibilityState.GLOBAL)
        resource_id = 'i{0}'.format(uuid.uuid4())
        self.put_deployment(blueprint_file_name='blueprint.yaml',
                            blueprint_id=resource_id,
                            deployment_id=resource_id,
                            site_name=self.SITE_NAME)
        deployment = self.client.deployments.get(resource_id)
        self.assertEqual(deployment.site_name, self.SITE_NAME)
        self.assertEqual(deployment.visibility, VisibilityState.TENANT)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_creation_failure_invalid_site_visibility(self):
        self.client.sites.create(self.SITE_NAME,
                                 visibility=VisibilityState.PRIVATE)
        resource_id = 'i{0}'.format(uuid.uuid4())
        error_msg = "400: The visibility of deployment `{0}`: `tenant` " \
                    "can't be wider than the visibility of it's site " \
                    "`{1}`: `private`".format(resource_id, self.SITE_NAME)
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.put_deployment,
                               blueprint_file_name='blueprint.yaml',
                               blueprint_id=resource_id,
                               deployment_id=resource_id,
                               site_name=self.SITE_NAME)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_creation_failure_invalid_site(self):
        error_msg = '404: Requested `Site` with ID `test_site` was not found'
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.put_deployment,
                               blueprint_file_name='blueprint.yaml',
                               blueprint_id='i{0}'.format(uuid.uuid4()),
                               deployment_id='i{0}'.format(uuid.uuid4()),
                               site_name=self.SITE_NAME)

        error_msg = '400: The `site_name` argument contains illegal ' \
                    'characters.'
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.put_deployment,
                               blueprint_file_name='blueprint.yaml',
                               blueprint_id='i{0}'.format(uuid.uuid4()),
                               deployment_id='i{0}'.format(uuid.uuid4()),
                               site_name=':invalid_site')

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_set_site_deployment_created_without_site(self):
        resource_id = self._put_deployment_without_site()
        self.client.sites.create(self.SITE_NAME)
        self.client.deployments.set_site(resource_id, site_name=self.SITE_NAME)
        deployment = self.client.deployments.get(resource_id)
        self.assertEqual(deployment.site_name, self.SITE_NAME)

        # Setting a site after a previous one was set
        new_site_name = 'new_site'
        self.client.sites.create(new_site_name, location="34.0,32.0")
        self.client.deployments.set_site(resource_id, site_name=new_site_name)
        deployment = self.client.deployments.get(resource_id)
        self.assertEqual(deployment.site_name, new_site_name)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_set_site_deployment_created_with_site(self):
        resource_id = self._put_deployment_with_site()

        # Setting a site after the deployment was created with a site
        new_site_name = 'new_site'
        self.client.sites.create(new_site_name, location="34.0,32.0")
        self.client.deployments.set_site(resource_id, site_name=new_site_name)
        deployment = self.client.deployments.get(resource_id)
        self.assertEqual(deployment.site_name, new_site_name)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_set_site_different_visibility(self):
        self.client.sites.create(self.SITE_NAME,
                                 visibility=VisibilityState.GLOBAL)
        resource_id = self._put_deployment_without_site()
        deployment = self.client.deployments.get(resource_id)
        self.assertEqual(deployment.visibility, VisibilityState.TENANT)
        self.client.deployments.set_site(resource_id, site_name=self.SITE_NAME)
        deployment = self.client.deployments.get(resource_id)
        self.assertEqual(deployment.site_name, self.SITE_NAME)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_set_site_invalid_deployment_visibility(self):
        resource_id = self._put_deployment_without_site()
        self.client.sites.create(self.SITE_NAME,
                                 visibility=VisibilityState.PRIVATE)
        error_msg = "400: The visibility of deployment `{0}`: `tenant` " \
                    "can't be wider than the visibility of it's site " \
                    "`{1}`: `private`".format(resource_id, self.SITE_NAME)
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.client.deployments.set_site,
                               resource_id,
                               site_name=self.SITE_NAME)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_set_site_invalid_deployment(self):
        error_msg = '404: Requested `Deployment` with ID `no_deployment` ' \
                    'was not found'
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.client.deployments.set_site,
                               'no_deployment',
                               site_name=self.SITE_NAME)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_set_site_invalid_site(self):
        resource_id = self._put_deployment_without_site()
        error_msg = '404: Requested `Site` with ID `{0}` was not ' \
                    'found'.format(self.SITE_NAME)
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.client.deployments.set_site,
                               resource_id,
                               site_name=self.SITE_NAME)

        error_msg = '400: The `site_name` argument contains illegal ' \
                    'characters.'
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.client.deployments.set_site,
                               deployment_id='i{0}'.format(uuid.uuid4()),
                               site_name=':invalid_site')

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_set_site_bad_parameters(self):
        resource_id = self._put_deployment_without_site()
        error_msg = '400: Must provide either a `site_name` of a valid site ' \
                    'or `detach_site` with true value for detaching the ' \
                    'current site of the given deployment'
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.client.deployments.set_site,
                               deployment_id=resource_id)
        self.client.sites.create(self.SITE_NAME)
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.client.deployments.set_site,
                               deployment_id=resource_id,
                               site_name=self.SITE_NAME,
                               detach_site=True)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_set_site_detach_existing_site(self):
        resource_id = self._put_deployment_with_site()

        # Detaching the site when the deployment is assigned with one
        self.client.deployments.set_site(resource_id, detach_site=True)
        deployment = self.client.deployments.get(resource_id)
        self.assertIsNone(deployment.site_name)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_set_site_detach_none_site(self):
        # Detaching the site when the deployment is not assigned with one
        resource_id = self._put_deployment_without_site()
        self.client.deployments.set_site(resource_id, detach_site=True)
        deployment = self.client.deployments.get(resource_id)
        self.assertIsNone(deployment.site_name)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_delete_site_of_deployment(self):
        resource_id = self._put_deployment_with_site()

        # Delete a site that is attached to the deployment
        self.client.sites.delete(self.SITE_NAME)
        deployment = self.client.deployments.get(resource_id)
        self.assertIsNone(deployment.site_name)
        error_msg = '404: Requested `Site` with ID `test_site` was not found'
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.client.sites.get,
                               self.SITE_NAME)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_delete_deployment_attached_to_site(self):
        resource_id = self._put_deployment_with_site()

        # Delete a deployment that is attached to a site
        self.delete_deployment(resource_id)

        # self.client.deployments.delete(resource_id, delete_db_mode=True)
        site = self.client.sites.get(self.SITE_NAME)
        self.assertEqual(site.name, self.SITE_NAME)
        error_msg = '404: Requested `Deployment` with ID `{}` ' \
                    'was not found'.format(resource_id)
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.client.deployments.get,
                               resource_id)

    def _put_deployment_without_site(self):
        resource_id = 'i{0}'.format(uuid.uuid4())
        self.put_deployment(blueprint_file_name='blueprint.yaml',
                            blueprint_id=resource_id,
                            deployment_id=resource_id)
        deployment = self.client.deployments.get(resource_id)
        self.assertIsNone(deployment.site_name)
        return resource_id

    def _put_deployment_with_site(self):
        self.client.sites.create(self.SITE_NAME)
        resource_id = 'i{0}'.format(uuid.uuid4())
        self.put_deployment(blueprint_file_name='blueprint.yaml',
                            blueprint_id=resource_id,
                            deployment_id=resource_id,
                            site_name=self.SITE_NAME)
        deployment = self.client.deployments.get(resource_id)
        self.assertEqual(deployment.site_name, self.SITE_NAME)
        return resource_id

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_creation_success_without_labels(self):
        resource_id = 'i{0}'.format(uuid.uuid4())
        _, _, _, deployment = self.put_deployment(
            blueprint_file_name='blueprint.yaml',
            blueprint_id=resource_id,
            deployment_id=resource_id)
        self.assertEmpty(deployment.labels)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_creation_success_with_labels(self):
        deployment = self.put_deployment_with_labels(self.LABELS)
        self._assert_deployment_labels(deployment.labels, self.LABELS)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_uppercase_labels_to_lowercase(self):
        deployment = self.put_deployment_with_labels(self.UPPERCASE_LABELS)
        self._assert_deployment_labels(deployment.labels, self.LABELS)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_creation_failure_with_invalid_labels(self):
        resource_id = 'i{0}'.format(uuid.uuid4())
        error_msg = '400: .*Labels must be a list of 1-entry dictionaries.*'
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.put_deployment,
                               blueprint_file_name='blueprint.yaml',
                               blueprint_id=resource_id,
                               deployment_id=resource_id,
                               labels=self.INVALID_LABELS)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_creation_failure_with_duplicate_labels(self):
        resource_id = 'i{0}'.format(uuid.uuid4())
        error_msg = '400: .*You cannot define the same label twice.*'
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.put_deployment,
                               blueprint_file_name='blueprint.yaml',
                               blueprint_id=resource_id,
                               deployment_id=resource_id,
                               labels=self.DUPLICATE_LABELS)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_update_deployments_labels(self):
        deployment = self.put_deployment_with_labels(self.LABELS)
        updated_dep = self.client.deployments.update_labels(
            deployment.id, self.UPDATED_LABELS)
        self._assert_deployment_labels(updated_dep.labels, self.UPDATED_LABELS)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_update_uppercase_deployments_labels(self):
        deployment = self.put_deployment_with_labels(self.LABELS)
        updated_dep = self.client.deployments.update_labels(
            deployment.id, self.UPDATED_UPPERCASE_LABELS)
        self._assert_deployment_labels(updated_dep.labels, self.UPDATED_LABELS)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_update_empty_deployments_labels(self):
        deployment = self.put_deployment_with_labels(self.LABELS)
        self._assert_deployment_labels(deployment.labels, self.LABELS)
        updated_dep = self.client.deployments.update_labels(deployment.id, [])
        self.assertEmpty(updated_dep.labels)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_update_failure_with_invalid_labels(self):
        deployment = self.put_deployment_with_labels(self.LABELS)
        error_msg = '400: .*Labels must be a list of 1-entry dictionaries.*'
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.client.deployments.update_labels,
                               deployment_id=deployment.id,
                               labels=self.INVALID_LABELS)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_update_failure_with_duplicate_labels(self):
        deployment = self.put_deployment_with_labels(self.LABELS)
        error_msg = '400: .*You cannot define the same label twice.*'
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.client.deployments.update_labels,
                               deployment_id=deployment.id,
                               labels=self.DUPLICATE_LABELS)

    def _assert_deployment_labels(self, deployment_labels, compared_labels):
        simplified_labels = set()
        compared_labels_set = set()

        for label in deployment_labels:
            simplified_labels.add((label['key'], label['value']))

        for compared_label in compared_labels:
            [(key, value)] = compared_label.items()
            compared_labels_set.add((key, value))

        self.assertEqual(simplified_labels, compared_labels_set)
