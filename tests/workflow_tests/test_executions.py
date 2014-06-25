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


__author__ = 'dan'

import time
import uuid
from testenv import (TestCase,
                     wait_for_execution_to_end,
                     do_retries,
                     verify_workers_installation_complete,
                     send_task,
                     get_resource as resource,
                     deploy_application as deploy)
from cloudify_rest_client.executions import Execution


class ExecutionsTest(TestCase):

    def test_cancel_execution(self):
        execution = self._execute_and_cancel_execution(
            'sleep_with_cancel_support')
        self._assert_execution_cancelled(execution)

    def test_force_cancel_execution(self):
        execution = self._execute_and_cancel_execution(
            'sleep', True)
        self._assert_execution_cancelled(execution)

    def test_cancel_execution_with_graph_workflow(self):
        execution = self._execute_and_cancel_execution(
            'sleep_with_graph_usage')
        self._assert_execution_cancelled(execution)

    def test_cancel_execution_and_then_force_cancel(self):
        execution = self._execute_and_cancel_execution(
            'sleep', False, False)

        # cancel didn't work (unsupported) - use force-cancel instead
        execution = self.client.executions.cancel(execution.id, True)
        self.assertEquals(Execution.FORCE_CANCELLING, execution.status)
        wait_for_execution_to_end(execution)
        execution = self.client.executions.get(execution.id)

        self._assert_execution_cancelled(execution)

    def test_cancel_on_non_supporting_workflow(self):
        execution = self._execute_and_cancel_execution(
            'sleep')
        self.assertEquals(Execution.TERMINATED, execution.status)

        from plugins.testmockoperations.tasks import \
            get_mock_operation_invocations

        invocations = send_task(get_mock_operation_invocations).get(timeout=10)
        self.assertEqual(2, len(invocations))
        self.assertDictEqual(invocations[0], {'before-sleep': None})
        self.assertDictEqual(invocations[1], {'after-sleep': None})

    def test_cancel_execution_before_it_started(self):
        execution = self._execute_and_cancel_execution(
            'sleep_with_cancel_support', False, True, 0)
        self.assertEquals(Execution.CANCELLED, execution.status)

        from plugins.testmockoperations.tasks import \
            get_mock_operation_invocations

        invocations = send_task(get_mock_operation_invocations).get(timeout=10)
        self.assertEqual(0, len(invocations))

    def test_get_deployments_executions_with_status(self):
        dsl_path = resource("dsl/basic.yaml")
        deployment, execution_id = deploy(dsl_path)

        def assertions():
            deployments_executions = self.client.deployments.list_executions(
                deployment.id)
            # expecting 2 executions (1 for workers installation and 1
            # execution of 'install'). Checking the install execution's status
            self.assertEquals(2, len(deployments_executions))
            self.assertIn(execution_id, [deployments_executions[0].id,
                                         deployments_executions[1].id])
            install_execution = \
                deployments_executions[0] if execution_id == \
                deployments_executions[0].id else deployments_executions[1]
            self.assertEquals(Execution.TERMINATED, install_execution.status)
            self.assertEquals('', install_execution.error)

        self.do_assertions(assertions, timeout=10)

    def test_execution_parameters(self):
        dsl_path = resource('dsl/workflow_parameters.yaml')
        _id = uuid.uuid1()
        blueprint_id = 'blueprint_{0}'.format(_id)
        deployment_id = 'deployment_{0}'.format(_id)
        self.client.blueprints.upload(dsl_path, blueprint_id)
        self.client.deployments.create(blueprint_id, deployment_id)
        do_retries(verify_workers_installation_complete, 30,
                   deployment_id=deployment_id)
        execution_parameters = {
            'operation': 'test_interface.operation',
            'properties': {
                'key': 'different-key',
                'value': 'different-value'
            },
            'extra-property': "doesn't matter"
        }
        execution = self.client.deployments.execute(
            deployment_id, 'another_execute_operation',
            parameters=execution_parameters)
        wait_for_execution_to_end(execution)

        from plugins.testmockoperations.tasks import \
            get_mock_operation_invocations

        invocations = send_task(get_mock_operation_invocations).get(timeout=10)
        self.assertEqual(1, len(invocations))
        self.assertDictEqual(invocations[0],
                             {'different-key': 'different-value'})

        # checking for execution parameters - expecting there to be a merge
        # with overrides with workflow parameters. 'extra-property' is not
        # expected to appear as it is not defined in the blueprint
        expected_params = {
            'node_id': 'test_node',
            'operation': 'test_interface.operation',
            'properties': {
                'key': 'different-key',
                'value': 'different-value'
            }
        }
        self.assertEqual(expected_params, execution.parameters)

    def test_update_execution_status(self):
        dsl_path = resource("dsl/basic.yaml")
        _, execution_id = deploy(dsl_path,
                                 wait_for_execution=True)
        execution = self.client.executions.get(execution_id)
        self.assertEquals(Execution.TERMINATED, execution.status)
        execution = self.client.executions.update(execution_id, 'new-status')
        self.assertEquals('new-status', execution.status)
        execution = self.client.executions.update(execution_id,
                                                  'another-new-status',
                                                  'some-error')
        self.assertEquals('another-new-status', execution.status)
        self.assertEquals('some-error', execution.error)
        # verifying that updating only the status field also resets the
        # error field to an empty string
        execution = self.client.executions.update(execution_id,
                                                  'final-status')
        self.assertEquals('final-status', execution.status)
        self.assertEquals('', execution.error)

    def _execute_and_cancel_execution(self, workflow_id, force=False,
                                      wait_for_termination=True, sleep=5):
        dsl_path = resource('dsl/sleep_workflows.yaml')
        _id = uuid.uuid1()
        blueprint_id = 'blueprint_{0}'.format(_id)
        deployment_id = 'deployment_{0}'.format(_id)
        self.client.blueprints.upload(dsl_path, blueprint_id)
        self.client.deployments.create(blueprint_id, deployment_id)
        do_retries(verify_workers_installation_complete, 30,
                   deployment_id=deployment_id)
        execution = self.client.deployments.execute(
            deployment_id, workflow_id)
        time.sleep(sleep)  # wait for the execution to reach some sleep command
        execution = self.client.executions.cancel(execution.id, force)
        expected_status = Execution.FORCE_CANCELLING if force else \
            Execution.CANCELLING
        self.assertEquals(expected_status, execution.status)
        if wait_for_termination:
            wait_for_execution_to_end(execution)
            execution = self.client.executions.get(execution.id)
        return execution

    def _assert_execution_cancelled(self, execution):
        self.assertEquals(Execution.CANCELLED, execution.status)

        from plugins.testmockoperations.tasks import \
            get_mock_operation_invocations

        invocations = send_task(get_mock_operation_invocations).get(timeout=10)
        self.assertEqual(1, len(invocations))
        self.assertDictEqual(invocations[0], {'before-sleep': None})
