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

__author__ = 'dan'


from base_test import BaseServerTestCase
from manager_rest import manager_exceptions


class DeploymentsTestCase(BaseServerTestCase):

    DEPLOYMENT_ID = 'deployment'

    def test_get_empty(self):
        result = self.get('/deployments')
        self.assertEquals(0, len(result.json))

    def test_put(self):
        (blueprint_id,
         deployment_id,
         blueprint_response,
         deployment_response) = self.put_test_deployment(self.DEPLOYMENT_ID)

        self.assertEquals(deployment_id, self.DEPLOYMENT_ID)
        self.assertEquals(blueprint_id, deployment_response['blueprint_id'])
        self.assertIsNotNone(deployment_response['created_at'])
        self.assertIsNotNone(deployment_response['updated_at'])
        typed_blueprint_plan = blueprint_response['plan']
        typed_deployment_plan = deployment_response['plan']
        self.assertEquals(typed_blueprint_plan['name'],
                          typed_deployment_plan['name'])

    def test_delete_blueprint_which_has_deployments(self):
        (blueprint_id,
         deployment_id,
         blueprint_response,
         deployment_response) = self.put_test_deployment(self.DEPLOYMENT_ID)
        resp = self.delete('/blueprints/{0}'.format(blueprint_id))
        self.assertEqual(400, resp.status_code)
        self.assertTrue('There exist deployments for this blueprint' in
                        resp.json['message'])
        self.assertEquals(resp.json['error_code'],
                          manager_exceptions.DEPENDENT_EXISTS_ERROR_CODE)

    def test_deployment_already_exists(self):
        (blueprint_id,
         deployment_id,
         blueprint_response,
         deployment_response) = self.put_test_deployment(self.DEPLOYMENT_ID)
        deployment_response = self.put(
            '/deployments/{0}'.format(self.DEPLOYMENT_ID),
            {'blueprint_id': blueprint_id})
        self.assertTrue('already exists' in
                        deployment_response.json['message'])
        self.assertEqual(409, deployment_response.status_code)
        self.assertEqual(deployment_response.json['error_code'],
                         manager_exceptions.CONFLICT_ERROR_CODE)

    def test_get_by_id(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_test_deployment(self.DEPLOYMENT_ID)

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
        self.assertEquals(deployment_response['plan'],
                          single_deployment['plan'])

    def test_get(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_test_deployment(self.DEPLOYMENT_ID)

        get_deployments_response = self.get('/deployments').json
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
        self.assertEquals(deployment_response['plan'],
                          single_deployment['plan'])

    def test_get_executions_of_deployment(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_test_deployment(self.DEPLOYMENT_ID)

        resource_path = '/deployments/{0}/executions'.format(deployment_id)
        execution = self.post(resource_path, {
            'workflow_id': 'install'
        }).json
        self.assertEquals(execution['workflow_id'], 'install')
        self.assertEquals(execution['blueprint_id'], blueprint_id)
        self.assertEquals(execution['deployment_id'],
                          deployment_response['id'])
        self.assertIsNotNone(execution['created_at'])
        get_execution = self.get(resource_path).json
        self.assertEquals(1, len(get_execution))
        self.assertEquals(execution, get_execution[0])

    def test_executing_nonexisting_workflow(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_test_deployment(self.DEPLOYMENT_ID)

        resource_path = '/deployments/{0}/executions'.format(deployment_id)
        response = self.post(resource_path, {
            'workflow_id': 'nonexisting-workflow-id'
        })
        self.assertEqual(400, response.status_code)
        self.assertEquals(response.json['error_code'],
                          manager_exceptions.NONEXISTENT_WORKFLOW_ERROR_CODE)

    def test_listing_executions_for_nonexistent_deployment(self):
        resource_path = '/deployments/{0}/executions'.format('doesnotexist')
        response = self.get(resource_path)
        self.assertEqual(404, response.status_code)
        self.assertEquals(response.json['error_code'],
                          manager_exceptions.NOT_FOUND_ERROR_CODE)

    def test_get_workflows_of_deployment(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_test_deployment(self.DEPLOYMENT_ID)

        resource_path = '/deployments/{0}/workflows'.format(deployment_id)
        workflows = self.get(resource_path).json
        self.assertEquals(workflows['blueprint_id'], blueprint_id)
        self.assertEquals(workflows['deployment_id'], deployment_id)
        self.assertEquals(2, len(workflows['workflows']))
        self.assertEquals(workflows['workflows'][0]['name'], 'install')
        self.assertTrue('created_at' in workflows['workflows'][0])
        self.assertEquals(workflows['workflows'][1]['name'], 'uninstall')
        self.assertTrue('created_at' in workflows['workflows'][1])

    def test_delete_deployment_verify_nodes_deletion(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_test_deployment(self.DEPLOYMENT_ID)

        resource_path = '/node-instances?deployment_id={0}'.format(
            deployment_id)
        nodes = self.get(resource_path).json
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
         deployment_response) = self.put_test_deployment(self.DEPLOYMENT_ID)

        # modifying a node's state so there'll be a node in a state other
        # than 'uninitialized'
        resource_path = '/node-instances?deployment_id={0}'.format(
            deployment_id)
        nodes = self.get(resource_path).json

        resp = self.patch('/node-instances/{0}'.format(nodes[0]['id']), {
            'version': 0,
            'state': 'started'
        })
        self.assertEquals(200, resp.status_code)

        # attempting to delete the deployment - should fail because there
        # are live nodes for the deployment
        delete_deployment_response = self.delete('/deployments/{0}'.format(
            deployment_id))
        self.assertEquals(400, delete_deployment_response.status_code)
        self.assertEquals(delete_deployment_response.json['error_code'],
                          manager_exceptions.DEPENDENT_EXISTS_ERROR_CODE)

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
         deployment_response) = self.put_test_deployment(self.DEPLOYMENT_ID)

        resource_path = '/node-instances?deployment_id={0}'.format(
            deployment_id)
        nodes = self.get(resource_path).json

        # modifying nodes states
        for node in nodes:
            resp = self.patch('/node-instances/{0}'.format(node['id']), {
                'version': 0,
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
         deployment_response) = self.put_test_deployment(self.DEPLOYMENT_ID)

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
        self.assertEquals(resp.json['error_code'],
                          manager_exceptions.NOT_FOUND_ERROR_CODE)

    def test_get_nodes_of_deployment(self):

        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_test_deployment(self.DEPLOYMENT_ID)

        resource_path = '/node-instances?deployment_id={0}'.format(
            deployment_id)
        nodes = self.get(resource_path).json
        self.assertEquals(2, len(nodes))

        def assert_node_exists(starts_with):
            self.assertTrue(any(map(
                lambda n: n['id'].startswith(starts_with), nodes)),
                'Failed finding node with prefix {0}'.format(starts_with))
        assert_node_exists('vm')
        assert_node_exists('http_web_server')
