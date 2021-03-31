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

import uuid
import hashlib
from itertools import dropwhile
from datetime import datetime, timedelta

import mock

from cloudify_rest_client import exceptions
from cloudify.models_states import ExecutionState
from cloudify.workflows import tasks as cloudify_tasks
from cloudify.constants import CLOUDIFY_EXECUTION_TOKEN_HEADER

from manager_rest.storage import models
from manager_rest import utils, manager_exceptions
from manager_rest.test.attribute import attr
from manager_rest.test.base_test import BaseServerTestCase, LATEST_API_VERSION


@attr(client_min_version=1, client_max_version=LATEST_API_VERSION)
class ExecutionsTestCase(BaseServerTestCase):

    DEPLOYMENT_ID = 'deployment'

    def _test_start_execution_dep_env(self, task_state, expected_ex):
        with mock.patch('manager_rest.test.mocks.task_state',
                        return_value=task_state):
            _, deployment_id, _, _ = self.put_deployment(self.DEPLOYMENT_ID)
        self.assertRaises(expected_ex, self.client.executions.start,
                          deployment_id, 'install')

    def _modify_execution_status(self, execution_id, new_status):
        execution = self.client.executions.update(execution_id, new_status)
        self.assertEqual(new_status, execution.status)
        return execution

    def _modify_execution_status_in_database(
            self, execution, new_status):
        try:
            execution_id = execution['id']
        except TypeError:
            execution_id = execution.id
        execution = self.sm.get(models.Execution, execution_id)
        execution.status = new_status
        self.sm.update(execution)
        updated_execution = self.client.executions.get(
            execution_id=execution_id)
        self.assertEqual(new_status, updated_execution['status'])

    def test_get_deployment_executions_empty(self):
        _, deployment_id, _, _ = self.put_deployment(self.DEPLOYMENT_ID)
        executions = self.client.executions.list(deployment_id=deployment_id)

        # expecting 1 execution (create_deployment_environment)
        self.assertEqual(1, len(executions))
        self.assertEqual('create_deployment_environment',
                         executions[0]['workflow_id'])

    def test_get_execution_by_id(self):
        (blueprint_id, deployment_id, _,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        execution = self.client.executions.start(deployment_id, 'install')
        get_execution = self.client.executions.get(execution.id)
        self.assertEqual(get_execution.status, 'terminated')
        self.assertEqual(get_execution['blueprint_id'], blueprint_id)
        self.assertEqual(get_execution['deployment_id'],
                         deployment_response['id'])
        self.assertIsNotNone(get_execution['created_at'])
        self.assertIsNotNone(get_execution['ended_at'])

        return get_execution

    def test_list_system_executions(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(
            deployment_id=self.DEPLOYMENT_ID)

        # manually pushing a system workflow execution to the storage
        system_wf_execution_id = 'mock_execution_id'
        system_wf_id = 'mock_system_workflow_id'
        system_wf_execution = models.Execution(
            id=system_wf_execution_id,
            status=ExecutionState.TERMINATED,
            workflow_id=system_wf_id,
            created_at=utils.get_formatted_timestamp(),
            error='',
            parameters=dict(),
            is_system_workflow=True,
            blueprint_id=blueprint_id
        )
        deployment = self.sm.get(models.Deployment, deployment_id)
        system_wf_execution.deployment = deployment
        self.sm.put(system_wf_execution)

        # listing only non-system workflow executions
        executions = self.client.executions.list(deployment_id=deployment_id)

        # expecting 1 execution (create_deployment_environment)
        self.assertEqual(1, len(executions))
        self.assertEqual('create_deployment_environment',
                         executions[0]['workflow_id'])

        # listing all executions
        executions = self.client.executions.list(deployment_id=deployment_id,
                                                 include_system_workflows=True)
        executions.sort(key=lambda e: e.created_at)

        # expecting 2 executions
        self.assertEqual(2, len(executions))
        self.assertEqual('create_deployment_environment',
                         executions[0]['workflow_id'])
        self.assertEqual(system_wf_id, executions[1]['workflow_id'])

        return deployment_id, system_wf_id

    @attr(client_min_version=3,
          client_max_version=LATEST_API_VERSION)
    def test_sort_list(self):
        blueprint = self._add_blueprint()
        deployment = self._add_deployment(blueprint)
        self._add_execution(deployment, '0')
        self._add_execution(deployment, '1')

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
        self.assertEqual(1, len(executions))
        self.assertEqual('create_deployment_environment',
                         executions[0]['workflow_id'])

        # listing only system executions
        executions = self.client.executions.list(deployment_id=deployment_id,
                                                 is_system_workflow=True)
        self.assertEqual(1, len(executions))
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
        # ensure all custom parameters are mentioned in the error message,
        # but they can be in any order
        expected_regex = 'param1,param2|param2,param1'
        with self.assertRaisesRegex(
                exceptions.CloudifyClientError, expected_regex) as cm:
            self.client.executions.start(deployment_id,
                                         'install',
                                         parameters)
        self.assertEqual(
            manager_exceptions.IllegalExecutionParametersError.
            ILLEGAL_EXECUTION_PARAMETERS_ERROR_CODE,
            cm.exception.error_code)

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
        except exceptions.IllegalExecutionParametersError as e:
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
        except exceptions.IllegalExecutionParametersError as e:
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
        except exceptions.IllegalExecutionParametersError as e:
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
        # ensure all custom parameters are mentioned in the error message,
        # but they can be in any order
        expected_regex = 'mandatory_param,mandatory_param2|'\
            'mandatory_param2,mandatory_param'
        with self.assertRaisesRegex(
                exceptions.CloudifyClientError, expected_regex) as cm:
            self.client.executions.start(deployment_id,
                                         'mock_workflow',
                                         parameters)

        self.assertEqual(
            manager_exceptions.IllegalExecutionParametersError.
            ILLEGAL_EXECUTION_PARAMETERS_ERROR_CODE,
            cm.exception.error_code)

    def test_bad_execution_parameters(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(
             self.DEPLOYMENT_ID, 'blueprint_with_workflows.yaml')
        with self.assertRaises(exceptions.CloudifyClientError) as cm:
            self.client.executions.start(deployment_id,
                                         'mock_workflow',
                                         'not_a_dictionary')
        self.assertEqual(
            manager_exceptions.BadParametersError.BAD_PARAMETERS_ERROR_CODE,
            cm.exception.error_code)

        with self.assertRaises(exceptions.CloudifyClientError) as cm:
            self.client.executions.start(deployment_id,
                                         'mock_workflow',
                                         '[still_not_a_dictionary]')
        self.assertEqual(
            manager_exceptions.BadParametersError.BAD_PARAMETERS_ERROR_CODE,
            cm.exception.error_code)

    def test_passing_parameters_parameter_to_execute(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(
             self.DEPLOYMENT_ID, 'blueprint_with_workflows.yaml')

        # passing a None parameters value to the execution
        execution = self.client.executions.start(deployment_id, 'install')
        execution = self.client.executions.get(execution.id)
        self.assertEqual('terminated', execution.status)

    def test_bad_parameters_on_update_execution_status(self):
        _, deployment_id, _, _ = self.put_deployment(self.DEPLOYMENT_ID)

        execution = self.client.executions.start(deployment_id, 'install')
        execution = self.client.executions.get(execution.id)
        self.assertEqual('terminated', execution.status)
        # making a bad update request - not passing the required 'status'
        # parameter
        resp = self.patch('/executions/{0}'.format(execution['id']), {})
        self.assertEqual(400, resp.status_code)
        self.assertTrue('status' in resp.json['message'])
        self.assertEqual(
            resp.json['error_code'],
            manager_exceptions.BadParametersError.BAD_PARAMETERS_ERROR_CODE)

    def test_bad_update_execution_status(self):
        execution = self.test_get_execution_by_id()
        resource_path = '/executions/{0}'.format(execution['id'])
        expected_error = manager_exceptions.InvalidExecutionUpdateStatus()
        expected_message = (
            'Invalid relationship - can\'t change status from {0} to {1}'
            ' for "{2}" execution while running "{3}" workflow.')

        force_cancelling_invalid_future_statuses = (
            ExecutionState.ACTIVE_STATES + [ExecutionState.TERMINATED])
        cancelling_invalid_future_statuses = dropwhile(
            lambda status: status == ExecutionState.CANCELLING,
            force_cancelling_invalid_future_statuses)
        invalid_status_map = {
            ExecutionState.TERMINATED: ExecutionState.STATES,
            ExecutionState.FAILED: ExecutionState.STATES,
            ExecutionState.CANCELLED: ExecutionState.STATES,
            ExecutionState.CANCELLING: cancelling_invalid_future_statuses,
            ExecutionState.FORCE_CANCELLING:
                force_cancelling_invalid_future_statuses,
        }

        def assert_invalid_update():
            self._modify_execution_status_in_database(
                execution=execution, new_status=last_status)
            response = self.patch(resource_path, {'status': next_status})
            self.assertEqual(
                expected_error.status_code, response.status_code)
            self.assertEqual(
                expected_error.error_code, response.json['error_code'])
            self.assertEqual(
                expected_message.format(last_status,
                                        next_status,
                                        execution['id'],
                                        execution['workflow_id']),
                response.json['message'])

        for last_status, status_list in invalid_status_map.items():
            for next_status in status_list:
                assert_invalid_update()

    @attr(client_min_version=2.1, client_max_version=LATEST_API_VERSION)
    def test_bad_update_execution_status_client_exception(self):
        execution = self.test_get_execution_by_id()
        expected_message = (
            'Invalid relationship - can\'t change status from {0} to {1}'
            ' for "{2}" execution while running "{3}" workflow.')
        last_status = ExecutionState.TERMINATED
        next_status = ExecutionState.STARTED
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
                expected_message.format(last_status,
                                        next_status,
                                        execution['id'],
                                        execution['workflow_id']),
                str(exc))

    def test_update_execution_status(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        execution = self.client.executions.start(deployment_id, 'install')
        execution = self.client.executions.get(execution.id)
        self.assertEqual('terminated', execution.status)
        self._modify_execution_status_in_database(
            execution, ExecutionState.STARTED)
        self._modify_execution_status(execution.id, 'pending')

    def test_dequeue_set_tenant(self):
        """After dequeueing, current_tenant is kept intact"""
        exec1 = self.sm.put(models.Execution(
            id=str(uuid.uuid4()),
            created_at=datetime.now(),
            is_system_workflow=True,
            workflow_id='delete_deployment_environment',
            status=ExecutionState.STARTED,
        ))
        self.sm.put(models.Execution(
            id=str(uuid.uuid4()),
            created_at=datetime.now(),
            is_system_workflow=True,
            workflow_id='irrelevant',
            status=ExecutionState.QUEUED,
        ))

        def _mock_delete(*a, **kw):
            # if the tenant was not restored correctly, but to a proxy cycle
            # (CYBL-1139), then this will throw
            self.assertEqual(utils.current_tenant.name, 'default_tenant')

        delete_dep_patch = 'manager_rest.resource_manager.'\
                           'ResourceManager.delete_deployment'
        with mock.patch(delete_dep_patch, side_effect=_mock_delete) as m:
            self._modify_execution_status(exec1.id, 'terminated')
            m.assert_called()

    def test_update_execution_status_with_error(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        execution = self.client.executions.start(deployment_id, 'install')
        execution = self.client.executions.get(execution.id)
        self.assertEqual('terminated', execution.status)
        self.assertEqual('', execution.error)
        self._modify_execution_status_in_database(
            execution, ExecutionState.STARTED)

        execution = self.client.executions.update(
            execution.id, 'pending', 'some error')
        self.assertEqual('pending', execution.status)
        self.assertEqual('some error', execution.error)
        # verifying that updating only the status field also resets the
        # error field to an empty string
        execution = self._modify_execution_status(
            execution.id, 'terminated')
        self.assertEqual('', execution.error)

    def test_update_nonexistent_execution(self):
        resp = self.patch('/executions/1234', {'status': 'new-status'})
        self.assertEqual(404, resp.status_code)

    def test_cancel_execution_by_id(self):
        execution = self.test_get_execution_by_id()
        # modifying execution status back to 'pending' to 'cancel' will be a
        #  legal action
        self._modify_execution_status_in_database(
            execution=execution,
            new_status=ExecutionState.PENDING)

        resource_path = '/executions/{0}'.format(execution['id'])
        cancel_response = self.post(resource_path, {
            'action': 'cancel'
        }).json
        self._assert_execution_status_changed(execution, cancel_response,
                                              ExecutionState.CANCELLING)

    def test_force_cancel_execution_by_id(self):
        execution = self.test_get_execution_by_id()
        self._modify_execution_status_in_database(
            execution=execution,
            new_status=ExecutionState.PENDING)
        resource_path = '/executions/{0}'.format(execution['id'])

        cancel_response = self.post(
            resource_path, {'action': 'force-cancel'}).json
        self._assert_execution_status_changed(execution, cancel_response,
                                              ExecutionState.FORCE_CANCELLING)

    def _assert_execution_status_changed(self, execution, response,
                                         expected_state):
        """Test that the cancel response contains the execution, but
        with a changed state
        """
        skip_fields = ['status', 'status_display']

        def _omit_fields(d, fields):
            return {k: v for k, v in d.items() if k not in fields}

        # check that the execution itself didn't change
        self.assertEqual(_omit_fields(execution, skip_fields),
                         _omit_fields(response, skip_fields))
        # ..and that the execution now has the expected status
        self.assertEqual(response['status'], expected_state)

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
                self.assertEqual(400, cancel_response.status_code)
                self.assertEqual(
                    manager_exceptions.IllegalActionError.
                    ILLEGAL_ACTION_ERROR_CODE,
                    cancel_response.json['error_code'])
            else:
                self.assertEqual(200, cancel_response.status_code)
                expected_status = ExecutionState.FORCE_CANCELLING if force\
                    else ExecutionState.CANCELLING
                self.assertEqual(expected_status,
                                 cancel_response.json['status'])

        # end states - can't either cancel or force-cancel
        attempt_cancel_on_status(ExecutionState.TERMINATED)
        attempt_cancel_on_status(ExecutionState.TERMINATED, True)
        attempt_cancel_on_status(ExecutionState.FAILED)
        attempt_cancel_on_status(ExecutionState.FAILED, True)
        attempt_cancel_on_status(ExecutionState.CANCELLED)
        attempt_cancel_on_status(ExecutionState.CANCELLED, True)

        # force-cancelling status - can't either cancel or force-cancel
        attempt_cancel_on_status(ExecutionState.FORCE_CANCELLING)
        attempt_cancel_on_status(ExecutionState.FORCE_CANCELLING, True)

        # cancelling state - can only override with force-cancel
        attempt_cancel_on_status(ExecutionState.CANCELLING)
        attempt_cancel_on_status(ExecutionState.CANCELLING, True, False)

        # pending and started states - can both cancel and force-cancel
        attempt_cancel_on_status(ExecutionState.PENDING, False, False)
        attempt_cancel_on_status(ExecutionState.PENDING, True, False)
        attempt_cancel_on_status(ExecutionState.STARTED, False, False)
        attempt_cancel_on_status(ExecutionState.STARTED, True, False)

    def test_cancel_non_existent_execution(self):
        resource_path = '/executions/do_not_exist'
        cancel_response = self.post(resource_path, {
            'action': 'cancel'
        })
        self.assertEqual(cancel_response.status_code, 404)
        self.assertEqual(
            cancel_response.json['error_code'],
            manager_exceptions.NotFoundError.NOT_FOUND_ERROR_CODE)

    def test_execution_bad_action(self):
        execution = self.test_get_execution_by_id()
        resource_path = '/executions/{0}'.format(execution['id'])
        cancel_response = self.post(resource_path, {
            'action': 'not_really_cancel'
        })
        self.assertEqual(cancel_response.status_code, 400)
        self.assertEqual(
            cancel_response.json['error_code'],
            manager_exceptions.BadParametersError.BAD_PARAMETERS_ERROR_CODE)

    def test_cancel_no_action(self):
        execution = self.test_get_execution_by_id()
        resource_path = '/executions/{0}'.format(execution['id'])
        cancel_response = self.post(resource_path, {
            'not_action': 'some_value'
        })
        self.assertEqual(cancel_response.status_code, 400)

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
            new_status=ExecutionState.PENDING)

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
            except exceptions.CloudifyClientError as e:
                self.assertEqual(expected_status_code, e.status_code)

    def test_get_non_existent_execution(self):
        resource_path = '/executions/idonotexist'
        response = self.get(resource_path)
        self.assertEqual(response.status_code, 404)

    def test_start_execution_dep_env_pending(self):
        self._test_start_execution_dep_env(
            ExecutionState.PENDING,
            exceptions.DeploymentEnvironmentCreationPendingError)

    def test_start_execution_dep_env_in_progress(self):
        self._test_start_execution_dep_env(
            ExecutionState.STARTED,
            exceptions.DeploymentEnvironmentCreationInProgressError)

    def test_install_empty_blueprint(self):
        (blueprint_id, deployment_id, _,
         deployment_response) = self.put_deployment(
            deployment_id=self.DEPLOYMENT_ID,
            blueprint_file_name='empty_blueprint.yaml')

        execution = self.client.executions.start(deployment_id, 'install')
        get_execution = self.client.executions.get(execution.id)
        self.assertEqual(get_execution.status, 'terminated')
        self.assertEqual(get_execution['blueprint_id'], blueprint_id)
        self.assertEqual(get_execution['deployment_id'],
                         deployment_response['id'])

    def _execution_resume_test(self, deployment, status):
        execution = self.sm.put(models.Execution(
            id=str(uuid.uuid4()),
            _deployment_fk=deployment._storage_id,
            created_at=datetime.now(),
            is_system_workflow=False,
            workflow_id='install',
            status=status,
            blueprint_id=deployment.blueprint_id
        ))
        tasks_graph = self.sm.put(models.TasksGraph(
            _execution_fk=execution._storage_id,
            name='install',
            created_at=datetime.now()
        ))
        operation = self.sm.put(models.Operation(
            _tasks_graph_fk=tasks_graph._storage_id,
            parameters={'current_retries': 20},
            state=cloudify_tasks.TASK_FAILED,
            created_at=datetime.now()
        ))

        self.client.executions.resume(execution.id, force=True)

        operations = self.sm.list(models.Operation, get_all_results=True)
        self.assertEqual(len(operations), 1)
        operation = operations[0]
        self.assertEqual(operation.state, cloudify_tasks.TASK_PENDING)
        self.assertEqual(operation.parameters['current_retries'], 0)

        execution = self.sm.get(models.Execution, execution.id)
        # started or terminated, it might have already finished by the time
        # the test was done
        self.assertIn(execution.status,
                      (ExecutionState.STARTED, ExecutionState.TERMINATED))

    @attr(client_min_version=3.1,
          client_max_version=LATEST_API_VERSION)
    def test_resume_force_failed(self):
        """Force-resume resets operation state and restart count"""
        _, deployment_id, _, _ = self.put_deployment(
            self.DEPLOYMENT_ID, 'empty_blueprint.yaml')
        deployment = self.sm.get(models.Deployment, deployment_id)
        self._execution_resume_test(deployment, ExecutionState.FAILED)

    @attr(client_min_version=3.1,
          client_max_version=LATEST_API_VERSION)
    def test_resume_force_cancelled(self):
        """Force-resume resets operation state and restart count"""
        _, deployment_id, _, _ = self.put_deployment(
            self.DEPLOYMENT_ID, 'empty_blueprint.yaml')
        deployment = self.sm.get(models.Deployment, deployment_id)
        self._execution_resume_test(deployment, ExecutionState.CANCELLED)

    @attr(client_min_version=3.1,
          client_max_version=LATEST_API_VERSION)
    def test_resume_invalid_state(self):
        """Resuming is allowed in the STARTED state"""
        _, deployment_id, _, _ = self.put_deployment(
            self.DEPLOYMENT_ID, 'empty_blueprint.yaml')

        deployment = self.sm.get(models.Deployment, deployment_id)
        execution = self.sm.put(models.Execution(
            id='execution-1',
            _deployment_fk=deployment._storage_id,
            created_at=datetime.now(),
            is_system_workflow=False,
            workflow_id='install',
            blueprint_id=deployment.blueprint_id
        ))

        for execution_status in [ExecutionState.PENDING,
                                 ExecutionState.CANCELLING,
                                 ExecutionState.FORCE_CANCELLING,
                                 ExecutionState.TERMINATED]:
            execution.status = execution_status
            self.sm.update(execution, modified_attrs=('status',))

            with self.assertRaises(exceptions.CloudifyClientError) as cm:
                self.client.executions.resume(execution.id)
            self.assertEqual(cm.exception.status_code, 409)
            self.assertIn('Cannot resume execution', str(cm.exception))

    @attr(client_min_version=3.1,
          client_max_version=LATEST_API_VERSION)
    def test_force_resume_invalid_state(self):
        """Force-resuming is allowed in the FAILED, CANCELLED  states
        """
        _, deployment_id, _, _ = self.put_deployment(
            self.DEPLOYMENT_ID, 'empty_blueprint.yaml')

        deployment = self.sm.get(models.Deployment, deployment_id)
        execution = self.sm.put(models.Execution(
            id='execution-1',
            _deployment_fk=deployment._storage_id,
            created_at=datetime.now(),
            is_system_workflow=False,
            workflow_id='install',
            blueprint_id=deployment.blueprint_id
        ))

        for execution_status in [ExecutionState.PENDING,
                                 ExecutionState.CANCELLING,
                                 ExecutionState.FORCE_CANCELLING,
                                 ExecutionState.TERMINATED,
                                 ExecutionState.STARTED]:
            execution.status = execution_status
            self.sm.update(execution, modified_attrs=('status',))

            with self.assertRaises(exceptions.CloudifyClientError) as cm:
                self.client.executions.resume(execution.id, force=True)
            self.assertEqual(cm.exception.status_code, 409)
            self.assertIn('Cannot force-resume execution', str(cm.exception))

    @attr(client_min_version=3.1, client_max_version=LATEST_API_VERSION)
    def test_execution_token_invalid(self):
        self._assert_invalid_execution_token()

    @attr(client_min_version=3.1, client_max_version=LATEST_API_VERSION)
    def test_execution_token_valid(self):
        token = uuid.uuid4().hex
        self._create_execution_and_update_token('deployment_1', token)
        self._assert_valid_execution_token(token)

    @attr(client_min_version=3.1, client_max_version=LATEST_API_VERSION)
    def test_execution_token_sequence(self):
        """ Verify the execution token authentication is not affected by
            previous requests
        """
        self._assert_invalid_execution_token()
        token = uuid.uuid4().hex
        self._create_execution_and_update_token('deployment_1', token)
        self._assert_valid_execution_token(token)
        self._assert_invalid_execution_token()

    @attr(client_min_version=3.1, client_max_version=LATEST_API_VERSION)
    def test_execution_token_created_in_db(self):
        _, deployment_id, _, _ = self.put_deployment(self.DEPLOYMENT_ID)
        execution = self.client.executions.start(deployment_id, 'install')
        db_execution = self.sm.get(models.Execution, execution.id)
        self.assertIsNotNone(db_execution.token)
        assert len(db_execution.token) > 10

    @attr(client_min_version=3.1, client_max_version=LATEST_API_VERSION)
    def test_execution_token_invalid_status(self):
        _, deployment_id, _, _ = self.put_deployment(self.DEPLOYMENT_ID)
        execution = self.client.executions.start(deployment_id, 'install')
        token = uuid.uuid4().hex

        # Update the token in the db
        execution = self.sm.get(models.Execution, execution.id)
        execution.token = hashlib.sha256(token.encode('ascii')).hexdigest()
        self.sm.update(execution)

        headers = {CLOUDIFY_EXECUTION_TOKEN_HEADER: token}
        client = self.create_client(headers=headers)

        # Authentication will fail because of the invalid status
        self.assertRaisesRegex(
            exceptions.UserUnauthorizedError,
            'Authentication failed, invalid Execution Token',
            client.executions.list
        )

        # Update the status to an active one
        self._modify_execution_status_in_database(execution,
                                                  ExecutionState.STARTED)

        # Authentication will succeed after updating the status
        executions = client.executions.list()
        assert len(executions) == 3   # bp upload + create dep.env + install

    @attr(client_min_version=3.1, client_max_version=LATEST_API_VERSION)
    def test_duplicate_execution_token(self):
        token = uuid.uuid4().hex
        self._create_execution_and_update_token('deployment_1', token)
        self._assert_valid_execution_token(token)
        self._create_execution_and_update_token('deployment_2', token)
        self._assert_invalid_execution_token(token)

    @attr(client_min_version=3.1, client_max_version=LATEST_API_VERSION)
    def test_delete_executions(self):
        self.put_deployment('dep-1')
        self._create_execution_and_update_token('dep-2', uuid.uuid4().hex)
        self.client.executions.start('dep-1', 'install')
        self.client.executions.start('dep-1', 'uninstall')
        # now we have 5 executions: 2 of them are deployment creations,
        # and one is not terminated -> so only 2 are eligible for deletion
        self.client.executions.delete()
        assert len(self.client.executions.list()) == 3

    @attr(client_min_version=3.1, client_max_version=LATEST_API_VERSION)
    def test_delete_executions_keep_last(self):
        self.put_deployment('dep-1')
        self.client.executions.start('dep-1', 'update')
        self.client.executions.start('dep-1', 'update')
        self.client.executions.start('dep-1', 'update')
        # 4 executions of which 1 is deployment creation, so 3 are deletable
        self.client.executions.delete(keep_last=2)
        assert len(self.client.executions.list()) == 2

    @attr(client_min_version=3.1, client_max_version=LATEST_API_VERSION)
    def test_delete_executions_by_date(self):
        self.put_deployment('dep-1')  # 2 execs: bp upload + dep.env.create
        exec1 = self.client.executions.start('dep-1', 'update')
        exec2 = self.client.executions.start('dep-1', 'update')
        self._update_execution_created_at(exec2, -60)
        self._update_execution_created_at(exec1, -30)
        self.client.executions.delete(
            to_datetime=datetime.strptime('1970-1-1', '%Y-%m-%d'))  # no change
        assert len(self.client.executions.list()) == 4
        a45d_ago = datetime.utcnow() - timedelta(days=45)
        self.client.executions.delete(to_datetime=a45d_ago)   # deletes exec_2
        assert len(self.client.executions.list()) == 3
        self.client.executions.delete(to_datetime=datetime.utcnow())
        assert len(self.client.executions.list()) == 1   # skip ep.env.create

    def _create_execution_and_update_token(self, deployment_id, token):
        self.put_deployment(deployment_id, blueprint_id=deployment_id)
        execution = self.client.executions.start(deployment_id, 'install')

        # Update the token in the db
        execution = self.sm.get(models.Execution, execution.id)
        execution.token = hashlib.sha256(token.encode('ascii')).hexdigest()
        execution.status = ExecutionState.STARTED
        self.sm.update(execution)
        return execution.id

    def _assert_invalid_execution_token(self, token='test_token'):
        headers = {CLOUDIFY_EXECUTION_TOKEN_HEADER: token}
        client = self.create_client(headers=headers)
        self.assertRaisesRegex(
            exceptions.UserUnauthorizedError,
            'Authentication failed, invalid Execution Token',
            client.blueprints.list
        )

    def _assert_valid_execution_token(self, token):
        headers = {CLOUDIFY_EXECUTION_TOKEN_HEADER: token}
        client = self.create_client(headers=headers)
        executions = client.executions.list()
        self.assertEqual(3, len(executions))
        # bp upload + create dep.env + main execution

    def _update_execution_created_at(self, execution, days):
        execution = self.sm.get(models.Execution, execution.id)
        execution.created_at = timedelta(days=days) + \
            datetime.strptime(execution.created_at, '%Y-%m-%dT%H:%M:%S.%fZ')
        self.sm.update(execution)
