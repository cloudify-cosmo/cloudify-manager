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


import mocks
from base_test import BaseServerTestCase
from test_blueprints import post_blueprint_args


class DeploymentsTestCase(BaseServerTestCase):

    DEPLOYMENT_ID = 'deployment'

    def _put_test_deployment(self):
        blueprint_response = self.post_file(*post_blueprint_args()).json
        blueprint_id = blueprint_response['id']
        # Execute post deployment
        deployment_response = self.put(
            '/deployments/{0}'.format(self.DEPLOYMENT_ID),
            {'blueprintId': blueprint_id}).json
        return (blueprint_id, deployment_response['id'], blueprint_response,
                deployment_response)

    def test_get_empty(self):
        result = self.get('/deployments')
        self.assertEquals(0, len(result.json))

    def test_put(self):
        (blueprint_id,
         deployment_id,
         blueprint_response,
         deployment_response) = self._put_test_deployment()

        self.assertEquals(deployment_id, self.DEPLOYMENT_ID)
        self.assertEquals(blueprint_id, deployment_response['blueprintId'])
        self.assertIsNotNone(deployment_response['createdAt'])
        self.assertIsNotNone(deployment_response['updatedAt'])
        typed_blueprint_plan = blueprint_response['plan']
        typed_deployment_plan = deployment_response['plan']
        self.assertEquals(typed_blueprint_plan['name'],
                          typed_deployment_plan['name'])

    def test_delete_blueprint_which_has_deployments(self):
        (blueprint_id,
         deployment_id,
         blueprint_response,
         deployment_response) = self._put_test_deployment()
        resp = self.delete('/blueprints/{0}'.format(blueprint_id))
        self.assertEqual(400, resp.status_code)
        self.assertTrue('There exist deployments for this blueprint' in
                        resp.json['message'])

    def test_deployment_already_exists(self):
        (blueprint_id,
         deployment_id,
         blueprint_response,
         deployment_response) = self._put_test_deployment()
        deployment_response = self.put(
            '/deployments/{0}'.format(self.DEPLOYMENT_ID),
            {'blueprintId': blueprint_id})
        self.assertTrue('already exists' in
                        deployment_response.json['message'])
        self.assertEqual(409, deployment_response.status_code)

    def test_get_by_id(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self._put_test_deployment()

        single_deployment = self.get('/deployments/{0}'
                                     .format(deployment_id)).json
        self.assertEquals(deployment_id, single_deployment['id'])
        self.assertEquals(deployment_response['blueprintId'],
                          single_deployment['blueprintId'])
        self.assertEquals(deployment_response['id'],
                          single_deployment['id'])
        self.assertEquals(deployment_response['createdAt'],
                          single_deployment['createdAt'])
        self.assertEquals(deployment_response['createdAt'],
                          single_deployment['updatedAt'])
        self.assertEquals(deployment_response['plan'],
                          single_deployment['plan'])

    def test_get(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self._put_test_deployment()

        get_deployments_response = self.get('/deployments').json
        self.assertEquals(1, len(get_deployments_response))
        single_deployment = get_deployments_response[0]
        self.assertEquals(deployment_id, single_deployment['id'])
        self.assertEquals(deployment_response['blueprintId'],
                          single_deployment['blueprintId'])
        self.assertEquals(deployment_response['id'],
                          single_deployment['id'])
        self.assertEquals(deployment_response['createdAt'],
                          single_deployment['createdAt'])
        self.assertEquals(deployment_response['createdAt'],
                          single_deployment['updatedAt'])
        self.assertEquals(deployment_response['plan'],
                          single_deployment['plan'])

    def test_get_blueprints_id_executions_empty(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self._put_test_deployment()
        get_executions = self.get('/deployments/{0}/executions'
                                  .format(deployment_response['id'])).json
        self.assertEquals(len(get_executions), 0)

    def test_get_execution_by_id(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self._put_test_deployment()

        resource_path = '/deployments/{0}/executions'.format(deployment_id)
        execution = self.post(resource_path, {
            'workflowId': 'install'
        }).json
        get_execution_resource = '/executions/{0}'.format(execution['id'])
        get_execution = self.get(get_execution_resource).json
        self.assertEquals(get_execution['status'], 'terminated')
        self.assertEquals(get_execution['blueprintId'], blueprint_id)
        self.assertEquals(get_execution['deploymentId'],
                          deployment_response['id'])
        self.assertIsNotNone(get_execution['createdAt'])

        return execution

    def test_cancel_execution_by_id(self):
        execution = self.test_get_execution_by_id()
        resource_path = '/executions/{0}'.format(execution['id'])
        cancel_response = self.post(resource_path, {
            'action': 'cancel'
        }).json
        self.assertEquals(execution, cancel_response)

    def test_cancel_non_existent_execution(self):
        resource_path = '/executions/do_not_exist'
        cancel_response = self.post(resource_path, {
            'action': 'cancel'
        })
        self.assertEquals(cancel_response.status_code, 404)

    def test_cancel_bad_action(self):
        execution = self.test_get_execution_by_id()
        resource_path = '/executions/{0}'.format(execution['id'])
        cancel_response = self.post(resource_path, {
            'action': 'not_really_cancel'
        })
        self.assertEquals(cancel_response.status_code, 400)

    def test_cancel_no_action(self):
        execution = self.test_get_execution_by_id()
        resource_path = '/executions/{0}'.format(execution['id'])
        cancel_response = self.post(resource_path, {
            'not_action': 'some_value'
        })
        self.assertEquals(cancel_response.status_code, 400)

    def test_get_executions_of_deployment(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self._put_test_deployment()

        resource_path = '/deployments/{0}/executions'.format(deployment_id)
        execution = self.post(resource_path, {
            'workflowId': 'install'
        }).json
        self.assertEquals(execution['workflowId'], 'install')
        self.assertEquals(execution['blueprintId'], blueprint_id)
        self.assertEquals(execution['deploymentId'], deployment_response['id'])
        self.assertIsNotNone(execution['createdAt'])
        get_execution = self.get(resource_path).json
        self.assertEquals(1, len(get_execution))
        # since we're not asking to retrieve execution statuses, status and
        # error fields should be None in response's executions
        execution['status'] = None
        execution['error'] = None
        self.assertEquals(execution, get_execution[0])

        # testing retrieval of updated execution status
        get_execution = self.get(resource_path, {'statuses': True}).json
        self.assertEquals(1, len(get_execution))
        execution['status'] = 'terminated'  # setting expected status
        self.assertEquals('terminated', get_execution[0]['status'])
        self.assertEquals(None, get_execution[0]['error'])
        self.assertEquals(execution, get_execution[0])

    def test_executing_nonexisting_workflow(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self._put_test_deployment()

        resource_path = '/deployments/{0}/executions'.format(deployment_id)
        response = self.post(resource_path, {
            'workflowId': 'nonexisting-workflow-id'
        })
        self.assertEqual(400, response.status_code)

    def test_listing_executions_for_nonexistent_deployment(self):
        resource_path = '/deployments/{0}/executions'.format('doesnotexist')
        response = self.get(resource_path)
        self.assertEqual(404, response.status_code)

    def test_get_workflows_of_deployment(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self._put_test_deployment()

        resource_path = '/deployments/{0}/workflows'.format(deployment_id)
        workflows = self.get(resource_path).json
        self.assertEquals(workflows['blueprintId'], blueprint_id)
        self.assertEquals(workflows['deploymentId'], deployment_id)
        self.assertEquals(2, len(workflows['workflows']))
        self.assertEquals(workflows['workflows'][0]['name'], 'install')
        self.assertTrue('createdAt' in workflows['workflows'][0])
        self.assertEquals(workflows['workflows'][1]['name'], 'uninstall')
        self.assertTrue('createdAt' in workflows['workflows'][1])

    def test_get_nodes_of_deployment(self):

        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self._put_test_deployment()

        resource_path = '/deployments/{0}/nodes'\
                        .format(deployment_id)
        nodes = self.get(resource_path).json
        self.assertEquals(deployment_id, nodes['deploymentId'])
        self.assertEquals(2, len(nodes['nodes']))

        def assert_node_exists(starts_with):
            self.assertTrue(any(map(
                lambda n: n['id'].startswith(starts_with),
                nodes['nodes'])),
                'Failed finding node with prefix {0}'.format(starts_with))
        assert_node_exists('vm')
        assert_node_exists('http_web_server')

    def test_execute_more_than_one_workflow_fails(self):
        previous_method = mocks.get_workflow_status

        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self._put_test_deployment()
        resource_path = '/deployments/{0}/executions'.format(deployment_id)
        self.post(resource_path, {
            'workflowId': 'install'
        })
        try:
            mocks.get_workflow_status = lambda wfid: 'running'
            response = self.post(resource_path, {
                'workflowId': 'install'
            })
            self.assertEqual(response.status_code, 400)
        finally:
            mocks.get_workflow_status = previous_method

    def test_execute_more_than_one_workflow_succeeds_with_force(self):
        previous_method = mocks.get_workflow_status

        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self._put_test_deployment()
        resource_path = '/deployments/{0}/executions'.format(deployment_id)
        self.post(resource_path, {
            'workflowId': 'install'
        })
        try:
            mocks.get_workflow_status = lambda wfid: 'running'
            response = self.post(resource_path, {
                'workflowId': 'install'
            }, query_params={'force': 'true'})
            self.assertEqual(response.status_code, 201)
        finally:
            mocks.get_workflow_status = previous_method

    def test_get_non_existent_execution(self):
        resource_path = '/executions/idonotexist'
        response = self.get(resource_path)
        self.assertEqual(response.status_code, 404)
