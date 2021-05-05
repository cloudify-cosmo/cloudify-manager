########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import time
import uuid
import pytest

from retrying import retry
from sh import ErrorReturnCode

from integration_tests import AgentlessTestCase
from integration_tests.framework import utils
from integration_tests.tests.utils import (
    verify_deployment_env_created,
    do_retries,
    get_resource as resource,
    upload_mock_plugin,
    generate_scheduled_for_date,
    create_api_token,
    create_tenants_and_add_users)
from integration_tests.tests.utils import (run_postgresql_command,
                                           wait_for_blueprint_upload)

from cloudify.models_states import ExecutionState as Execution
from cloudify_rest_client.exceptions import CloudifyClientError


@pytest.mark.usefixtures('cloudmock_plugin')
@pytest.mark.usefixtures('mock_workflows_plugin')
@pytest.mark.usefixtures('testmockoperations_plugin')
class ExecutionsTest(AgentlessTestCase):

    def _wait_for_exec_to_end_and_modify_status(self, execution, new_status):
        self.wait_for_execution_to_end(execution)
        self.manually_update_execution_status(new_status, execution.id)
        self._assert_execution_status(execution.id, new_status)

        return execution

    def _create_snapshot_and_modify_execution_status(self, new_status):
        snapshot = self.client.snapshots.create('snapshot_1',
                                                include_credentials=True,
                                                include_logs=True,
                                                include_events=True,
                                                include_metrics=True,
                                                queue=True)
        execution = self._wait_for_exec_to_end_and_modify_status(snapshot,
                                                                 new_status)
        return execution

    def _update_to_terminated_and_assert_propper_dequeue(self, id1, id2):

        """
        This method modifies the status of the first execution (id1) to
        `terminated` in order to start the de-queue mechanism, and
        then assert that the second execution (that was queued) started.

        """

        self.client.executions.update(id1, Execution.TERMINATED)

        queued_execution = self.client.executions.get(id2)
        self.wait_for_execution_to_end(queued_execution)

        self._assert_execution_status(id1, Execution.TERMINATED)
        self._assert_execution_status(id2, Execution.TERMINATED)

    def _get_executions_list(self):
        return self.client.executions.list(deployment_id=None,
                                           include_system_workflows=True,
                                           sort='created_at',
                                           is_descending=False,
                                           _all_tenants=True,
                                           _offset=0,
                                           _size=1000).items

    @retry(wait_fixed=300, stop_max_attempt_number=10)
    def _assert_execution_status(self, execution_id,
                                 wanted_status, client=None):
        client = client or self.client
        current_status = client.executions.get(execution_id).status
        self.assertEqual(current_status, wanted_status)

    def test_queue_execution_while_system_execution_is_running(self):

        dsl_path = resource("dsl/basic.yaml")
        deployment = self.deploy(dsl_path)

        # Create snapshot and make sure it's state remains 'started'
        # so that new executions will be queued
        snapshot = self._create_snapshot_and_modify_execution_status(
            Execution.STARTED)

        # Create an 'install' execution and make sure it's being queued
        execution = self.execute_workflow(workflow_name='install',
                                          deployment_id=deployment.id,
                                          wait_for_execution=False,
                                          queue=True)
        execution_id = execution.id
        self._assert_execution_status(execution_id, Execution.QUEUED)

        # Update snapshot state to 'terminated' so the queued 'install'
        #  execution will start
        self._update_to_terminated_and_assert_propper_dequeue(
            snapshot.id, execution_id)

    def test_queue_system_execution_while_system_execution_is_running(self):

        # Create snapshot and make sure it's state remains 'started'
        # so that new executions will be queued
        snapshot = self._create_snapshot_and_modify_execution_status(
            Execution.STARTED)

        # Create another system execution and make sure it's being  queued
        second_snap = self.client.snapshots.create('snapshot_2',
                                                   include_credentials=True,
                                                   include_logs=True,
                                                   include_events=True,
                                                   include_metrics=True,
                                                   queue=True)
        self._assert_execution_status(second_snap.id, Execution.QUEUED)

        # Update first snapshot state to 'terminated', so the second snapshot
        #  will start.
        self._update_to_terminated_and_assert_propper_dequeue(
            snapshot.id, second_snap.id)

    def test_queue_execution_while_system_execution_is_queued(self):

        # Create deployment
        dsl_path = resource("dsl/basic.yaml")
        deployment = self.deploy(dsl_path)

        # Create snapshot and make sure it's state remains 'queud'
        # so that new executions will be queued
        snapshot = self._create_snapshot_and_modify_execution_status(
            Execution.QUEUED)

        # Create an 'install' execution
        execution = self.execute_workflow(workflow_name='install',
                                          deployment_id=deployment.id,
                                          wait_for_execution=False,
                                          queue=True)
        self._assert_execution_status(execution.id, Execution.QUEUED)

        # Update snapshot state to 'terminated' so the queued 'install'
        #  execution will start
        self._update_to_terminated_and_assert_propper_dequeue(
            snapshot.id, execution.id)

    def test_queue_system_execution_while_execution_is_running(self):

        # Create deployment and start 'install' execution
        dsl_path = resource("dsl/basic.yaml")
        deployment = self.deploy(dsl_path)
        execution = self.execute_workflow(workflow_name='install',
                                          deployment_id=deployment.id,
                                          wait_for_execution=False,
                                          queue=True)
        # Make sure the install execution stays 'started'
        execution = self._wait_for_exec_to_end_and_modify_status(
            execution, Execution.STARTED)

        # Create a system execution and make sure it's being queued
        second_snap = self.client.snapshots.create('snapshot_2',
                                                   include_credentials=True,
                                                   include_logs=True,
                                                   include_events=True,
                                                   include_metrics=True,
                                                   queue=True)
        self._assert_execution_status(second_snap.id, Execution.QUEUED)

        # Update first snapshot state to 'terminated', so the second snapshot
        #  will start.
        self._update_to_terminated_and_assert_propper_dequeue(
            execution.id, second_snap.id)

    def test_queue_execution_while_execution_is_running_under_same_dep(self):

        # Create deployment
        dsl_path = resource("dsl/basic.yaml")
        deployment = self.deploy(dsl_path)

        # Start 'install' execution and
        execution_1 = self.execute_workflow(workflow_name='install',
                                            deployment_id=deployment.id,
                                            wait_for_execution=False,
                                            queue=True)

        # Make sure the install execution stays 'started'
        execution_1 = self._wait_for_exec_to_end_and_modify_status(
            execution_1, Execution.STARTED)

        # Start a second 'install' under the same deployment and assert it's
        # being queued
        execution_2 = self.execute_workflow(workflow_name='uninstall',
                                            deployment_id=deployment.id,
                                            wait_for_execution=False,
                                            queue=True)
        self._assert_execution_status(execution_2.id, Execution.QUEUED)

        # Update first snapshot state to 'terminated', so the second snapshot
        #  will start.
        self._update_to_terminated_and_assert_propper_dequeue(
            execution_1.id, execution_2.id)

    def test_start_exec_while_other_exec_is_running_under_different_dep(self):

        # Create deployments
        dsl_path = resource("dsl/basic.yaml")
        deployment_1 = self.deploy(dsl_path)
        deployment_2 = self.deploy(dsl_path)

        # Start 'install' execution and make sure it's status stays 'started'
        execution_1 = self.execute_workflow(workflow_name='install',
                                            deployment_id=deployment_1.id,
                                            wait_for_execution=False,
                                            queue=True)
        self._wait_for_exec_to_end_and_modify_status(
            execution_1, Execution.STARTED)

        # Start a second 'install' under different deployment
        execution_2 = self.execute_workflow(workflow_name='install',
                                            deployment_id=deployment_2.id,
                                            wait_for_execution=False,
                                            queue=True)

        # Make sure the second 'install' ran in parallel
        self.wait_for_execution_to_end(execution_2)
        self._assert_execution_status(execution_2.id, Execution.TERMINATED)

    def test_queue_exec_from_queue_while_system_execution_is_running(self):
        """
        - System execution (snapshot) is running
        - Queue contains: another snapshot and a regular execution.
        Once the first snapshot finishes we expect the second one to run and
        the execution to be queued again.

        """
        # Create deployment
        dsl_path = resource('dsl/sleep_workflows.yaml')
        deployment = self.deploy(dsl_path)

        # Create snapshot and make sure it's state remains 'started'
        # so that new executions will be queued
        snapshot = self._create_snapshot_and_modify_execution_status(
            Execution.STARTED)

        # Create another system execution
        snapshot_2 = self.client.snapshots.create('snapshot_2',
                                                  include_credentials=True,
                                                  include_logs=True,
                                                  include_events=True,
                                                  include_metrics=True,
                                                  queue=True)

        # Start 'install' execution
        execution = self.execute_workflow(workflow_name='sleep',
                                          deployment_id=deployment.id,
                                          wait_for_execution=False,
                                          queue=True)

        # Make sure snapshot_2 and execution are queued (since there's a
        # running system execution)
        self._assert_execution_status(snapshot_2.id, Execution.QUEUED)
        self._assert_execution_status(execution.id, Execution.QUEUED)

        # Update first snapshot status to terminated
        self.client.executions.update(snapshot.id, Execution.TERMINATED)

        # Make sure snapshot_2 started (or pending) while the execution
        # is queued again
        current_status = self.client.executions.get(snapshot_2.id).status
        self.assertIn(current_status, [Execution.PENDING, Execution.STARTED])
        self._assert_execution_status(execution.id, Execution.QUEUED)

    def test_queue_exec_from_queue_while_exec_in_same_dep_is_running(self):
        """
        - System execution (snapshot) is running
        - Queue contains: 2 regular executions under the same deployment.
        Once the snapshot finishes we expect only the first execution in
        the queue to start running, and the second execution to be queued
        again.

        """
        # Create deployment
        dsl_path = resource('dsl/sleep_workflows.yaml')
        deployment = self.deploy(dsl_path)

        # Create snapshot and make sure it's state remains 'started'
        # so that new executions will be queued
        snapshot = self._create_snapshot_and_modify_execution_status(
            Execution.STARTED)

        # create 2 executions under the same deployment
        execution_1 = self.execute_workflow(workflow_name='install',
                                            deployment_id=deployment.id,
                                            wait_for_execution=False,
                                            queue=True)

        execution_2 = self.execute_workflow(workflow_name='uninstall',
                                            deployment_id=deployment.id,
                                            wait_for_execution=False,
                                            queue=True)

        # Make sure the 2 executions are queued (since there's a
        # running system execution)
        self._assert_execution_status(execution_1.id, Execution.QUEUED)
        self._assert_execution_status(execution_2.id, Execution.QUEUED)

        # Update snapshot status to terminated
        self.client.executions.update(snapshot.id, Execution.TERMINATED)

        # Make sure exeuction_1 status is started (or pending) and that
        #  execution_2 is still queued
        current_status = self.client.executions.get(execution_1.id).status
        self.assertIn(current_status, [Execution.PENDING, Execution.STARTED])
        self._assert_execution_status(execution_2.id, Execution.QUEUED)

    def test_run_exec_from_queue_while_exec_in_diff_dep_is_running(self):
        """
        - System execution (snapshot) is running
        - Queue contains: 2 regular executions under different deployments.
        Once the snapshot finishes we expect both execution to run in parallel

        """
        # Create deployment
        dsl_path = resource('dsl/sleep_workflows.yaml')
        deployment_1 = self.deploy(dsl_path)
        deployment_2 = self.deploy(dsl_path)

        # Create snapshot and make sure it's state remains 'started'
        # so that new executions will be queued
        snapshot = self._create_snapshot_and_modify_execution_status(
            Execution.STARTED)

        # create 2 executions under the same deployment
        execution_1 = self.execute_workflow(workflow_name='install',
                                            deployment_id=deployment_1.id,
                                            wait_for_execution=False,
                                            queue=True)

        execution_2 = self.execute_workflow(workflow_name='install',
                                            deployment_id=deployment_2.id,
                                            wait_for_execution=False,
                                            queue=True)

        # Make sure the 2 executions are queued (since there's a
        # running system execution)
        self._assert_execution_status(execution_1.id, Execution.QUEUED)
        self._assert_execution_status(execution_2.id, Execution.QUEUED)

        # Update snapshot status to terminated
        self.client.executions.update(snapshot.id, Execution.TERMINATED)

        # Make sure both executions' status is started (or pending)
        self.wait_for_execution_to_end(execution_1)
        self.wait_for_execution_to_end(execution_2)

    def test_queue_system_exec_from_queue_while_system_exec_is_running(self):
        """
        - System execution (snapshot) is running
        - Queue contains: two more snapshots. (3 snapshots in total)
        Once the first snapshot finishes we expect the second one to run and
        the third one to be queued again.

        """

        # Create snapshot and make sure it's state remains 'started'
        # so that new executions will be queued
        snapshot = self._create_snapshot_and_modify_execution_status(
            Execution.STARTED)

        # Create another system execution
        snapshot_2 = self.client.snapshots.create('snapshot_2',
                                                  include_credentials=True,
                                                  include_logs=True,
                                                  include_events=True,
                                                  include_metrics=True,
                                                  queue=True)
        snapshot_3 = self.client.snapshots.create('snapshot_3',
                                                  include_credentials=True,
                                                  include_logs=True,
                                                  include_events=True,
                                                  include_metrics=True,
                                                  queue=True)

        # Make sure the 2 snapshots are queued (since there's a
        # running system execution)
        self._assert_execution_status(snapshot_2.id, Execution.QUEUED)
        self._assert_execution_status(snapshot_3.id, Execution.QUEUED)

        # Update first snapshot status to terminated
        self.client.executions.update(snapshot.id, Execution.TERMINATED)

        # Make sure snapshot_2 started while the snapshot_3 is queued again
        self._assert_execution_status(snapshot_3.id, Execution.QUEUED)
        self.wait_for_execution_to_end(snapshot_2)

    def test_queue_system_exec_from_queue_while_exec_is_running(self):
        """
        - System execution (snapshot) is running
        - Queue contains: a regular execution ('install') and a system
          execution (snapshot).
        Once the first snapshot finishes we expect the snapshot to run
        and the regular execution to be queued again.

        """
        # Create deployment
        dsl_path = resource('dsl/sleep_workflows.yaml')
        deployment_1 = self.deploy(dsl_path)

        # Create snapshot and make sure it's state remains 'started'
        # so that new executions will be queued
        snapshot_1 = self._create_snapshot_and_modify_execution_status(
            Execution.STARTED)

        # create a regular execution and a system execution
        execution = self.execute_workflow(workflow_name='install',
                                          deployment_id=deployment_1.id,
                                          wait_for_execution=False,
                                          queue=True)

        snapshot_2 = self.client.snapshots.create('snapshot_2',
                                                  include_credentials=True,
                                                  include_logs=True,
                                                  include_events=True,
                                                  include_metrics=True,
                                                  queue=True)

        # Make sure snapshot_2 and execution are queued (since there's a
        # running system execution)
        self._assert_execution_status(execution.id, Execution.QUEUED)
        self._assert_execution_status(snapshot_2.id, Execution.QUEUED)

        # Update first snapshot status to terminated
        self.client.executions.update(snapshot_1.id, Execution.TERMINATED)

        # Make sure snapshot_2 started while the install is queued again
        current_status = self.client.executions.get(snapshot_2.id).status
        self.assertIn(current_status, [Execution.PENDING, Execution.STARTED])
        self._assert_execution_status(execution.id, Execution.QUEUED)
        self.wait_for_execution_to_end(snapshot_2)

    def test_fail_to_delete_deployment_of_queued_execution(self):
        """
        Make sure users can't delete deployment of a queued exeuction
        """

        # Create deployment
        dsl_path = resource('dsl/sleep_workflows.yaml')
        deployment_1 = self.deploy(dsl_path)
        execution = self.execute_workflow(workflow_name='install',
                                          deployment_id=deployment_1.id,
                                          wait_for_execution=False,
                                          queue=True)
        self._wait_for_exec_to_end_and_modify_status(execution,
                                                     Execution.QUEUED)
        try:
            self.client.deployments.delete(deployment_1.id)
        except CloudifyClientError as e:
            self.assertIn('There are running or queued', str(e))
            self.assertEqual(e.status_code, 400)
            self.assertEqual(e.error_code, 'dependent_exists_error')

    def test_cancel_queued_execution(self):
        # Create snapshot and make sure it's state remains 'queued'
        snapshot = self._create_snapshot_and_modify_execution_status(
            Execution.QUEUED)
        self.client.executions.cancel(snapshot.id)
        time.sleep(3)
        self._assert_execution_status(snapshot.id, Execution.CANCELLED)

    def _execute_unpermitted_operation_and_catch_exception(self, op, args):
        with self.assertRaisesRegex(
                CloudifyClientError, '[Cc]annot start') as cm:
            op(args)
        self.assertEqual(cm.exception.status_code, 400)

    def test_fail_to_create_deployment_while_creating_snapshot(self):
        # Create snapshot and make sure it's state remains 'started'
        self._create_snapshot_and_modify_execution_status(Execution.STARTED)

        dsl_path = resource('dsl/sleep_workflows.yaml')
        self._execute_unpermitted_operation_and_catch_exception(
            self.deploy, dsl_path
        )

    def test_fail_to_delete_deployment_while_creating_snapshot(self):
        # Create deployment
        dsl_path = resource('dsl/sleep_workflows.yaml')
        deployment = self.deploy(dsl_path)

        # Create snapshot and make sure it's state remains 'started'
        self._create_snapshot_and_modify_execution_status(Execution.STARTED)
        self._execute_unpermitted_operation_and_catch_exception(
            self.client.deployments.delete, deployment.id
        )

    def test_fail_to_upload_plugin_while_creating_snapshot(self):
        # Create snapshot and make sure it's state remains 'started'
        self._create_snapshot_and_modify_execution_status(Execution.STARTED)
        with self.assertRaisesRegex(
                CloudifyClientError, '[Cc]annot start') as cm:
            upload_mock_plugin(self.client, 'cloudify-script-plugin', '1.2')
        self.assertEqual(cm.exception.status_code, 400)

    def test_fail_to_delete_plugin_while_creating_snapshot(self):
        # Upload plugin
        plugin = upload_mock_plugin(
            self.client, 'cloudify-script-plugin', '1.2')
        plugins_list = self.client.plugins.list()
        # 3 plugins were uploaded with the test class
        self.assertEqual(4, len(plugins_list),
                         'expecting 4 plugin results, '
                         'got {0}'.format(len(plugins_list)))

        # Create snapshot and make sure it's state remains 'started'
        self._create_snapshot_and_modify_execution_status(Execution.STARTED)
        self._execute_unpermitted_operation_and_catch_exception(
            self.client.plugins.delete, plugin.id)

    def test_cancel_execution(self):
        execution, deployment_id = self._execute_and_cancel_execution(
            'sleep_with_cancel_support')
        self._assert_execution_cancelled(execution, deployment_id)

    def test_force_cancel_execution(self):
        execution, deployment_id = self._execute_and_cancel_execution(
            'sleep', True)
        self._assert_execution_cancelled(execution, deployment_id)

    def test_cancel_execution_with_graph_workflow(self):
        execution, deployment_id = self._execute_and_cancel_execution(
            'sleep_with_graph_usage')
        self._assert_execution_cancelled(execution, deployment_id)

    def test_cancel_execution_and_then_force_cancel(self):
        execution, deployment_id = self._execute_and_cancel_execution(
            'sleep', False, False)

        # cancel didn't work (unsupported) - use force-cancel instead
        execution = self.client.executions.cancel(execution.id, True)
        self.assertEqual(Execution.FORCE_CANCELLING, execution.status)
        self.wait_for_execution_to_end(execution)
        execution = self.client.executions.get(execution.id)

        self._assert_execution_cancelled(execution, deployment_id)

    def test_execute_and_kill_execution(self):
        """
        Tests the kill execution option by asserting the execution pid doesn't
        exist.
        """
        dsl_path = resource('dsl/write_pid_node.yaml')
        dep = self.deploy(dsl_path, wait=False, client=self.client)
        do_retries(verify_deployment_env_created, 30,
                   container_id=self.env.container_id,
                   deployment_id=dep.id,
                   client=self.client)
        execution = self.client.executions.start(deployment_id=dep.id,
                                                 workflow_id='install')
        pid = do_retries(self.read_manager_file,
                         timeout_seconds=60,
                         file_path='/tmp/pid.txt')
        path = '/proc/{}/status'.format(pid)
        execution = self.client.executions.cancel(execution.id,
                                                  force=True, kill=True)
        self.assertEqual(Execution.KILL_CANCELLING, execution.status)

        # If the process is still running docl.read_file will raise an error.
        # We use do_retries to give the kill cancel operation time to kill
        # the process.
        do_retries(self.assertRaises, expected_exception=ErrorReturnCode,
                   callableObj=self.read_manager_file,
                   file_path=path)

    def test_legacy_cancel_execution(self):
        # this tests cancellation of an execution where the workflow
        # announces the cancel occurred by returning a value rather than by
        # raising an error
        execution, deployment_id = self._execute_and_cancel_execution(
            'sleep_with_cancel_support',
            workflow_params={'use_legacy_cancel': True})
        self._assert_execution_cancelled(execution, deployment_id)

    def test_cancel_execution_before_it_started(self):
        execution, deployment_id = self._execute_and_cancel_execution(
            'sleep_with_cancel_support', False, True, False)
        self.assertEqual(Execution.CANCELLED, execution.status)
        data = self.get_runtime_property(deployment_id,
                                         'mock_operation_invocation')
        self.assertEqual(data, [])

    def test_sort_executions(self):
        dsl_path = resource("dsl/basic.yaml")
        deployment, execution_id = self.deploy_application(dsl_path)
        self.wait_for_execution_to_end(
            self.client.executions.get(execution_id))
        deployment, execution_id = self.deploy_application(dsl_path)
        self.wait_for_execution_to_end(
            self.client.executions.get(execution_id))
        deployments_executions = self.client.executions.list(sort='created_at')
        for i in range(len(deployments_executions) - 1):
            self.assertTrue(deployments_executions[i]['created_at'] <
                            deployments_executions[i + 1]['created_at'],
                            'execution list not sorted correctly')
        deployments_executions = self.client.executions.list(
            sort='created_at',
            is_descending=True)
        for i in range(len(deployments_executions) - 1):
            self.assertTrue(deployments_executions[i]['created_at'] >
                            deployments_executions[i + 1]['created_at'],
                            'execution list not sorted correctly')

    def test_get_deployments_executions_with_status(self):
        dsl_path = resource("dsl/basic.yaml")
        deployment, execution_id = self.deploy_application(dsl_path)

        def assertions():
            deployments_executions = self.client.executions.list(
                deployment_id=deployment.id)
            # expecting 2 executions (1 for deployment environment
            # creation and 1 execution of 'install'). Checking the install
            # execution's status
            self.assertEqual(2, len(deployments_executions))
            self.assertIn(execution_id, [deployments_executions[0].id,
                                         deployments_executions[1].id])
            install_execution = deployments_executions[0]\
                if (execution_id == deployments_executions[0].id) \
                else deployments_executions[1]
            self.assertEqual(Execution.TERMINATED, install_execution.status)
            self.assertIsNotNone(install_execution.created_at)
            self.assertIsNotNone(install_execution.ended_at)
            self.assertEqual('', install_execution.error)

        self.do_assertions(assertions, timeout=10)

    def test_execution_parameters(self):
        dsl_path = resource('dsl/workflow_parameters.yaml')
        _id = uuid.uuid1()
        blueprint_id = 'blueprint_{0}'.format(_id)
        deployment_id = 'deployment_{0}'.format(_id)
        self.client.blueprints.upload(dsl_path, blueprint_id)
        wait_for_blueprint_upload(blueprint_id, self.client, True)
        self.client.deployments.create(blueprint_id, deployment_id,
                                       skip_plugins_validation=True)

        do_retries(verify_deployment_env_created, 60,
                   container_id=self.env.container_id,
                   deployment_id=deployment_id,
                   client=self.client)
        execution_parameters = {
            'operation': 'test_interface.operation',
            'properties': {
                'key': 'different-key',
                'value': 'different-value'
            },
            'custom-parameter': "doesn't matter"
        }

        execution = self.client.executions.start(
            deployment_id, 'another_execute_operation',
            parameters=execution_parameters,
            allow_custom_parameters=True)
        self.wait_for_execution_to_end(execution)
        invocations = self.get_runtime_property(deployment_id,
                                                'mock_operation_invocation')[0]
        self.assertEqual(1, len(invocations))
        self.assertDictEqual(invocations[0],
                             {'different-key': 'different-value'})

        # checking for execution parameters - expecting there to be a merge
        # with overrides with workflow parameters.
        expected_params = {
            'node_id': 'test_node',
            'operation': 'test_interface.operation',
            'properties': {
                'key': 'different-key',
                'value': 'different-value'
            },
            'custom-parameter': "doesn't matter"
        }
        self.assertEqual(expected_params, execution.parameters)

    def test_update_execution_status(self):
        dsl_path = resource("dsl/basic.yaml")
        _, execution_id = self.deploy_application(dsl_path,
                                                  wait_for_execution=True)
        execution = self.client.executions.get(execution_id)
        self.assertEqual(Execution.TERMINATED, execution.status)

        # Manually updating the status, because the client checks for
        # correct transitions
        run_postgresql_command(
            self.env.container_id,
            "UPDATE executions SET status='started' "
            "WHERE id='{0}'".format(execution_id)
        )
        execution = self.client.executions.get(execution_id)
        self.assertEqual(Execution.STARTED, execution.status)
        execution = self.client.executions.update(execution_id,
                                                  'pending',
                                                  'some-error')
        self.assertEqual(Execution.PENDING, execution.status)
        self.assertEqual('some-error', execution.error)
        # verifying that updating only the status field also resets the
        # error field to an empty string
        execution = self.client.executions.update(execution_id,
                                                  Execution.TERMINATED)
        self.assertEqual(Execution.TERMINATED, execution.status)
        self.assertEqual('', execution.error)

    def _check_node_instance_state(self, expected_state, node_inst_id):
        for _ in range(30):
            instance_state = self.client.node_instances.get(node_inst_id).state
            if instance_state == expected_state:
                break
            time.sleep(1)
        else:
            raise RuntimeError('Expected instance state is: {}, '
                               'but the actual state is: {}'
                               .format(expected_state, instance_state))

    def _execute_from_resource(self, workflow_id, workflow_params=None,
                               resource_file=None):
        dsl_path = resource(resource_file)
        _id = uuid.uuid1()
        blueprint_id = 'blueprint_{0}'.format(_id)
        deployment_id = 'deployment_{0}'.format(_id)
        self.client.blueprints.upload(dsl_path, blueprint_id)
        wait_for_blueprint_upload(blueprint_id, self.client, True)
        self.client.deployments.create(blueprint_id, deployment_id,
                                       skip_plugins_validation=True)
        do_retries(verify_deployment_env_created, 30,
                   container_id=self.env.container_id,
                   deployment_id=deployment_id,
                   client=self.client)
        execution = self.client.executions.start(
            deployment_id, workflow_id, parameters=workflow_params)
        node_inst_id = self.client.node_instances.list(
            deployment_id=deployment_id)[0].id

        return execution, node_inst_id, deployment_id

    def _execute_and_cancel_execution(self, workflow_id, force=False,
                                      wait_for_termination=True,
                                      is_wait_for_asleep_node=True,
                                      workflow_params=None):

        execution, node_inst_id, deployment_id = self._execute_from_resource(
            workflow_id, workflow_params, 'dsl/sleep_workflows.yaml')
        if is_wait_for_asleep_node:
            self._check_node_instance_state('asleep', node_inst_id)

        execution = self.client.executions.cancel(execution.id, force)
        expected_status = (Execution.FORCE_CANCELLING if force else
                           Execution.CANCELLING)
        self.assertEqual(expected_status, execution.status)
        if wait_for_termination:
            self.wait_for_execution_to_end(execution)
            execution = self.client.executions.get(execution.id)
        return execution, deployment_id

    @retry(wait_fixed=300, stop_max_attempt_number=10)
    def _assert_execution_cancelled(self, execution, deployment_id):
        self.assertEqual(Execution.CANCELLED, execution.status)
        self.assertIsNotNone(execution.ended_at)
        invocations = self.get_runtime_property(deployment_id,
                                                'mock_operation_invocation')[0]
        self.assertEqual(1, len(invocations))
        self.assertDictEqual(invocations[0], {'before-sleep': None})

    def test_dry_run_execution(self):
        expected_messages = {
            "Starting 'install' workflow execution (dry run)",
            "Validating node instance before creation: nothing to do",
            "Precreating node instance: nothing to do",
            "Creating node instance",
            "Sending task 'cloudmock.tasks.provision'",
            "Task started 'cloudmock.tasks.provision'",
            "Task succeeded 'cloudmock.tasks.provision (dry run)'",
            "Node instance created",
            "Configuring node instance: nothing to do",
            "Starting node instance",
            "Sending task 'cloudmock.tasks.start'",
            "Task started 'cloudmock.tasks.start'",
            "Task succeeded 'cloudmock.tasks.start (dry run)'",
            "Sending task 'cloudmock.tasks.get_state'",
            "Task started 'cloudmock.tasks.get_state'",
            "Task succeeded 'cloudmock.tasks.get_state (dry run)'",
            "Poststarting node instance: nothing to do",
            "Node instance started",
            "'install' workflow execution succeeded (dry run)"
        }

        dsl_path = resource("dsl/basic.yaml")
        _, execution_id = self.deploy_application(dsl_path,
                                                  wait_for_execution=True,
                                                  dry_run=True)
        # We're waiting for the final event (workflow execution success),
        # which might arrive after the execution status has changed to
        # "terminated", because it arrives via a different mechanism
        time.sleep(3)
        events = self.client.events.list(execution_id=execution_id)
        event_messages = {event['message'] for event in events}

        self.assertEqual(event_messages, expected_messages)

        # We expect the instances to remain unchaged after a dry run
        for instance in self.client.node_instances.list():
            self.assertEqual(instance['state'], 'uninitialized')

    def test_scheduled_execution(self):

        # The token in the container is invalid, create new valid one
        create_api_token(self.env.container_id)
        dsl_path = resource('dsl/basic.yaml')
        dep = self.deploy(dsl_path, wait=False, client=self.client)
        dep_id = dep.id
        do_retries(verify_deployment_env_created, 30,
                   container_id=self.env.container_id,
                   deployment_id=dep_id,
                   client=self.client)
        scheduled_time = generate_scheduled_for_date()

        self.client.executions.start(deployment_id=dep_id,
                                     workflow_id='install',
                                     schedule=scheduled_time)
        schedule = self.client.execution_schedules.list(
            deployment_id=dep.id)[0]
        self.assertEqual(schedule.workflow_id, 'install')
        self.assertIn('install_', schedule.id)

        self.wait_for_scheduled_execution_to_fire(dep_id)
        self.client.execution_schedules.delete(schedule.id, dep_id)

    def test_schedule_execution_snapshot_running_multi_tenant(self):
        """
        - default_tenant: system execution (snapshot) is running
        - tenant_0: scheduled execution

        Scheduled execution 'wakes up' while snapshot is running in a different
        tenant, we expect scheduled execution to become 'queued', and
        start only when the snapshot terminates.

        """
        # The token in the container is invalid, create new valid one
        create_api_token(self.env.container_id)
        create_tenants_and_add_users(client=self.client, num_of_tenants=1)
        tenant_client = self.create_rest_client(
            username='user_0', password='password', tenant='tenant_0',
        )
        dsl_path = resource('dsl/sleep_workflows.yaml')
        dep = self.deploy(dsl_path, wait=False, client=tenant_client)
        dep_id = dep.id
        time.sleep(2)

        # default_tenant: create snapshot and keep it's status 'started'
        snapshot = self._create_snapshot_and_modify_execution_status(
            Execution.STARTED)

        # tenant_0: schedule an execution for 1 min in the future
        scheduled_time = generate_scheduled_for_date()
        tenant_client.executions.start(deployment_id=dep_id,
                                       workflow_id='install',
                                       schedule=scheduled_time)
        execution = self.wait_for_scheduled_execution_to_fire(dep_id)
        self._assert_execution_status(execution.id,
                                      Execution.QUEUED, tenant_client)
        self.client.executions.update(snapshot.id, Execution.TERMINATED)
        self.wait_for_execution_to_end(execution, client=tenant_client)
        schedule = tenant_client.execution_schedules.list(
            deployment_id=dep.id)[0]
        tenant_client.execution_schedules.delete(schedule.id, dep_id)

    def test_two_scheduled_execution_same_tenant(self):
        """
        Schedule 2 executions to start a second apart.
        """
        # The token in the container is invalid, create new valid one
        create_api_token(self.env.container_id)
        dsl_path = resource('dsl/basic.yaml')
        dep1 = self.deploy(dsl_path, wait=False, client=self.client)
        dep2 = self.deploy(dsl_path, wait=False, client=self.client)
        dep1_id = dep1.id
        dep2_id = dep2.id
        do_retries(verify_deployment_env_created, 30,
                   container_id=self.env.container_id,
                   deployment_id=dep1_id,
                   client=self.client)
        do_retries(verify_deployment_env_created, 30,
                   container_id=self.env.container_id,
                   deployment_id=dep2_id,
                   client=self.client)
        scheduled_time = generate_scheduled_for_date()
        self.client.executions.start(deployment_id=dep1_id,
                                     workflow_id='install',
                                     schedule=scheduled_time)
        self.client.executions.start(deployment_id=dep2_id,
                                     workflow_id='install',
                                     schedule=scheduled_time)
        self.wait_for_scheduled_execution_to_fire(dep1_id)
        self.wait_for_scheduled_execution_to_fire(dep2_id)
        schedule1 = self.client.execution_schedules.list(
            deployment_id=dep1.id)[0]
        schedule2 = self.client.execution_schedules.list(
            deployment_id=dep2.id)[0]
        self.client.execution_schedules.delete(schedule1.id, dep1_id)
        self.client.execution_schedules.delete(schedule2.id, dep2_id)

    def test_schedule_execution_while_snapshot_running_same_tenant(self):

        # The token in the container is invalid, create new valid one
        create_api_token(self.env.container_id)
        dsl_path = resource('dsl/sleep_workflows.yaml')
        dep = self.deploy(dsl_path, wait=False, client=self.client)
        dep_id = dep.id
        do_retries(verify_deployment_env_created, 30,
                   container_id=self.env.container_id,
                   deployment_id=dep_id,
                   client=self.client)
        # Create snapshot and keep it's status 'started'
        snapshot_1 = self._create_snapshot_and_modify_execution_status(
            Execution.STARTED)

        scheduled_time = generate_scheduled_for_date()
        self.client.executions.start(deployment_id=dep_id,
                                     workflow_id='install',
                                     schedule=scheduled_time)
        execution = self.wait_for_scheduled_execution_to_fire(dep_id)
        self._assert_execution_status(execution.id, Execution.QUEUED)
        self.client.executions.update(snapshot_1.id, Execution.TERMINATED)
        self.wait_for_execution_to_end(execution)
        schedule = self.client.execution_schedules.list(
            deployment_id=dep.id)[0]
        self.client.execution_schedules.delete(schedule.id, dep_id)

    def test_schedule_execution_and_create_snapshot_same_tenant(self):
        """
        Schedule an execution, then create snapshot.
        Execution 'wakes up' while snapshot is still running, so it becomes
        'queued' and start when snapshot terminates.
        """
        # The token in the container is invalid, create new valid one
        create_api_token(self.env.container_id)
        dsl_path = resource('dsl/sleep_workflows.yaml')
        dep = self.deploy(dsl_path, wait=False, client=self.client)
        dep_id = dep.id
        do_retries(verify_deployment_env_created, 30,
                   container_id=self.env.container_id,
                   deployment_id=dep_id,
                   client=self.client)

        # Create snapshot and keep it's status 'started'
        snapshot = self._create_snapshot_and_modify_execution_status(
            Execution.STARTED)

        scheduled_time = generate_scheduled_for_date()
        self.client.executions.start(deployment_id=dep_id,
                                     workflow_id='install',
                                     schedule=scheduled_time)

        execution = self.wait_for_scheduled_execution_to_fire(dep_id)
        self._assert_execution_status(execution.id, Execution.QUEUED)
        self.client.executions.update(snapshot.id, Execution.TERMINATED)
        self.wait_for_execution_to_end(execution)
        schedule = self.client.execution_schedules.list(
            deployment_id=dep.id)[0]
        self.client.execution_schedules.delete(schedule.id, dep_id)

    def test_schedule_execution_while_execution_running_under_same_dep(self):
        """
        Start an execution and while it is running schedule an execution
        for the future, under the same deployment.

        """
        # The token in the container is invalid, create new valid one
        create_api_token(self.env.container_id)
        dsl_path = resource('dsl/sleep_workflows.yaml')
        dep = self.deploy(dsl_path, wait=False, client=self.client)
        dep_id = dep.id
        do_retries(verify_deployment_env_created, 30,
                   container_id=self.env.container_id,
                   deployment_id=dep_id,
                   client=self.client)
        execution1 = self.client.executions.start(deployment_id=dep_id,
                                                  workflow_id='install')
        self._wait_for_exec_to_end_and_modify_status(execution1,
                                                     Execution.STARTED)

        scheduled_time = generate_scheduled_for_date()
        self.client.executions.start(deployment_id=dep_id,
                                     workflow_id='install',
                                     schedule=scheduled_time)
        self.client.executions.update(execution1.id, Execution.TERMINATED)

        self.wait_for_scheduled_execution_to_fire(dep_id)
        schedule = self.client.execution_schedules.list(
            deployment_id=dep.id)[0]
        self.client.execution_schedules.delete(schedule.id, dep_id)

    @retry(wait_fixed=1000, stop_max_attempt_number=120)
    def wait_for_scheduled_execution_to_fire(self, deployment_id):
        # The execution must fire within 2 minutes.
        # if the 1st check_schedules occurs between the creation time and the
        # next :00, the 2nd check (1 min. from then) will run the execution
        executions = self.client.executions.list(deployment_id=deployment_id,
                                                 workflow_id='install',
                                                 _all_tenants=True)
        self.assertEqual(1, len(executions))
        return executions[0]
