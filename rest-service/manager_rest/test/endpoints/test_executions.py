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


from datetime import datetime
from itertools import dropwhile

import mock
from nose.plugins.attrib import attr

from manager_rest.test.base_test import BaseServerTestCase
from manager_rest.test.base_test import LATEST_API_VERSION
from cloudify_rest_client import exceptions
from manager_rest import manager_exceptions
from manager_rest import models
from manager_rest.storage import storage_manager
from manager_rest import utils


@attr(client_min_version=1, client_max_version=LATEST_API_VERSION)
class ExecutionsTestCase(BaseServerTestCase):

    DEPLOYMENT_ID = 'deployment'

    def test_get_deployment_executions_empty(self):
        _, deployment_id, _, _ = self.put_deployment(self.DEPLOYMENT_ID)
        executions = self.client.executions.list(deployment_id=deployment_id)

        # expecting 1 execution (create_deployment_environment)
        self.assertEquals(1, len(executions))
        self.assertEquals('create_deployment_environment',
                          executions[0]['workflow_id'])

    def test_get_execution_by_id(self):
        (blueprint_id, deployment_id, _,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        execution = self.client.executions.start(deployment_id, 'install')
        get_execution = self.client.executions.get(execution.id)
        self.assertEquals(get_execution.status, 'terminated')
        self.assertEquals(get_execution['blueprint_id'], blueprint_id)
        self.assertEquals(get_execution['deployment_id'],
                          deployment_response['id'])
        self.assertIsNotNone(get_execution['created_at'])

        return get_execution

    def test_list_system_executions(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        # manually pushing a system workflow execution to the storage
        system_wf_execution_id = 'mock_execution_id'
        system_wf_id = 'mock_system_workflow_id'
        system_wf_execution = models.Execution(
            id=system_wf_execution_id,
            status=models.Execution.TERMINATED,
            deployment_id=deployment_id,
            workflow_id=system_wf_id,
            blueprint_id=blueprint_id,
            created_at=utils.get_formatted_timestamp(),
            error='',
            parameters=dict(),
            is_system_workflow=True)
        storage_manager._get_instance().put_execution(
            system_wf_execution_id, system_wf_execution)

        # listing only non-system workflow executions
        executions = self.client.executions.list(deployment_id=deployment_id)

        # expecting 1 execution (create_deployment_environment)
        self.assertEquals(1, len(executions))
        self.assertEquals('create_deployment_environment',
                          executions[0]['workflow_id'])

        # listing all executions
        executions = self.client.executions.list(deployment_id=deployment_id,
                                                 include_system_workflows=True)
        executions.sort(key=lambda e: e.created_at)

        # expecting 2 executions
        self.assertEquals(2, len(executions))
        self.assertEquals('create_deployment_environment',
                          executions[0]['workflow_id'])
        self.assertEquals(system_wf_id, executions[1]['workflow_id'])

        return deployment_id, system_wf_id

    @attr(client_min_version=2.1,
          client_max_version=LATEST_API_VERSION)
    def test_sort_list(self):
        execution1 = models.Execution(
            id='0',
            status=models.Execution.TERMINATED,
            deployment_id='',
            workflow_id='',
            blueprint_id='',
            created_at=datetime.now().isoformat(),
            error='',
            parameters=dict(),
            is_system_workflow=False
        )
        execution2 = models.Execution(
            id='1',
            status=models.Execution.TERMINATED,
            deployment_id='',
            workflow_id='',
            blueprint_id='',
            created_at=datetime.now().isoformat(),
            error='',
            parameters=dict(),
            is_system_workflow=False
        )
        storage_manager._get_instance().put_execution('0', execution1)
        storage_manager._get_instance().put_execution('1', execution2)

        executions = self.client.executions.list(sort='created_at')
        self.assertEqual(2, len(executions))
        self.assertEqual('0', executions[0].id)
        self.assertEqual('1', executions[1].id)

        executions = self.client.executions.list(
            sort='created_at', is_descending=True)
        self.assertEqual(2, len(executions))
        self.assertEqual('1', executions[0].id)
        self.assertEqual('0', executions[1].id)

    @attr(client_min_version=2,
          client_max_version=LATEST_API_VERSION)
    def test_list_system_executions_with_filters(self):
        deployment_id, system_wf_id = self.test_list_system_executions()

        # explicitly listing only non-system executions
        executions = self.client.executions.list(deployment_id=deployment_id,
                                                 is_system_workflow=False)
        self.assertEquals(1, len(executions))
        self.assertEqual('create_deployment_environment',
                         executions[0]['workflow_id'])

        # listing only system executions
        executions = self.client.executions.list(deployment_id=deployment_id,
                                                 is_system_workflow=True)
        self.assertEquals(1, len(executions))
        self.assertEqual(system_wf_id, executions[0]['workflow_id'])

    def test_execute_with_custom_parameters(self):
        # note that this test also tests for passing custom parameters for an
        #  execution of a workflow which doesn't have any workflow parameters

        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        parameters = {'param1': 'val1', 'param2': 'val2'}
        execution = self.client.executions.start(deployment_id,
                                                 'install',
                                                 parameters,
                                                 allow_custom_parameters=True)
        self.assertEqual(parameters, execution.parameters)

    def test_execute_with_custom_parameters_not_allowed(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        parameters = {'param1': 'val1', 'param2': 'val2'}
        try:
            self.client.executions.start(deployment_id,
                                         'install',
                                         parameters)
        except exceptions.CloudifyClientError, e:
            self.assertEquals(400, e.status_code)
            expected_error = manager_exceptions.IllegalExecutionParametersError
            self.assertEquals(
                expected_error.ILLEGAL_EXECUTION_PARAMETERS_ERROR_CODE,
                e.error_code)
            self.assertIn('param1', e.message)
            self.assertIn('param2', e.message)
            # ensure all custom parameters are mentioned in the error message

    def test_execute_with_mandatory_parameters_types(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(
            self.DEPLOYMENT_ID,
            'blueprint_with_workflows_with_parameters_types.yaml')

        parameters = {
            'mandatory1': 'bla',
            'mandatory2': 6,
            'mandatory_int1': 1,
            'mandatory_int2': 'bla',
            'mandatory_float1': 3.5,
            'mandatory_float2': True,
            'mandatory_str1': 'bla',
            'mandatory_str2': 7,
            'mandatory_bool1': False,
            'mandatory_bool2': 'string_that_is_not_a_boolean'
        }
        try:
            self.client.executions.start(deployment_id,
                                         'mock_workflow',
                                         parameters)
        except exceptions.IllegalExecutionParametersError, e:
            self.assertIn('mandatory_int2', str(e))
            self.assertIn('mandatory_float2', str(e))
            self.assertIn('mandatory_str2', str(e))
            self.assertIn('mandatory_bool2', str(e))
            self.assertNotIn('mandatory1', str(e))
            self.assertNotIn('mandatory2', str(e))
            self.assertNotIn('mandatory_int1', str(e))
            self.assertNotIn('mandatory_float1', str(e))
            self.assertNotIn('mandatory_str1', str(e))
            self.assertNotIn('mandatory_bool1', str(e))
            # check which parameters are mentioned in the error message
        else:
            self.fail()

    def test_execute_with_optional_parameters_types(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(
            self.DEPLOYMENT_ID,
            'blueprint_with_workflows_with_parameters_types.yaml')

        parameters = {
            'mandatory1': False,
            'mandatory2': [],
            'mandatory_int1': '-7',
            'mandatory_int2': 3.5,
            'mandatory_float1': '5.0',
            'mandatory_float2': [],
            'mandatory_str1': u'bla',
            'mandatory_str2': ['bla'],
            'mandatory_bool1': 'tRUe',
            'mandatory_bool2': 0,
            'optional1': 'bla',
            'optional2': 6,
            'optional_int1': 1,
            'optional_int2': 'bla',
            'optional_float1': 3.5,
            'optional_float2': True,
            'optional_str1': 'bla',
            'optional_str2': 7,
            'optional_bool1': False,
            'optional_bool2': 'bla'
        }
        try:
            self.client.executions.start(deployment_id,
                                         'mock_workflow',
                                         parameters)
        except exceptions.IllegalExecutionParametersError, e:
            self.assertIn('mandatory_int2', str(e))
            self.assertIn('mandatory_float2', str(e))
            self.assertIn('mandatory_str2', str(e))
            self.assertIn('mandatory_bool2', str(e))
            self.assertNotIn('mandatory1', str(e))
            self.assertNotIn('mandatory2', str(e))
            self.assertNotIn('mandatory_int1', str(e))
            self.assertNotIn('mandatory_float1', str(e))
            self.assertNotIn('mandatory_str1', str(e))
            self.assertNotIn('mandatory_bool1', str(e))
            # check which parameters are mentioned in the error message
            self.assertIn('optional_int2', str(e))
            self.assertIn('optional_float2', str(e))
            self.assertIn('optional_str2', str(e))
            self.assertIn('optional_bool2', str(e))
            self.assertNotIn('optional1', str(e))
            self.assertNotIn('optional2', str(e))
            self.assertNotIn('optional_int1', str(e))
            self.assertNotIn('optional_float1', str(e))
            self.assertNotIn('optional_str1', str(e))
            self.assertNotIn('optional_bool1', str(e))
        else:
            self.fail()

    def test_execute_with_custom_parameters_types(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(
            self.DEPLOYMENT_ID,
            'blueprint_with_workflows_with_parameters_types.yaml')

        parameters = {
            'mandatory1': False,
            'mandatory2': [],
            'mandatory_int1': -7,
            'mandatory_int2': 3,
            'mandatory_float1': 5.0,
            'mandatory_float2': 0.0,
            'mandatory_str1': u'bla',
            'mandatory_str2': 'bla',
            'mandatory_bool1': 'falSE',
            'mandatory_bool2': False,
            'optional1': 'bla',
            'optional2': 6,
            'optional_int1': 1,
            'optional_int2': 'bla',
            'optional_float1': 3.5,
            'optional_str1': 'bla',
            'optional_bool1': False,
            'custom1': 8,
            'custom2': 3.2,
            'custom3': 'bla',
            'custom4': True
        }
        try:
            self.client.executions.start(deployment_id,
                                         'mock_workflow',
                                         parameters,
                                         allow_custom_parameters=True)
        except exceptions.IllegalExecutionParametersError, e:
            self.assertNotIn('mandatory_int2', str(e))
            self.assertNotIn('mandatory_float2', str(e))
            self.assertNotIn('mandatory_str2', str(e))
            self.assertNotIn('mandatory_bool2', str(e))
            self.assertNotIn('mandatory1', str(e))
            self.assertNotIn('mandatory2', str(e))
            self.assertNotIn('mandatory_int1', str(e))
            self.assertNotIn('mandatory_float1', str(e))
            self.assertNotIn('mandatory_str1', str(e))
            self.assertNotIn('mandatory_bool1', str(e))
            # check which parameters are mentioned in the error message
            self.assertIn('optional_int2', str(e))
            self.assertNotIn('optional_float2', str(e))
            self.assertNotIn('optional_str2', str(e))
            self.assertNotIn('optional_bool2', str(e))
            self.assertNotIn('optional1', str(e))
            self.assertNotIn('optional2', str(e))
            self.assertNotIn('optional_int1', str(e))
            self.assertNotIn('optional_float1', str(e))
            self.assertNotIn('optional_str1', str(e))
            self.assertNotIn('optional_bool1', str(e))

            self.assertNotIn('custom1', str(e))
            self.assertNotIn('custom2', str(e))
            self.assertNotIn('custom3', str(e))
            self.assertNotIn('custom4', str(e))
        else:
            self.fail()

    def test_get_execution_parameters(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(
             self.DEPLOYMENT_ID, 'blueprint_with_workflows.yaml')

        parameters = {'mandatory_param': 'value',
                      'mandatory_param2': 'value2'}
        execution = self.client.executions.start(deployment_id,
                                                 'mock_workflow',
                                                 parameters)
        expected_executions_params = {
            'mandatory_param': 'value',
            'mandatory_param2': 'value2',
            'optional_param': 'test_default_value',
            'nested_param': {
                'key': 'test_key',
                'value': 'test_value'
            }
        }
        self.assertEqual(expected_executions_params, execution.parameters)

    def test_execution_parameters_override_over_workflow_parameters(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(
             self.DEPLOYMENT_ID, 'blueprint_with_workflows.yaml')

        parameters = {'mandatory_param': 'value',
                      'mandatory_param2': 'value2',
                      'optional_param': {'overridden_value': 'obj'}}
        execution = self.client.executions.start(deployment_id,
                                                 'mock_workflow',
                                                 parameters)
        # overriding 'optional_param' with a value of a different type
        expected_executions_params = {
            'mandatory_param': 'value',
            'mandatory_param2': 'value2',
            'optional_param': {'overridden_value': 'obj'},
            'nested_param': {
                'key': 'test_key',
                'value': 'test_value'
            }
        }
        self.assertEqual(expected_executions_params, execution.parameters)

    def test_execution_parameters_override_no_recursive_merge(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(
             self.DEPLOYMENT_ID, 'blueprint_with_workflows.yaml')

        parameters = {'mandatory_param': 'value',
                      'mandatory_param2': 'value2',
                      'nested_param': {'key': 'overridden_value'}}
        execution = self.client.executions.start(deployment_id,
                                                 'mock_workflow',
                                                 parameters)
        # expecting 'nested_param' to only have the one subfield - there's
        # no recursive merge for parameters, so the second key ('value')
        # should no longer appear
        expected_executions_params = {
            'mandatory_param': 'value',
            'mandatory_param2': 'value2',
            'optional_param': 'test_default_value',
            'nested_param': {
                'key': 'overridden_value'
            }
        }
        self.assertEqual(expected_executions_params, execution.parameters)

    def test_missing_execution_parameters(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(
             self.DEPLOYMENT_ID, 'blueprint_with_workflows.yaml')

        parameters = {'optional_param': 'some_value'}
        try:
            self.client.executions.start(deployment_id,
                                         'mock_workflow',
                                         parameters)
            self.fail()
        except exceptions.CloudifyClientError, e:
            self.assertEquals(400, e.status_code)
            error = manager_exceptions.IllegalExecutionParametersError
            self.assertEquals(
                error.ILLEGAL_EXECUTION_PARAMETERS_ERROR_CODE,
                e.error_code)
            # ensure all missing mandatory parameters are mentioned in message
            self.assertIn('mandatory_param', e.message)
            self.assertIn('mandatory_param2', e.message)

    def test_bad_execution_parameters(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(
             self.DEPLOYMENT_ID, 'blueprint_with_workflows.yaml')
        try:
            self.client.executions.start(deployment_id,
                                         'mock_workflow',
                                         'not_a_dictionary')
            self.fail()
        except exceptions.CloudifyClientError, e:
            self.assertEqual(400, e.status_code)
            bad_params_error = manager_exceptions.BadParametersError
            self.assertEqual(bad_params_error.BAD_PARAMETERS_ERROR_CODE,
                             e.error_code)
        try:
            self.client.executions.start(deployment_id,
                                         'mock_workflow',
                                         '[still_not_a_dictionary]')
            self.fail()
        except exceptions.CloudifyClientError, e:
            self.assertEqual(400, e.status_code)
            bad_params_error = manager_exceptions.BadParametersError
            self.assertEqual(bad_params_error.BAD_PARAMETERS_ERROR_CODE,
                             e.error_code)

    def test_passing_parameters_parameter_to_execute(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(
             self.DEPLOYMENT_ID, 'blueprint_with_workflows.yaml')

        # passing a None parameters value to the execution
        execution = self.client.executions.start(deployment_id, 'install')
        execution = self.client.executions.get(execution.id)
        self.assertEquals('terminated', execution.status)

    def test_bad_parameters_on_update_execution_status(self):
        _, deployment_id, _, _ = self.put_deployment(self.DEPLOYMENT_ID)

        execution = self.client.executions.start(deployment_id, 'install')
        execution = self.client.executions.get(execution.id)
        self.assertEquals('terminated', execution.status)
        # making a bad update request - not passing the required 'status'
        # parameter
        resp = self.patch('/executions/{0}'.format(execution['id']), {})
        self.assertEquals(400, resp.status_code)
        self.assertTrue('status' in resp.json['message'])
        self.assertEquals(
            resp.json['error_code'],
            manager_exceptions.BadParametersError.BAD_PARAMETERS_ERROR_CODE)

    def test_bad_update_execution_status(self):
        execution = self.test_get_execution_by_id()
        resource_path = '/executions/{0}'.format(execution['id'])
        expected_error = manager_exceptions.InvalidExecutionUpdateStatus()
        expected_message = (
            "Invalid relationship - can't change status from {0} to {1}")

        force_cancelling_invalid_future_statuses = (
            models.Execution.ACTIVE_STATES + [models.Execution.TERMINATED])
        cancelling_invalid_future_statuses = dropwhile(
            lambda status: status == models.Execution.CANCELLING,
            force_cancelling_invalid_future_statuses)
        invalid_status_map = {
            models.Execution.TERMINATED: models.Execution.STATES,
            models.Execution.FAILED: models.Execution.STATES,
            models.Execution.CANCELLED: models.Execution.STATES,
            models.Execution.CANCELLING: cancelling_invalid_future_statuses,
            models.Execution.FORCE_CANCELLING:
                force_cancelling_invalid_future_statuses,
        }

        def assert_invalid_update():
            self._modify_execution_status_in_database(
                execution=execution, new_status=last_status)
            response = self.patch(resource_path, {'status': next_status})
            self.assertEqual(
                expected_error.http_code, response.status_code)
            self.assertEqual(
                expected_error.error_code, response.json['error_code'])
            self.assertEqual(
                expected_message.format(last_status, next_status),
                response.json['message'])

        for last_status, status_list in invalid_status_map.iteritems():
            for next_status in status_list:
                assert_invalid_update()

    @attr(client_min_version=2.1, client_max_version=LATEST_API_VERSION)
    def test_bad_update_execution_status_client_exception(self):
        execution = self.test_get_execution_by_id()
        expected_message = (
            "Invalid relationship - can't change status from {0} to {1}")
        last_status = models.Execution.TERMINATED
        next_status = models.Execution.STARTED
        self._modify_execution_status_in_database(
            execution=execution,
            new_status=last_status)

        try:
            self.client.executions.update(
                execution_id=execution['id'],
                status=next_status,
                error='')
            self.fail('changing status from {0} to {1} should raise error'
                      .format(last_status, next_status))
        except exceptions.InvalidExecutionUpdateStatus as exc:
            self.assertEqual(400, exc.status_code)
            self.assertEqual(
                exceptions.InvalidExecutionUpdateStatus.ERROR_CODE,
                exc.error_code)
            self.assertIn(
                expected_message.format(last_status, next_status),
                str(exc))

    def test_update_execution_status(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        execution = self.client.executions.start(deployment_id, 'install')
        execution = self.client.executions.get(execution.id)
        self.assertEquals('terminated', execution.status)
        self._modify_execution_status_in_database(
            execution, models.Execution.STARTED)
        self._modify_execution_status(execution.id, 'new_status')

    def test_update_execution_status_with_error(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        execution = self.client.executions.start(deployment_id, 'install')
        execution = self.client.executions.get(execution.id)
        self.assertEquals('terminated', execution.status)
        self.assertEquals('', execution.error)
        self._modify_execution_status_in_database(
            execution, models.Execution.STARTED)

        execution = self.client.executions.update(
            execution.id, 'new-status', 'some error')
        self.assertEquals('new-status', execution.status)
        self.assertEquals('some error', execution.error)
        # verifying that updating only the status field also resets the
        # error field to an empty string
        execution = self._modify_execution_status(
            execution.id, 'final-status')
        self.assertEquals('', execution.error)

    def test_update_nonexistent_execution(self):
        resp = self.patch('/executions/1234', {'status': 'new-status'})
        self.assertEquals(404, resp.status_code)

    def test_cancel_execution_by_id(self):
        execution = self.test_get_execution_by_id()
        # modifying execution status back to 'pending' to 'cancel' will be a
        #  legal action
        self._modify_execution_status_in_database(
            execution=execution,
            new_status=models.Execution.PENDING)

        resource_path = '/executions/{0}'.format(execution['id'])
        cancel_response = self.post(resource_path, {
            'action': 'cancel'
        }).json
        execution['status'] = models.Execution.CANCELLING
        self.assertEquals(execution, cancel_response)

    def test_force_cancel_execution_by_id(self):
        execution = self.test_get_execution_by_id()
        self._modify_execution_status_in_database(
            execution=execution,
            new_status=models.Execution.PENDING)
        resource_path = '/executions/{0}'.format(execution['id'])

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
            self._modify_execution_status_in_database(execution, new_status)

            action = 'force-cancel' if force else 'cancel'
            cancel_response = self.post(resource_path, {'action': action})
            if expect_failure:
                self.assertEquals(400, cancel_response.status_code)
                self.assertEquals(
                    manager_exceptions.IllegalActionError.
                    ILLEGAL_ACTION_ERROR_CODE,
                    cancel_response.json['error_code'])
            else:
                self.assertEquals(200, cancel_response.status_code)
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
        expected_status_code = 201
        self._test_execute_more_than_one_workflow(True, expected_status_code)

    def _test_execute_more_than_one_workflow(self, is_use_force,
                                             expected_status_code):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        execution = self.client.executions.start(deployment_id, 'install')
        self._modify_execution_status_in_database(
            execution=execution,
            new_status=models.Execution.PENDING)

        if expected_status_code < 400:
            self.client.executions.start(deployment_id,
                                         'install',
                                         force=is_use_force)
        else:
            try:
                self.client.executions.start(deployment_id,
                                             'install',
                                             force=is_use_force)
                self.fail()
            except exceptions.CloudifyClientError, e:
                self.assertEqual(expected_status_code, e.status_code)

    def test_get_non_existent_execution(self):
        resource_path = '/executions/idonotexist'
        response = self.get(resource_path)
        self.assertEqual(response.status_code, 404)

    def test_start_execution_dep_env_pending(self):
        self._test_start_execution_dep_env(
            models.Execution.PENDING,
            exceptions.DeploymentEnvironmentCreationPendingError)

    def test_start_execution_dep_env_in_progress(self):
        self._test_start_execution_dep_env(
            models.Execution.STARTED,
            exceptions.DeploymentEnvironmentCreationInProgressError)

    def _test_start_execution_dep_env(self, task_state, expected_ex):
        with mock.patch('manager_rest.test.mocks.task_state',
                        return_value=task_state):
            _, deployment_id, _, _ = self.put_deployment(self.DEPLOYMENT_ID)
        self.assertRaises(expected_ex, self.client.executions.start,
                          deployment_id, 'install')

    def _modify_execution_status(self, execution_id, new_status):
        execution = self.client.executions.update(execution_id, new_status)
        self.assertEquals(new_status, execution.status)
        return execution

    def _modify_execution_status_in_database(
            self, execution, new_status):
        try:
            execution_id = execution['id']
        except TypeError:
            execution_id = execution.id
        storage_manager._get_instance().update_execution_status(
            execution_id, new_status, error='')
        updated_execution = self.client.executions.get(
            execution_id=execution_id)
        self.assertEqual(new_status, updated_execution['status'])
