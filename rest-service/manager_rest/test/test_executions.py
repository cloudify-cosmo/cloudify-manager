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

import mock
from nose.plugins.attrib import attr

from manager_rest.test.base_test import BaseServerTestCase
from manager_rest.test.base_test import test_config
from manager_rest.test.base_test import inject_test_config
from manager_rest.test.base_test import LATEST_API_VERSION
from cloudify_rest_client import exceptions
from manager_rest import manager_exceptions
from manager_rest import models
from manager_rest import storage_manager
from manager_rest.blueprints_manager import (
    TRANSIENT_WORKERS_MODE_ENABLED_DEFAULT as IS_TRANSIENT_WORKERS_MODE,
    LIMITLESS_GLOBAL_PARALLEL_EXECUTIONS_VALUE as LIMITLESS_GLOBAL_EXECUTIONS,
    GLOBAL_PARALLEL_EXECUTIONS_LIMIT_DEFAULT as GLOBAL_EXECS_LIMIT_DEFAULT)


@attr(client_min_version=1, client_max_version=LATEST_API_VERSION)
class ExecutionsTestCase(BaseServerTestCase):

    DEPLOYMENT_ID = 'deployment'

    def test_get_deployment_executions_empty(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        executions = self.client.executions.list(deployment_id=deployment_id)

        # expecting 1 execution (create_deployment_environment)
        self.assertEquals(1, len(executions))
        self.assertEquals('create_deployment_environment',
                          executions[0]['workflow_id'])

    def test_get_execution_by_id(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        execution = self.client.executions.start(deployment_id, 'install')
        get_execution = self.client.executions.get(execution.id)
        self.assertEquals(get_execution.status, 'terminated')
        self.assertEquals(get_execution['blueprint_id'], blueprint_id)
        self.assertEquals(get_execution['deployment_id'],
                          deployment_response['id'])
        self.assertIsNotNone(get_execution['created_at'])

        return execution

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
            created_at=str(datetime.now()),
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

    def test_bad_update_execution_status(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

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

    def test_update_execution_status(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        execution = self.client.executions.start(deployment_id, 'install')
        execution = self.client.executions.get(execution.id)
        self.assertEquals('terminated', execution.status)
        self._modify_execution_status(execution.id, 'new_status')

    def test_update_execution_status_with_error(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        execution = self.client.executions.start(deployment_id, 'install')
        execution = self.client.executions.get(execution.id)
        self.assertEquals('terminated', execution.status)
        self.assertEquals('', execution.error)
        execution = self.client.executions.update(execution.id,
                                                  'new-status',
                                                  'some error')
        self.assertEquals('new-status', execution.status)
        self.assertEquals('some error', execution.error)
        # verifying that updating only the status field also resets the
        # error field to an empty string
        execution = self._modify_execution_status(execution.id,
                                                  'final-status')
        self.assertEquals('', execution.error)

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
        expected_status_code = 400 if IS_TRANSIENT_WORKERS_MODE else 201
        self._test_execute_more_than_one_workflow(True, expected_status_code)

    def _test_execute_more_than_one_workflow(self, is_use_force,
                                             expected_status_code):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        execution = self.client.executions.start(deployment_id, 'install')
        self._modify_execution_status(execution.id, 'pending')

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


class TransientDeploymentWorkersExecutionsTestCase(BaseServerTestCase):

    DEPLOYMENT_ID = 'deployment'

    @inject_test_config
    def initialize_provider_context(self, test_config):
        provider_context = {
            'cloudify': {
                'transient_deployment_workers_mode': test_config
            }
        }
        self.client.manager.create_context(self.id(), provider_context)

    @test_config(enabled=True,
                 global_parallel_executions_limit=LIMITLESS_GLOBAL_EXECUTIONS)
    def test_transient_dep_workers_force_execute(self):
        # verifies force-executing a workflow is disabled in transient
        # deployment workers mode - regardless of whether other workflows
        # are currently executing or not
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        try:
            self.client.executions.start(deployment_id, 'install', force=True)
            self.fail('Expected force-executing a workflow to be disabled'
                      'in transient deployment workers mode')
        except exceptions.CloudifyClientError, e:
            self.assertEqual(400, e.status_code)
            expected_error_code = \
                manager_exceptions.ExistingRunningExecutionError.\
                EXISTING_RUNNING_EXECUTION_ERROR_CODE
            self.assertEqual(expected_error_code, e.error_code)

    @test_config()
    def test_transient_dep_workers_default_config(self):
        # verifies default values in the REST service for the transient
        # deployment workers mode configuration

        expected_default_config = {
            'enabled': True,
            'global_parallel_executions_limit': GLOBAL_EXECS_LIMIT_DEFAULT
        }

        with mock.patch('manager_rest.blueprints_manager.BlueprintsManager.'
                        '_check_for_active_executions') as m:
            (blueprint_id, deployment_id, blueprint_response,
             deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

            self.client.executions.start(deployment_id, 'install')

            m.assert_called_once_with(deployment_id, False,
                                      expected_default_config)

    @test_config(enabled=True,
                 global_parallel_executions_limit=2)
    def test_transient_dep_workers_global_executions_limit(self):
        # verifies global executions limit takes effect when transient
        # deployment workers mode is enabled
        self._run_parallel_executions_and_verify_result(expect_failure=True)

    @test_config(enabled=False,
                 global_parallel_executions_limit=1)
    def test_transient_dep_workers_disabled_global_executions_limit(self):
        # verifies global executions limit has no effect when transient
        # deployment workers mode is disabled
        self._run_parallel_executions_and_verify_result(expect_failure=False)

    @test_config(enabled=True,
                 global_parallel_executions_limit=LIMITLESS_GLOBAL_EXECUTIONS)
    def test_transient_dep_workers_limitless_global_executions(self):
        # verifies the value for limitless global executions is used correctly
        self._run_parallel_executions_and_verify_result(expect_failure=False)

    @attr(client_min_version=2,
          client_max_version=LATEST_API_VERSION)
    @test_config(enabled=True,
                 global_parallel_executions_limit=50)
    def test_transient_dep_workers_global_executions_updated_limit(self):
        # verifies global executions limit updates take effect

        # run parallel executions pre-modification - not expecting failures
        self._run_parallel_executions_and_verify_result(expect_failure=False)
        # resetting all active executions to 'terminated' status
        executions = self.client.executions.list()
        map(lambda execution: self.client.executions.update(
            execution.id, 'terminated'), executions)

        # modifying the global parallel executions limit and trying again
        self.client.manager.set_global_parallel_executions_limit(2)
        self._run_parallel_executions_and_verify_result(
            expect_failure=True, blueprint_id='blueprint2',
            deployment_id_prefix='deployment2')

    def _run_parallel_executions_and_verify_result(
            self, expect_failure, blueprint_id='blueprint',
            deployment_id_prefix=DEPLOYMENT_ID):
        # runs three executions on three different deployments
        # and verifies success/failure accordingly
        deployment1 = deployment_id_prefix + '1'
        deployment2 = deployment_id_prefix + '2'
        deployment3 = deployment_id_prefix + '3'

        (blueprint_id, deployment_id, _, _) = \
            self.put_deployment(deployment1, blueprint_id=blueprint_id)
        self.client.deployments.create(blueprint_id, deployment2)
        self.client.deployments.create(blueprint_id, deployment3)

        execution1 = self.client.executions.start(deployment1, 'install')
        self.client.executions.update(execution1.id, 'started')
        execution2 = self.client.executions.start(deployment2, 'install')
        self.client.executions.update(execution2.id, 'started')

        if expect_failure:
            try:
                self.client.executions.start(deployment3, 'install')
                self.fail('Expected global parallel running executions limit '
                          'to have been reached')
            except exceptions.CloudifyClientError, e:
                self.assertEqual(400, e.status_code)
                expected_error_code = \
                    manager_exceptions. \
                    GlobalParallelRunningExecutionsLimitReachedError. \
                    GLOBAL_PARALLEL_RUNNING_EXECUTIONS_LIMIT_REACHED_ERROR_CODE
                self.assertEqual(expected_error_code, e.error_code)
        else:
            execution3 = self.client.executions.start(deployment3, 'install')
            executions = self.client.executions.list()
            executions = sorted(executions, key=lambda e: e.created_at)
            # expecting 6 executions - first three are deployment env creation
            self.assertEquals(6, len(executions))
            self.assertEquals(execution1.id,
                              executions[3]['id'])
            self.assertEquals(execution2.id,
                              executions[4]['id'])
            self.assertEquals(execution3.id,
                              executions[5]['id'])
