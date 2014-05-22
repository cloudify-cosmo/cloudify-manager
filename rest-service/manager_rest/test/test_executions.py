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

__author__ = 'ran'


import mocks
from base_test import BaseServerTestCase


class ExecutionsTestCase(BaseServerTestCase):

    DEPLOYMENT_ID = 'deployment'

    def test_get_deployment_executions_empty(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_test_deployment(self.DEPLOYMENT_ID)
        get_executions = self.get('/deployments/{0}/executions'
            .format(deployment_response['id'])).json
        self.assertEquals(len(get_executions), 0)

    def test_get_execution_by_id(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_test_deployment(self.DEPLOYMENT_ID)

        resource_path = '/deployments/{0}/executions'.format(deployment_id)
        execution = self.post(resource_path, {
            'workflowId': 'install'
        }).json
        get_execution_resource = '/executions/{0}'.format(execution['id'])
        get_execution = self.get(get_execution_resource).json
        self.assertEquals(get_execution['status'], 'pending')
        self.assertEquals(get_execution['blueprintId'], blueprint_id)
        self.assertEquals(get_execution['deploymentId'],
                          deployment_response['id'])
        self.assertIsNotNone(get_execution['createdAt'])

        return execution

    # def test_update_execution_status(self):
    #     (blueprint_id, deployment_id, blueprint_response,
    #      deployment_response) = self.put_test_deployment(self.DEPLOYMENT_ID)
    #
    #     resource_path = '/deployments/{0}/executions'.format(deployment_id)
    #     execution = self.post(resource_path, {
    #         'workflowId': 'install'
    #     }).json
    #     get_execution_resource = '/executions/{0}'.format(execution['id'])
    #     execution = self.get(get_execution_resource).json
    #     self.assertEquals(, execution['status'])

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

    def test_execute_more_than_one_workflow_fails(self):
        previous_method = mocks.get_workflow_status

        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_test_deployment(self.DEPLOYMENT_ID)
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
         deployment_response) = self.put_test_deployment(self.DEPLOYMENT_ID)
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