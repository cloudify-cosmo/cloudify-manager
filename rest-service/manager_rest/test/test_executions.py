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
from manager_rest import manager_exceptions
from manager_rest import models


class ExecutionsTestCase(BaseServerTestCase):

    DEPLOYMENT_ID = 'deployment'

    def test_get_deployment_executions_empty(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_test_deployment(self.DEPLOYMENT_ID)
        executions = self.get('/deployments/{0}/executions'
                              .format(deployment_response['id'])).json
        # expecting 1 execution (workers installation)
        self.assertEquals(1, len(executions))
        self.assertEquals('workers_installation',
                          executions[0]['workflow_id'])

    def test_get_execution_by_id(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_test_deployment(self.DEPLOYMENT_ID)

        resource_path = '/deployments/{0}/executions'.format(deployment_id)
        execution = self.post(resource_path, {
            'workflow_id': 'install'
        }).json
        get_execution_resource = '/executions/{0}'.format(execution['id'])
        get_execution = self.get(get_execution_resource).json
        self.assertEquals(get_execution['status'], 'terminated')
        self.assertEquals(get_execution['blueprint_id'], blueprint_id)
        self.assertEquals(get_execution['deployment_id'],
                          deployment_response['id'])
        self.assertIsNotNone(get_execution['created_at'])

        return execution

    def test_execute_with_extra_parameters(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_test_deployment(self.DEPLOYMENT_ID)

        resource_path = '/deployments/{0}/executions'.format(deployment_id)
        parameters = {'param1': 'val1', 'param2': 'val2'}
        execution = self.post(resource_path, {
            'workflow_id': 'install',
            'parameters': parameters
        }).json
        get_execution_resource = '/executions/{0}'.format(execution['id'])
        execution = self.get(get_execution_resource).json
        # expecting an empty parameters dictionary since the parameters were
        #  never defined in the blueprint
        self.assertEqual(dict(), execution['parameters'])

    def test_get_execution_parameters(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_test_deployment(
             self.DEPLOYMENT_ID, 'blueprint_with_workflows.yaml')

        resource_path = '/deployments/{0}/executions'.format(deployment_id)
        parameters = {'mandatory_param': 'value'}
        execution = self.post(resource_path, {
            'workflow_id': 'mock_workflow',
            'parameters': parameters
        }).json
        get_execution_resource = '/executions/{0}'.format(execution['id'])
        execution = self.get(get_execution_resource).json
        expected_executions_params = {
            'mandatory_param': 'value',
            'optional_param': 'test_default_value',
            'nested_param': {
                'key': 'test_key',
                'value': 'test_value'
            }
        }
        self.assertEqual(expected_executions_params, execution['parameters'])

    def test_execution_parameters_override_over_workflow_parameters(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_test_deployment(
             self.DEPLOYMENT_ID, 'blueprint_with_workflows.yaml')

        resource_path = '/deployments/{0}/executions'.format(deployment_id)
        # overriding 'optional_param' with a value of a different type
        parameters = {'mandatory_param': 'value',
                      'optional_param': {'overridden_value': 'obj'}}
        execution = self.post(resource_path, {
            'workflow_id': 'mock_workflow',
            'parameters': parameters
        }).json
        get_execution_resource = '/executions/{0}'.format(execution['id'])
        execution = self.get(get_execution_resource).json
        expected_executions_params = {
            'mandatory_param': 'value',
            'optional_param': {'overridden_value': 'obj'},
            'nested_param': {
                'key': 'test_key',
                'value': 'test_value'
            }
        }
        self.assertEqual(expected_executions_params, execution['parameters'])

    def test_execution_parameters_override_no_recursive_merge(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_test_deployment(
             self.DEPLOYMENT_ID, 'blueprint_with_workflows.yaml')

        resource_path = '/deployments/{0}/executions'.format(deployment_id)
        # overriding one of 'nested_param' subfields
        parameters = {'mandatory_param': 'value',
                      'nested_param': {'key': 'overridden_value'}}
        execution = self.post(resource_path, {
            'workflow_id': 'mock_workflow',
            'parameters': parameters
        }).json
        get_execution_resource = '/executions/{0}'.format(execution['id'])
        execution = self.get(get_execution_resource).json
        # expecting 'nested_param' to only have the one subfield - there's
        # no recursive merge for parameters, so the second key ('value')
        # should no longer appear
        expected_executions_params = {
            'mandatory_param': 'value',
            'optional_param': 'test_default_value',
            'nested_param': {
                'key': 'overridden_value'
            }
        }
        self.assertEqual(expected_executions_params, execution['parameters'])

    def test_missing_execution_parameters(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_test_deployment(
             self.DEPLOYMENT_ID, 'blueprint_with_workflows.yaml')

        resource_path = '/deployments/{0}/executions'.format(deployment_id)
        parameters = {'optional_param': 'some_value'}
        response = self.post(resource_path, {
            'workflow_id': 'mock_workflow',
            'parameters': parameters
        })
        self.assertEquals(400, response.status_code)
        self.assertEquals(
            response.json['error_code'],
            manager_exceptions.MissingExecutionParametersError.
            MISSING_EXECUTION_PARAMETERS_ERROR_CODE)

    def test_bad_execution_parameters(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_test_deployment(
             self.DEPLOYMENT_ID, 'blueprint_with_workflows.yaml')

        resource_path = '/deployments/{0}/executions'.format(deployment_id)
        parameters = 'not_a_dictionary'
        response = self.post(resource_path, {
            'workflow_id': 'mock_workflow',
            'parameters': parameters
        })
        self.assertEquals(400, response.status_code)
        self.assertEquals(
            response.json['error_code'],
            manager_exceptions.BadParametersError.BAD_PARAMETERS_ERROR_CODE)

        parameters = '[still_not_a_dictionary]'
        response = self.post(resource_path, {
            'workflow_id': 'mock_workflow',
            'parameters': parameters
        })
        self.assertEquals(400, response.status_code)
        self.assertEquals(
            response.json['error_code'],
            manager_exceptions.BadParametersError.BAD_PARAMETERS_ERROR_CODE)

    def test_passing_parameters_parameter_to_execute(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_test_deployment(
             self.DEPLOYMENT_ID, 'blueprint_with_workflows.yaml')

        # passing a None parameters value to the execution
        resource_path = '/deployments/{0}/executions'.format(deployment_id)
        parameters = None
        response = self.post(resource_path, {
            'workflow_id': 'install',
            'parameters': parameters
        })
        self.assertEquals(201, response.status_code)
        get_execution_resource = '/executions/{0}'.format(response.json['id'])
        execution = self.get(get_execution_resource).json
        self.assertEquals('terminated', execution['status'])

    def test_bad_update_execution_status(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_test_deployment(self.DEPLOYMENT_ID)

        resource_path = '/deployments/{0}/executions'.format(deployment_id)
        execution = self.post(resource_path, {
            'workflow_id': 'install'
        }).json
        get_execution_resource = '/executions/{0}'.format(execution['id'])
        execution = self.get(get_execution_resource).json
        self.assertEquals('terminated', execution['status'])
        # making a bad update request - not passing the required 'status'
        # parameter
        resp = self.patch('/executions/{0}'.format(execution['id']), {})
        self.assertEquals(400, resp.status_code)
        self.assertTrue('status' in resp.json['message'])
        self.assertEquals(
            resp.json['error_code'],
            manager_exceptions.BadParametersError.BAD_PARAMETERS_ERROR_CODE)

    def test_update_execution_status(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_test_deployment(self.DEPLOYMENT_ID)

        resource_path = '/deployments/{0}/executions'.format(deployment_id)
        execution = self.post(resource_path, {
            'workflow_id': 'install'
        }).json
        get_execution_resource = '/executions/{0}'.format(execution['id'])
        execution = self.get(get_execution_resource).json
        self.assertEquals('terminated', execution['status'])
        self._modify_execution_status(execution['id'], 'new_status')

    def test_update_execution_status_with_error(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_test_deployment(self.DEPLOYMENT_ID)

        resource_path = '/deployments/{0}/executions'.format(deployment_id)
        execution = self.post(resource_path, {
            'workflow_id': 'install'
        }).json
        get_execution_resource = '/executions/{0}'.format(execution['id'])
        execution = self.get(get_execution_resource).json
        self.assertEquals('terminated', execution['status'])
        self.assertEquals('', execution['error'])
        execution = self.patch('/executions/{0}'.format(execution['id']),
                               {'status': 'new-status',
                                'error': 'some error'}).json
        self.assertEquals('new-status', execution['status'])
        self.assertEquals('some error', execution['error'])
        # verifying that updating only the status field also resets the
        # error field to an empty string
        execution = self._modify_execution_status(execution['id'],
                                                  'final-status')
        self.assertEquals('', execution['error'])

    def test_update_nonexistent_execution(self):
        resp = self.patch('/executions/1234', {'status': 'new-status'})
        self.assertEquals(404, resp.status_code)

    def test_cancel_execution_by_id(self):
        execution = self.test_get_execution_by_id()
        # modifying execution status back to 'pending' to 'cancel' will be a
        #  legal action
        resource_path = '/executions/{0}'.format(execution['id'])
        execution = self._modify_execution_status(execution['id'], 'pending')

        cancel_response = self.post(resource_path, {
            'action': 'cancel'
        }).json
        execution['status'] = models.Execution.CANCELLING
        self.assertEquals(execution, cancel_response)

    def test_force_cancel_execution_by_id(self):
        execution = self.test_get_execution_by_id()
        # modifying execution status back to 'pending' to 'cancel' will be a
        #  legal action
        resource_path = '/executions/{0}'.format(execution['id'])
        execution = self._modify_execution_status(execution['id'], 'pending')

        cancel_response = self.post(
            resource_path, {'action': 'force-cancel'}).json
        execution['status'] = models.Execution.FORCE_CANCELLING
        self.assertEquals(execution, cancel_response)

    def test_illegal_cancel_on_execution(self):
        # tests for attempts to cancel an execution which is in a status
        # that is illegal to call cancel for
        execution = self.test_get_execution_by_id()
        resource_path = '/executions/{0}'.format(execution['id'])

        def attempt_cancel_on_status(new_status,
                                     force=False,
                                     expect_failure=True):
            self._modify_execution_status(execution['id'], new_status)

            action = 'force-cancel' if force else 'cancel'
            cancel_response = self.post(resource_path, {'action': action})
            if expect_failure:
                self.assertEquals(400, cancel_response.status_code)
                self.assertEquals(
                    manager_exceptions.IllegalActionError.
                    ILLEGAL_ACTION_ERROR_CODE,
                    cancel_response.json['error_code'])
            else:
                self.assertEquals(201, cancel_response.status_code)
                expected_status = models.Execution.FORCE_CANCELLING if force\
                    else models.Execution.CANCELLING
                self.assertEquals(expected_status,
                                  cancel_response.json['status'])

        # end states - can't either cancel or force-cancel
        attempt_cancel_on_status(models.Execution.TERMINATED)
        attempt_cancel_on_status(models.Execution.TERMINATED, True)
        attempt_cancel_on_status(models.Execution.FAILED)
        attempt_cancel_on_status(models.Execution.FAILED, True)
        attempt_cancel_on_status(models.Execution.CANCELLED)
        attempt_cancel_on_status(models.Execution.CANCELLED, True)

        # force-cancelling status - can't either cancel or force-cancel
        attempt_cancel_on_status(models.Execution.FORCE_CANCELLING)
        attempt_cancel_on_status(models.Execution.FORCE_CANCELLING, True)

        # cancelling state - can only override with force-cancel
        attempt_cancel_on_status(models.Execution.CANCELLING)
        attempt_cancel_on_status(models.Execution.CANCELLING, True, False)

        # pending and started states - can both cancel and force-cancel
        attempt_cancel_on_status(models.Execution.PENDING, False, False)
        attempt_cancel_on_status(models.Execution.PENDING, True, False)
        attempt_cancel_on_status(models.Execution.STARTED, False, False)
        attempt_cancel_on_status(models.Execution.STARTED, True, False)

    def test_cancel_non_existent_execution(self):
        resource_path = '/executions/do_not_exist'
        cancel_response = self.post(resource_path, {
            'action': 'cancel'
        })
        self.assertEquals(cancel_response.status_code, 404)
        self.assertEquals(
            cancel_response.json['error_code'],
            manager_exceptions.NotFoundError.NOT_FOUND_ERROR_CODE)

    def test_execution_bad_action(self):
        execution = self.test_get_execution_by_id()
        resource_path = '/executions/{0}'.format(execution['id'])
        cancel_response = self.post(resource_path, {
            'action': 'not_really_cancel'
        })
        self.assertEquals(cancel_response.status_code, 400)
        self.assertEquals(
            cancel_response.json['error_code'],
            manager_exceptions.BadParametersError.BAD_PARAMETERS_ERROR_CODE)

    def test_cancel_no_action(self):
        execution = self.test_get_execution_by_id()
        resource_path = '/executions/{0}'.format(execution['id'])
        cancel_response = self.post(resource_path, {
            'not_action': 'some_value'
        })
        self.assertEquals(cancel_response.status_code, 400)

    def test_execute_more_than_one_workflow_fails(self):
        self._test_execute_more_than_one_workflow(False, 400)

    def test_execute_more_than_one_workflow_succeeds_with_force(self):
        self._test_execute_more_than_one_workflow(True, 201)

    def _test_execute_more_than_one_workflow(self, is_use_force,
                                             expected_status_code):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_test_deployment(self.DEPLOYMENT_ID)
        resource_path = '/deployments/{0}/executions'.format(deployment_id)
        execution = self.post(resource_path, {
            'workflow_id': 'install'
        }).json

        self._modify_execution_status(execution['id'], 'pending')

        response = self.post(resource_path, {
            'workflow_id': 'install'
        }, query_params={'force': is_use_force})
        self.assertEqual(expected_status_code, response.status_code)

    def test_get_non_existent_execution(self):
        resource_path = '/executions/idonotexist'
        response = self.get(resource_path)
        self.assertEqual(response.status_code, 404)

    def _modify_execution_status(self, execution_id, new_status):
        resource_path = '/executions/{0}'.format(execution_id)
        execution = self.patch(resource_path, {'status': new_status}).json
        self.assertEquals(new_status, execution['status'])
        return execution
