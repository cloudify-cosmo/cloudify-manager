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

from integration_tests import AgentlessTestCase
from integration_tests.framework import postgresql
from cloudify_rest_client.executions import Execution
from integration_tests.framework.postgresql import run_query
from cloudify_rest_client.exceptions import CloudifyClientError
from integration_tests.tests.utils import (
    verify_deployment_environment_creation_complete,
    do_retries,
    get_resource as resource)


class ExecutionsTest(AgentlessTestCase):

    def _wait_for_exec_to_end_and_modify_status(self, execution, new_status):
        self.wait_for_execution_to_end(execution)
        self._manually_update_execution_status(new_status, execution.id)
        self._assert_correct_execution_status(execution.id, new_status)

        return execution

    def _create_snapshot_and_modify_execution_status(self, new_status):
        snapshot = self.client.snapshots.create('snapshot_1',
                                                include_metrics=True,
                                                include_credentials=True,
                                                include_logs=True,
                                                include_events=True,
                                                queue=True)
        execution = self._wait_for_exec_to_end_and_modify_status(snapshot,
                                                                 new_status)
        return execution

    def _update_to_terminated_and_assert_propper_dequeue(self, id1, id2):

        """
        This method modifies the status of the first execution (id1) to
        `terminated` in order to enable the de-queue mechanism to start, and
        then assert that the second execution (that was queued) was properly
        de-queued and run.
        :param id1: execution id of the first execution that was created, and
                    about to change status to `terminated`.
        :param id2: execution id of the second execution that was created

        """

        self.client.executions.update(id1, 'terminated')

        queued_execution = self.client.executions.get(id2)
        self.wait_for_execution_to_end(queued_execution)

        self._assert_correct_execution_status(id1, 'terminated')
        self._assert_correct_execution_status(id2, 'terminated')

    def _get_executions_list(self):
        return self.client.executions.list(deployment_id=None,
                                           include_system_workflows=True,
                                           sort='created_at',
                                           is_descending=False,
                                           _all_tenants=True,
                                           _offset=0,
                                           _size=1000).items

    @staticmethod
    def _manually_update_execution_status(new_status, id):
        run_query("UPDATE executions SET status = '{0}' WHERE id = '{1}'"
                  .format(new_status, id))

    def _assert_correct_execution_status(self, execution_id, wanted_status):
        current_status = self.client.executions.get(execution_id).status
        self.assertEquals(current_status, wanted_status)

    def test_queue_execution_while_system_execution_is_running(self):

        # Create snapshot and make sure it's state remains 'started'
        # so that new executions will be queued
        snapshot = self._create_snapshot_and_modify_execution_status('started')

        # Create an 'install' execution and make sure it's being queued
        dsl_path = resource("dsl/basic.yaml")
        deployment, execution_id = self.deploy_application(
            dsl_path, wait_for_execution=False, queue=True)
        self._assert_correct_execution_status(execution_id, 'queued')

        # Update snapshot state to 'terminated' so the queued 'install'
        #  execution will start
        self._update_to_terminated_and_assert_propper_dequeue(
            snapshot.id, execution_id)

    def test_queue_system_execution_while_system_execution_is_running(self):

        # Create snapshot and make sure it's state remains 'started'
        # so that new executions will be queued
        snapshot = self._create_snapshot_and_modify_execution_status('started')

        # Create another system execution and make sure it's being  queued
        second_snap = self.client.snapshots.create('snapshot_2',
                                                   include_metrics=True,
                                                   include_credentials=True,
                                                   include_logs=True,
                                                   include_events=True,
                                                   queue=True)
        self._assert_correct_execution_status(second_snap.id, 'queued')

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
        snapshot = self._create_snapshot_and_modify_execution_status('queued')

        # Create an 'install' execution
        execution = self.execute_workflow(workflow_name='install',
                                          deployment_id=deployment.id,
                                          wait_for_execution=False,
                                          queue=True)
        self._assert_correct_execution_status(execution.id, 'queued')

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
        execution = self._wait_for_exec_to_end_and_modify_status(execution,
                                                                 'started')

        # Create a system execution and make sure it's being queued
        second_snap = self.client.snapshots.create('snapshot_2',
                                                   include_metrics=True,
                                                   include_credentials=True,
                                                   include_logs=True,
                                                   include_events=True,
                                                   queue=True)
        self._assert_correct_execution_status(second_snap.id, 'queued')

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
        execution_1 = self._wait_for_exec_to_end_and_modify_status(execution_1,
                                                                   'started')

        # Start a second 'install' under the same deployment and assert it's
        # being queued
        execution_2 = self.execute_workflow(workflow_name='uninstall',
                                            deployment_id=deployment.id,
                                            wait_for_execution=False,
                                            queue=True)
        self._assert_correct_execution_status(execution_2.id, 'queued')

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
        self._wait_for_exec_to_end_and_modify_status(execution_1, 'started')

        # Start a second 'install' under different deployment
        execution_2 = self.execute_workflow(workflow_name='install',
                                            deployment_id=deployment_2.id,
                                            wait_for_execution=False,
                                            queue=True)

        # Make sure the second 'install' ran in parallel
        self.wait_for_execution_to_end(execution_2)
        self._assert_correct_execution_status(execution_2.id, 'terminated')

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
        snapshot = self._create_snapshot_and_modify_execution_status('started')

        # Create another system execution
        snapshot_2 = self.client.snapshots.create('snapshot_2',
                                                  include_metrics=True,
                                                  include_credentials=True,
                                                  include_logs=True,
                                                  include_events=True,
                                                  queue=True)

        # Start 'install' execution
        execution = self.execute_workflow(workflow_name='sleep',
                                          deployment_id=deployment.id,
                                          wait_for_execution=False,
                                          queue=True)

        # Make sure snapshot_2 and execution are queued (since there's a
        # running system execution)
        self._assert_correct_execution_status(snapshot_2.id, 'queued')
        self._assert_correct_execution_status(execution.id, 'queued')

        # Update first snapshot status to terminated
        self.client.executions.update(snapshot.id, 'terminated')

        # Make sure snapshot_2 started (or pending) while the execution
        # is queued again
        current_status = self.client.executions.get(snapshot_2.id).status
        self.assertIn(current_status, ['pending', 'started'])
        self._assert_correct_execution_status(execution.id, 'queued')

    def test_run_exec_from_queue_while_system_execution_is_queued(self):
        """
        - System execution (snapshot) is running
        - Queue contains: a regular execution and another system execution
        Once the first snapshot finishes we expect the regular execution to run
        (even though snapshot_2 is in the queue) and the second snapshot
        to be queued again.

        """
        # Create deployment
        dsl_path = resource('dsl/sleep_workflows.yaml')
        deployment = self.deploy(dsl_path)

        # Create snapshot and make sure it's state remains 'started'
        # so that new executions will be queued
        snapshot = self._create_snapshot_and_modify_execution_status('started')

        # Start 'install' execution
        execution = self.execute_workflow(workflow_name='sleep',
                                          deployment_id=deployment.id,
                                          wait_for_execution=False,
                                          queue=True)

        # Create another system execution
        snapshot_2 = self.client.snapshots.create('snapshot_2',
                                                  include_metrics=True,
                                                  include_credentials=True,
                                                  include_logs=True,
                                                  include_events=True,
                                                  queue=True)

        # Make sure execution and snapshot_2 are queued (since there's a
        # running system execution)
        self._assert_correct_execution_status(snapshot_2.id, 'queued')
        self._assert_correct_execution_status(execution.id, 'queued')

        # Update first snapshot status to terminated
        self.client.executions.update(snapshot.id, 'terminated')

        # Make sure exeuction status is started (or pending) even though
        # there's a queued system execution
        current_status = self.client.executions.get(execution.id).status
        self.assertIn(current_status, ['pending', 'started'])
        self._assert_correct_execution_status(snapshot_2.id, 'queued')

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
        snapshot = self._create_snapshot_and_modify_execution_status('started')

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
        self._assert_correct_execution_status(execution_1.id, 'queued')
        self._assert_correct_execution_status(execution_2.id, 'queued')

        # Update snapshot status to terminated
        self.client.executions.update(snapshot.id, 'terminated')

        # Make sure exeuction_1 status is started (or pending) and that
        #  execution_2 is still queued
        current_status = self.client.executions.get(execution_1.id).status
        self.assertIn(current_status, ['pending', 'started'])
        self._assert_correct_execution_status(execution_2.id, 'queued')

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
        snapshot = self._create_snapshot_and_modify_execution_status('started')

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
        self._assert_correct_execution_status(execution_1.id, 'queued')
        self._assert_correct_execution_status(execution_2.id, 'queued')

        # Update snapshot status to terminated
        self.client.executions.update(snapshot.id, 'terminated')

        # Make sure both executions' status is started (or pending)
        execution_1_status = self.client.executions.get(execution_1.id).status
        execution_2_status = self.client.executions.get(execution_2.id).status
        self.assertIn(execution_1_status, ['pending', 'started'])
        self.assertIn(execution_2_status, ['pending', 'started'])

    def test_queue_system_exec_from_queue_while_system_exec_is_running(self):
        """
        - System execution (snapshot) is running
        - Queue contains: two more snapshots. (3 snapshots in total)
        Once the first snapshot finishes we expect the second one to run and
        the third one to be queued again.

        """

        # Create snapshot and make sure it's state remains 'started'
        # so that new executions will be queued
        snapshot = self._create_snapshot_and_modify_execution_status('started')

        # Create another system execution
        snapshot_2 = self.client.snapshots.create('snapshot_2',
                                                  include_metrics=True,
                                                  include_credentials=True,
                                                  include_logs=True,
                                                  include_events=True,
                                                  queue=True)
        snapshot_3 = self.client.snapshots.create('snapshot_3',
                                                  include_metrics=True,
                                                  include_credentials=True,
                                                  include_logs=True,
                                                  include_events=True,
                                                  queue=True)

        # Make sure the 2 snapshots are queued (since there's a
        # running system execution)
        self._assert_correct_execution_status(snapshot_2.id, 'queued')
        self._assert_correct_execution_status(snapshot_3.id, 'queued')

        # Update first snapshot status to terminated
        self.client.executions.update(snapshot.id, 'terminated')

        # Make sure snapshot_2 started (or pending) while the snapshot_3
        # is queued again
        current_status = self.client.executions.get(snapshot_2.id).status
        self.assertIn(current_status, ['pending', 'started'])
        self._assert_correct_execution_status(snapshot_3.id, 'queued')

    def test_queue_system_exec_from_queue_while_exec_is_running(self):
        """
        - System execution (snapshot) is running
        - Queue contains: a regular execution ('install') and a system
          execution (snapshot).
        Once the first snapshot finishes we expect the regular execution to run
        and the third one (the snapshot) to be queued again.

        """
        # Create deployment
        dsl_path = resource('dsl/sleep_workflows.yaml')
        deployment_1 = self.deploy(dsl_path)

        # Create snapshot and make sure it's state remains 'started'
        # so that new executions will be queued
        snapshot_1 = self._create_snapshot_and_modify_execution_status(
            'started')

        # create a regular execution and a system execution
        execution = self.execute_workflow(workflow_name='install',
                                          deployment_id=deployment_1.id,
                                          wait_for_execution=False,
                                          queue=True)

        snapshot_2 = self.client.snapshots.create('snapshot_2',
                                                  include_metrics=True,
                                                  include_credentials=True,
                                                  include_logs=True,
                                                  include_events=True,
                                                  queue=True)

        # Make sure snapshot_2 and execution are queued (since there's a
        # running system execution)
        self._assert_correct_execution_status(execution.id, 'queued')
        self._assert_correct_execution_status(snapshot_2.id, 'queued')

        # Update first snapshot status to terminated
        self.client.executions.update(snapshot_1.id, 'terminated')

        # Make sure snapshot_2 started (or pending) while the snapshot_3
        # is queued again
        current_status = self.client.executions.get(execution.id).status
        self.assertIn(current_status, ['pending', 'started'])
        self._assert_correct_execution_status(snapshot_2.id, 'queued')

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
        self._wait_for_exec_to_end_and_modify_status(execution, 'queued')
        try:
            self.client.deployments.delete(deployment_1.id)
        except CloudifyClientError as e:
            self.assertIn('There are running or queued', e.message)
            self.assertEquals(e.status_code, 400)
            self.assertEquals(e.error_code, 'dependent_exists_error')

    def test_cancel_queued_execution(self):
        # Create snapshot and make sure it's state remains 'queued'
        snapshot = self._create_snapshot_and_modify_execution_status('queued')
        self.client.executions.cancel(snapshot.id)
        time.sleep(3)
        self._assert_correct_execution_status(snapshot.id, 'cancelled')

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
        self.assertEquals(Execution.FORCE_CANCELLING, execution.status)
        self.wait_for_execution_to_end(execution)
        execution = self.client.executions.get(execution.id)

        self._assert_execution_cancelled(execution, deployment_id)

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
        self.assertEquals(Execution.CANCELLED, execution.status)
        data = self.get_plugin_data(
            plugin_name='testmockoperations',
            deployment_id=deployment_id
        )
        self.assertEqual(data, {})

    def test_sort_executions(self):
        dsl_path = resource("dsl/basic.yaml")
        deployment, execution_id = self.deploy_application(dsl_path)
        self.wait_for_execution_to_end(
                self.client.executions.get(execution_id))
        deployment, execution_id = self.deploy_application(dsl_path)
        self.wait_for_execution_to_end(
                self.client.executions.get(execution_id))
        deployments_executions = self.client.executions.list(sort='created_at')
        for i in range(len(deployments_executions)-1):
            self.assertTrue(deployments_executions[i]['created_at'] <
                            deployments_executions[i+1]['created_at'],
                            'execution list not sorted correctly')
        deployments_executions = self.client.executions.list(
                sort='created_at',
                is_descending=True)
        for i in range(len(deployments_executions)-1):
            self.assertTrue(deployments_executions[i]['created_at'] >
                            deployments_executions[i+1]['created_at'],
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
            self.assertEquals(2, len(deployments_executions))
            self.assertIn(execution_id, [deployments_executions[0].id,
                                         deployments_executions[1].id])
            install_execution = \
                deployments_executions[0] if execution_id == \
                deployments_executions[0].id else deployments_executions[1]
            self.assertEquals(Execution.TERMINATED, install_execution.status)
            self.assertIsNotNone(install_execution.created_at)
            self.assertIsNotNone(install_execution.ended_at)
            self.assertEquals('', install_execution.error)

        self.do_assertions(assertions, timeout=10)

    def test_execution_parameters(self):
        dsl_path = resource('dsl/workflow_parameters.yaml')
        _id = uuid.uuid1()
        blueprint_id = 'blueprint_{0}'.format(_id)
        deployment_id = 'deployment_{0}'.format(_id)
        self.client.blueprints.upload(dsl_path, blueprint_id)
        self.client.deployments.create(blueprint_id, deployment_id,
                                       skip_plugins_validation=True)
        do_retries(verify_deployment_environment_creation_complete, 60,
                   deployment_id=deployment_id)
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
        invocations = self.get_plugin_data(
            plugin_name='testmockoperations',
            deployment_id=deployment_id
        )['mock_operation_invocation']
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
        self.assertEquals(Execution.TERMINATED, execution.status)

        # Manually updating the status, because the client checks for
        # correct transitions
        postgresql.run_query(
            "UPDATE executions SET status='started' "
            "WHERE id='{0}'".format(execution_id)
        )
        execution = self.client.executions.get(execution_id)
        self.assertEquals('started', execution.status)
        execution = self.client.executions.update(execution_id,
                                                  'pending',
                                                  'some-error')
        self.assertEquals('pending', execution.status)
        self.assertEquals('some-error', execution.error)
        # verifying that updating only the status field also resets the
        # error field to an empty string
        execution = self.client.executions.update(execution_id, 'terminated')
        self.assertEquals('terminated', execution.status)
        self.assertEquals('', execution.error)

    def _execute_and_cancel_execution(self, workflow_id, force=False,
                                      wait_for_termination=True,
                                      is_wait_for_asleep_node=True,
                                      workflow_params=None):
        dsl_path = resource('dsl/sleep_workflows.yaml')
        _id = uuid.uuid1()
        blueprint_id = 'blueprint_{0}'.format(_id)
        deployment_id = 'deployment_{0}'.format(_id)
        self.client.blueprints.upload(dsl_path, blueprint_id)
        self.client.deployments.create(blueprint_id, deployment_id,
                                       skip_plugins_validation=True)
        do_retries(verify_deployment_environment_creation_complete, 30,
                   deployment_id=deployment_id)
        execution = self.client.executions.start(
            deployment_id, workflow_id, parameters=workflow_params)

        node_inst_id = self.client.node_instances.list(
            deployment_id=deployment_id)[0].id

        if is_wait_for_asleep_node:
            for retry in range(30):
                if self.client.node_instances.get(
                        node_inst_id).state == 'asleep':
                    break
                time.sleep(1)
            else:
                raise RuntimeError("Execution was expected to go"
                                   " into 'sleeping' status")

        execution = self.client.executions.cancel(execution.id, force)
        expected_status = Execution.FORCE_CANCELLING if force else \
            Execution.CANCELLING
        self.assertEquals(expected_status, execution.status)
        if wait_for_termination:
            self.wait_for_execution_to_end(execution)
            execution = self.client.executions.get(execution.id)
        return execution, deployment_id

    def _assert_execution_cancelled(self, execution, deployment_id):
        self.assertEquals(Execution.CANCELLED, execution.status)
        self.assertIsNotNone(execution.ended_at)
        invocations = self.get_plugin_data(
            plugin_name='testmockoperations',
            deployment_id=deployment_id
        )['mock_operation_invocation']
        self.assertEqual(1, len(invocations))
        self.assertDictEqual(invocations[0], {'before-sleep': None})

    def test_dry_run_execution(self):
        expected_messages = {
            "Starting 'install' workflow execution (dry run)",
            "Creating node",
            "Sending task 'cloudmock.tasks.provision'",
            "Task started 'cloudmock.tasks.provision'",
            "Task succeeded 'cloudmock.tasks.provision (dry run)'",
            "Configuring node",
            "Starting node",
            "Sending task 'cloudmock.tasks.start'",
            "Task started 'cloudmock.tasks.start'",
            "Task succeeded 'cloudmock.tasks.start (dry run)'",
            "Sending task 'cloudmock.tasks.get_state'",
            "Task started 'cloudmock.tasks.get_state'",
            "Task succeeded 'cloudmock.tasks.get_state (dry run)'",
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

        self.assertEquals(event_messages, expected_messages)

        # We expect the instances to remain unchaged after a dry run
        for instance in self.client.node_instances.list():
            self.assertEqual(instance['state'], 'uninitialized')
