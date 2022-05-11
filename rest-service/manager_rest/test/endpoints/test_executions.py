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

import mock
import uuid
import hashlib
import unittest
from itertools import dropwhile
from datetime import datetime, timedelta

from cloudify_rest_client import exceptions
from cloudify.models_states import ExecutionState, VisibilityState
from cloudify.workflows import tasks as cloudify_tasks
from cloudify.constants import CLOUDIFY_EXECUTION_TOKEN_HEADER

from manager_rest.storage import models, db
from manager_rest import manager_exceptions
from manager_rest.test.base_test import BaseServerTestCase


class ExecutionsTestCase(BaseServerTestCase):

    DEPLOYMENT_ID = 'deployment'

    def _test_start_execution_dep_env(self, task_state, expected_ex):
        _, deployment_id, _, _ = self.put_deployment(self.DEPLOYMENT_ID)
        deployment = self.sm.get(models.Deployment, deployment_id)
        create_dep_env = deployment.executions[0]
        self.assertEqual(create_dep_env.workflow_id,
                         'create_deployment_environment')
        create_dep_env.status = task_state
        self.sm.update(create_dep_env)
        with self.assertRaises(expected_ex):
            self.client.executions.start(deployment_id, 'install')

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

    def test_bad_execution_parameters(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(
             self.DEPLOYMENT_ID, 'blueprint_with_workflows.yaml')
        with self.assertRaises(exceptions.CloudifyClientError) as cm:
            self.client.executions.start(deployment_id,
                                         'mock_workflow',
                                         'not_a_dictionary')
        self.assertEqual(
            manager_exceptions.BadParametersError.error_code,
            cm.exception.error_code)

        with self.assertRaises(exceptions.CloudifyClientError) as cm:
            self.client.executions.start(deployment_id,
                                         'mock_workflow',
                                         '[still_not_a_dictionary]')
        self.assertEqual(
            manager_exceptions.BadParametersError.error_code,
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
            manager_exceptions.BadParametersError.error_code)

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

    def test_failed_when_global_disallowed(self):
        """When check_allow_global throws, the execution is failed"""
        self.put_deployment(self.DEPLOYMENT_ID)

        with mock.patch('manager_rest.resource_manager.ResourceManager'
                        '._check_allow_global_execution',
                        side_effect=manager_exceptions.ForbiddenError()):
            with self.assertRaises(exceptions.CloudifyClientError):
                self.client.executions.start(self.DEPLOYMENT_ID, 'install')
        executions = self.client.executions.list(
            deployment_id=self.DEPLOYMENT_ID,
            workflow_id='install')
        self.assertEqual(len(executions), 1)
        execution = executions[0]
        self.assertEqual(ExecutionState.FAILED, execution.status)

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
                    manager_exceptions.IllegalActionError.error_code,
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
            manager_exceptions.NotFoundError.error_code)

    def test_execution_bad_action(self):
        execution = self.test_get_execution_by_id()
        resource_path = '/executions/{0}'.format(execution['id'])
        cancel_response = self.post(resource_path, {
            'action': 'not_really_cancel'
        })
        self.assertEqual(cancel_response.status_code, 400)
        self.assertEqual(
            cancel_response.json['error_code'],
            manager_exceptions.BadParametersError.error_code)

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
            created_at=datetime.utcnow(),
            is_system_workflow=False,
            workflow_id='install',
            status=status,
            blueprint_id=deployment.blueprint_id,
            parameters={},
        ))
        tasks_graph = self.sm.put(models.TasksGraph(
            _execution_fk=execution._storage_id,
            name='install',
            created_at=datetime.utcnow()
        ))
        operation = self.sm.put(models.Operation(
            _tasks_graph_fk=tasks_graph._storage_id,
            parameters={'current_retries': 20},
            state=cloudify_tasks.TASK_FAILED,
            created_at=datetime.utcnow()
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

    def test_resume_force_failed(self):
        """Force-resume resets operation state and restart count"""
        _, deployment_id, _, _ = self.put_deployment(
            self.DEPLOYMENT_ID, 'empty_blueprint.yaml')
        deployment = self.sm.get(models.Deployment, deployment_id)
        self._execution_resume_test(deployment, ExecutionState.FAILED)

    def test_resume_force_cancelled(self):
        """Force-resume resets operation state and restart count"""
        _, deployment_id, _, _ = self.put_deployment(
            self.DEPLOYMENT_ID, 'empty_blueprint.yaml')
        deployment = self.sm.get(models.Deployment, deployment_id)
        self._execution_resume_test(deployment, ExecutionState.CANCELLED)

    def test_resume_invalid_state(self):
        """Resuming is allowed in the STARTED state"""
        _, deployment_id, _, _ = self.put_deployment(
            self.DEPLOYMENT_ID, 'empty_blueprint.yaml')

        deployment = self.sm.get(models.Deployment, deployment_id)
        execution = self.sm.put(models.Execution(
            id='execution-1',
            _deployment_fk=deployment._storage_id,
            created_at=datetime.utcnow(),
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

    def test_force_resume_invalid_state(self):
        """Force-resuming is allowed in the FAILED, CANCELLED  states
        """
        _, deployment_id, _, _ = self.put_deployment(
            self.DEPLOYMENT_ID, 'empty_blueprint.yaml')

        deployment = self.sm.get(models.Deployment, deployment_id)
        execution = self.sm.put(models.Execution(
            id='execution-1',
            _deployment_fk=deployment._storage_id,
            created_at=datetime.utcnow(),
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

    def test_execution_token_invalid(self):
        self._assert_invalid_execution_token()

    def test_execution_token_valid(self):
        token = uuid.uuid4().hex
        self._create_execution_and_update_token('deployment_1', token)
        self._assert_valid_execution_token(token)

    def test_execution_token_sequence(self):
        """ Verify the execution token authentication is not affected by
            previous requests
        """
        self._assert_invalid_execution_token()
        token = uuid.uuid4().hex
        self._create_execution_and_update_token('deployment_1', token)
        self._assert_valid_execution_token(token)
        self._assert_invalid_execution_token()

    def test_execution_token_created_in_db(self):
        _, deployment_id, _, _ = self.put_deployment(self.DEPLOYMENT_ID)
        execution = self.client.executions.start(deployment_id, 'install')
        db_execution = self.sm.get(models.Execution, execution.id)
        self.assertIsNotNone(db_execution.token)
        assert len(db_execution.token) > 10

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

    def test_duplicate_execution_token(self):
        token = uuid.uuid4().hex
        self._create_execution_and_update_token('deployment_1', token)
        self._assert_valid_execution_token(token)
        self._create_execution_and_update_token('deployment_2', token)
        self._assert_invalid_execution_token(token)

    def test_delete_executions(self):
        self.put_deployment('dep-1')
        self._create_execution_and_update_token('dep-2', uuid.uuid4().hex)
        self.client.executions.start('dep-1', 'install')
        self.client.executions.start('dep-1', 'uninstall')
        # now we have 5 executions: 2 of them are deployment creations,
        # and one is not terminated -> so only 2 are eligible for deletion
        self.client.executions.delete()
        assert len(self.client.executions.list()) == 3

    def test_delete_executions_keep_last(self):
        self.put_deployment('dep-1')
        self.client.executions.start('dep-1', 'update')
        self.client.executions.start('dep-1', 'update')
        self.client.executions.start('dep-1', 'update')
        # 4 executions of which 1 is deployment creation, so 3 are deletable
        self.client.executions.delete(keep_last=2)
        assert len(self.client.executions.list()) == 2

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


@mock.patch.object(db, 'session', mock.MagicMock())
class TestExecutionModelValidationTests(unittest.TestCase):
    def test_missing_workflow(self):
        d = models.Deployment(workflows={
            'wf': {}
        })
        with self.assertRaises(manager_exceptions.NonexistentWorkflowError):
            models.Execution(
                parameters={},
                deployment=d,
                workflow_id='nonexistent',
            )

    def test_parameters_type_conversion(self):
        d = models.Deployment(workflows={
            'wf': {
                'parameters': {
                    'bool_param': {'type': 'boolean'},
                    'int_param': {'type': 'integer'},
                    'float_param': {'type': 'float'},
                    'string_param': {'type': 'string'},
                    'untyped_param': {}
                }
            }
        })
        exc = models.Execution(
            parameters={
                'bool_param': 'true',
                'int_param': '5',
                'float_param': '1.5',
                'string_param': 'abc',
                'untyped_param': 'def',
            },
            deployment=d,
            workflow_id='wf',
        )
        assert exc.parameters == {
            'bool_param': True,
            'int_param': 5,
            'float_param': 1.5,
            'string_param': 'abc',
            'untyped_param': 'def'
        }

    def test_parameters_wrong_type(self):
        d = models.Deployment(workflows={
            'wf': {
                'parameters': {
                    'bool_param': {'type': 'boolean', 'default': True},
                    'int_param': {'type': 'integer', 'default': 5},
                    'float_param': {'type': 'float', 'default': 5.0},
                }
            }
        })
        with self.assertRaises(
                manager_exceptions.IllegalExecutionParametersError) as cm:
            models.Execution(
                parameters={
                    'bool_param': 'abc',
                    'int_param': 'abc',
                    'float_param': 'abc',
                },
                deployment=d,
                workflow_id='wf',
            )

        error_message = str(cm.exception)
        assert 'bool_param' in error_message
        assert 'int_param' in error_message
        assert 'float_param' in error_message

    def test_parameters_constraints(self):
        d = models.Deployment(workflows={
            'wf': {
                'parameters': {
                    'foo': {'type': 'string', 'constraints': [
                        {'min_length': 1},
                        {'max_length': 2},
                        {'valid_values': ['Hi', 'Ho']}
                    ]},
                    'bar': {'type': 'string', 'default': 'Q', 'constraints': [
                        {'max_length': 8},
                        {'pattern': r'[A-Z]+'},
                    ]},
                    'baz': {'type': 'integer', 'constraints': [
                        {'greater_than': 100},
                        {'less_than': 1000},
                    ]},
                }
            }
        })
        exc = models.Execution(
            parameters={
                'foo': 'Hi',
                'baz': '500',
            },
            deployment=d,
            workflow_id='wf',
        )
        assert exc.parameters == {
            'foo': 'Hi',
            'bar': 'Q',
            'baz': 500,
        }

    def test_parameters_constraints_violated(self):
        d = models.Deployment(workflows={
            'wf': {
                'parameters': {
                    'foo': {'type': 'string', 'constraints': [
                        {'min_length': 1},
                        {'max_length': 2},
                        {'valid_values': ['Hi', 'Ho']},
                    ]},
                    'bar': {'type': 'string', 'default': 'Q', 'constraints': [
                        {'max_length': 8},
                        {'pattern': r'[A-Z]+'},
                    ]},
                    'baz': {'type': 'integer', 'constraints': [
                        {'greater_than': 100},
                        {'less_than': 1000},
                    ]},
                }
            }
        })
        with self.assertRaises(
                manager_exceptions.IllegalExecutionParametersError) as cm:
            models.Execution(
                parameters={
                    'foo': 'Ab',
                    'bar': 'anything',
                    'baz': 1,
                },
                deployment=d,
                workflow_id='wf',
            )
        error_message = str(cm.exception)
        assert 'foo' in error_message
        assert 'bar' in error_message
        assert 'baz' in error_message

    def test_missing_mandatory_param(self):
        d = models.Deployment(workflows={
            'wf': {
                'parameters': {
                    'mandatory_param': {}
                }
            }
        })
        with self.assertRaisesRegex(
            manager_exceptions.IllegalExecutionParametersError,
            'mandatory_param'
        ):
            models.Execution(
                parameters={},
                deployment=d,
                workflow_id='wf',
            )

    def test_use_default_params(self):
        d = models.Deployment(workflows={
            'wf': {
                'parameters': {
                    'param1': {'default': 'abc'}
                }
            }
        })
        exc = models.Execution(
            parameters={},
            deployment=d,
            workflow_id='wf',
        )
        assert exc.parameters == {'param1': 'abc'}

    def test_override_default_params(self):
        d = models.Deployment(workflows={
            'wf': {
                'parameters': {
                    'param1': {'default': 'abc'},
                    'param2': {'default': {'nested': 'abc'}}
                }
            }
        })
        exc = models.Execution(
            parameters={'param1': 'bcd', 'param2': {'nested': 'bcd'}},
            deployment=d,
            workflow_id='wf',
        )
        assert exc.parameters == {'param1': 'bcd', 'param2': {'nested': 'bcd'}}

    def test_undeclared_parameters(self):
        d = models.Deployment(workflows={
            'wf': {}
        })
        with self.assertRaisesRegex(
            manager_exceptions.IllegalExecutionParametersError,
            'custom parameters',
        ):
            models.Execution(
                parameters={'param1': 'abc'},
                deployment=d,
                workflow_id='wf',
            )

    def test_allow_undeclared_parameters(self):
        d = models.Deployment(workflows={
            'wf': {}
        })
        exc = models.Execution(
            parameters={'param1': 'abc'},
            deployment=d,
            workflow_id='wf',
            allow_custom_parameters=True
        )
        assert exc.parameters == {'param1': 'abc'}

    def test_set_parent(self):
        bp = models.Blueprint(id='abc')
        t = models.Tenant()
        d = models.Deployment(
            blueprint=bp,
            visibility=VisibilityState.TENANT,
            tenant=t,
        )
        exc = models.Execution(deployment=d)
        assert exc.blueprint_id == d.blueprint_id
        assert exc.visibility == d.visibility
        assert exc.tenant == d.tenant

    def test_unavailable_workflow(self):
        d = models.Deployment(workflows={
            'wf': {'availability_rules': {'available': False}},
        })
        with self.assertRaisesRegex(
            manager_exceptions.UnavailableWorkflowError, 'wf'
        ):
            models.Execution(
                parameters={},
                deployment=d,
                workflow_id='wf',
            )


@mock.patch(
    'manager_rest.resource_manager.workflow_executor.workflow_sendhandler',
    mock.Mock()
)
class ExecutionQueueingTests(BaseServerTestCase):
    def setUp(self):
        super().setUp()
        with self.sm.transaction():
            bp = models.Blueprint(id='abc')
            self.sm.put(bp)
            self.deployment1 = models.Deployment(id='dep1',
                                                 display_name='dep1',
                                                 blueprint=bp)
            self.sm.put(self.deployment1)
            self.deployment2 = models.Deployment(id='dep2',
                                                 display_name='dep2',
                                                 blueprint=bp)
            self.sm.put(self.deployment2)
            self.execution1 = models.Execution(
                deployment=self.deployment1,
                workflow_id='install',
                parameters={},
                status=ExecutionState.TERMINATED,
            )
            self.sm.put(self.execution1)
            self.bp = bp

    def _get_queued(self):
        return list(self.rm._get_queued_executions())

    def _make_execution(self, status=None, deployment=None):
        with self.sm.transaction():
            execution = models.Execution(
                deployment=deployment or self.deployment2,
                workflow_id='install',
                parameters={},
                status=status or ExecutionState.QUEUED,
            )
            self.sm.put(execution)
        return execution

    def test_unrelated_execution(self):
        execution2 = self._make_execution()
        assert self._get_queued() == [execution2]

    def test_system_workflow(self):
        self._make_execution()
        system_execution = models.Execution(
            workflow_id='install',
            parameters={},
            status=ExecutionState.QUEUED,
            is_system_workflow=True
        )
        self.sm.put(system_execution)
        assert self._get_queued() == [system_execution]

    def test_one_per_deployment(self):
        self._make_execution(deployment=self.deployment2)
        self._make_execution(deployment=self.deployment2)
        assert len(self._get_queued()) == 1

    def test_full_group(self):
        group = models.ExecutionGroup(workflow_id='install')
        self.sm.put(group)

        # group has concurrency=5, has 4 started, so 1 can run
        for _ in range(4):
            execution = self._make_execution(status=ExecutionState.STARTED)
            group.executions.append(execution)

        queued_execution = self._make_execution(deployment=self.deployment1)
        group.executions.append(queued_execution)

        assert self._get_queued() == [queued_execution]
        # now group has 5 started, so none can run
        execution = self._make_execution(status=ExecutionState.STARTED)
        group.executions.append(execution)
        assert self._get_queued() == []

    def test_two_groups(self):
        group1 = models.ExecutionGroup(id='g1', workflow_id='install')
        self.sm.put(group1)
        group2 = models.ExecutionGroup(id='g2', workflow_id='install')
        self.sm.put(group2)
        for _ in range(5):
            execution = self._make_execution(status=ExecutionState.STARTED)
            group1.executions.append(execution)

        queued_execution = self._make_execution(deployment=self.deployment1)
        group2.executions.append(queued_execution)
        assert self._get_queued() == [queued_execution]

        group1.executions.append(queued_execution)
        # execution won't run because it is in a full group now
        assert self._get_queued() == []

    @mock.patch('manager_rest.workflow_executor.send_hook', mock.Mock())
    def test_already_running_queues(self):
        self._make_execution(status=ExecutionState.STARTED)
        exc2 = self._make_execution(status=ExecutionState.PENDING)
        with self.assertRaises(
                manager_exceptions.ExistingRunningExecutionError):
            self.rm.prepare_executions([exc2])

        self.rm.prepare_executions([exc2], queue=True)
        assert exc2.status == ExecutionState.QUEUED

    @mock.patch('manager_rest.workflow_executor.send_hook', mock.Mock())
    def test_system_wf_already_running_queues(self):
        exc1 = models.Execution(
            status=ExecutionState.STARTED,
            workflow_id='create_snapshot',
            is_system_workflow=True,
        )
        self.sm.put(exc1)
        exc2 = self._make_execution(status=ExecutionState.PENDING)
        with self.assertRaises(
                manager_exceptions.ExistingRunningExecutionError):
            self.rm.prepare_executions([exc2])

        self.rm.prepare_executions([exc2], queue=True)
        assert exc2.status == ExecutionState.QUEUED

    @mock.patch('manager_rest.workflow_executor.send_hook', mock.Mock())
    def test_queue_before_create_finishes(self):
        """Execs queued before create-dep-env finished, have default params.

        Default params are taken from the plan, and that is only available
        when create-dep-env parses the blueprint. It is possible to queue
        executions beforehand, and those executions must re-evaluated
        before actually running.
        """
        dep = models.Deployment(
            id='d1',
            blueprint=self.bp,
            creator=self.user,
            tenant=self.tenant,
        )
        create_dep_env = dep.make_create_environment_execution()
        exc = models.Execution(
            workflow_id='workflow1',
            parameters={
                'param1': 'value1',
            },
            status=ExecutionState.QUEUED,
            deployment=dep,
            creator=self.user,
            tenant=self.tenant,
        )
        dep.workflows = {
            'workflow1': {
                'parameters': {
                    'param1': {'default': 'default1'},
                    'param2': {'default': 'default2'}
                },
            }
        }

        self.rm.update_execution_status(
            create_dep_env.id, ExecutionState.TERMINATED, None)

        assert not exc.error
        assert exc.status == ExecutionState.PENDING
        # now, the execution did get updated with the parameters from the plan,
        # when create-dep-env finished
        assert exc.parameters == {
            'param1': 'value1',
            'param2': 'default2',
        }

    @mock.patch('manager_rest.workflow_executor.send_hook', mock.Mock())
    def test_queue_nonexistent_workflow(self):
        """Dequeueing an execution of a nonexistent workflow, fails."""
        dep = models.Deployment(
            id='d1',
            blueprint=self.bp,
            creator=self.user,
            tenant=self.tenant,
        )
        create_dep_env = dep.make_create_environment_execution()
        exc = models.Execution(
            workflow_id='nonexistent1',
            parameters={
                'param1': 'value1',
            },
            status=ExecutionState.QUEUED,
            deployment=dep,
            creator=self.user,
            tenant=self.tenant,
        )

        self.rm.update_execution_status(
            create_dep_env.id, ExecutionState.TERMINATED, None)

        assert exc.error
        assert 'nonexistent1' in exc.error
        assert exc.status == ExecutionState.FAILED

    def test_install_before_create(self):
        # make a create_dep_env execution, and an install execution; the
        # create_dep_env for the new deployment cannot run, because it's in
        # an exec-group that is already full. The install for the new dep
        # could run, but we check that it MUST NOT run, because create-dep-env
        # hasn't finished yet (or even started)
        create_group = models.ExecutionGroup(
            id='create_group',
            workflow_id='create_deployment_environment',
            concurrency=1,
            creator=self.user,
            tenant=self.tenant,
        )
        old_dep = models.Deployment(
            id='old_dep',
            blueprint=self.bp,
            creator=self.user,
            tenant=self.tenant,
        )
        create_exc = models.Execution(
            id=f'create_{old_dep.id}',
            workflow_id='create_deployment_environment',
            deployment=old_dep,
            status=ExecutionState.STARTED,
            creator=self.user,
            tenant=self.tenant,
        )
        old_dep.create_execution = create_exc
        old_dep.latest_execution = create_exc
        create_group.executions.append(create_exc)

        new_dep = models.Deployment(
            id='new_dep',
            blueprint=self.bp,
            creator=self.user,
            tenant=self.tenant,
        )
        create_exc = models.Execution(
            id=f'create_{new_dep.id}',
            workflow_id='create_deployment_environment',
            deployment=new_dep,
            status=ExecutionState.QUEUED,
            creator=self.user,
            tenant=self.tenant,
        )
        new_dep.create_execution = create_exc
        new_dep.latest_execution = create_exc
        create_group.executions.append(create_exc)
        models.Execution(
            id=f'install_{new_dep.id}',
            workflow_id='install',
            deployment=new_dep,
            status=ExecutionState.QUEUED,
            creator=self.user,
            tenant=self.tenant,
        )

        assert self._get_queued() == []

    def test_checks_other_groups(self):
        models.Execution(
            id='install_nongroup',
            workflow_id='install',
            deployment=self.deployment1,
            status=ExecutionState.PENDING,
            creator=self.user,
            tenant=self.tenant,
        )

        started_groups = [
            models.ExecutionGroup(
                id=f'group_started_{i}',
                workflow_id='install',
                concurrency=1,
                creator=self.user,
                tenant=self.tenant,
            ) for i in range(5)]
        # each of the "started" groups will have one started execution, and
        # 4 queued executions
        exc_states = [ExecutionState.STARTED] + [ExecutionState.QUEUED] * 4
        for group in started_groups:
            for i, exc_state in enumerate(exc_states):
                dep = models.Deployment(
                    id=f'dep_{group.id}_{i}',
                    blueprint=self.bp,
                    creator=self.user,
                    tenant=self.tenant,
                )
                exc = models.Execution(
                    id=f'install_{dep.id}',
                    workflow_id='install',
                    deployment=dep,
                    status=exc_state,
                    creator=self.user,
                    tenant=self.tenant,
                )
                group.executions.append(exc)

        queued_groups = [
            models.ExecutionGroup(
                id=f'group_queued_{i}',
                workflow_id='install',
                concurrency=1,
                creator=self.user,
                tenant=self.tenant,
            ) for i in range(5)]
        # each of the "queued" groups will have five queued executions
        exc_states = [ExecutionState.QUEUED] * 5
        for group in queued_groups:
            for i, exc_state in enumerate(exc_states):
                dep = models.Deployment(
                    id=f'dep_{group.id}_{i}',
                    blueprint=self.bp,
                    creator=self.user,
                    tenant=self.tenant,
                )
                exc = models.Execution(
                    id=f'install_{dep.id}',
                    workflow_id='install',
                    deployment=dep,
                    status=exc_state,
                    creator=self.user,
                    tenant=self.tenant,
                )
                group.executions.append(exc)

        # if we just go ordered by storage_id, then we'll only fetch the queued
        # executions for the groups that are already over concurrency, and
        # we won't be able to start them. We must make sure that the "queued"
        # groups are checked
        dequeued = list(self._get_queued())

        # this will probably be just 1, because we'll only dequeue one queued
        # group up to its concurrency, but it's correct to dequeue more
        assert len(dequeued) > 0

        # hopefully we didn't dequeue anything from the "started" groups!
        for exc in dequeued:
            assert all(gr in queued_groups for gr in exc.execution_groups)
