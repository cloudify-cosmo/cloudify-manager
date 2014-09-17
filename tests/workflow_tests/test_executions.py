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

from testenv.utils import wait_for_execution_to_end
from testenv.utils import do_retries
from testenv.utils import verify_deployment_environment_creation_complete
from testenv.utils import get_resource as resource
from testenv.utils import deploy_application as deploy
from testenv import TestCase
from cloudify_rest_client.executions import Execution


class ExecutionsTest(TestCase):

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
        wait_for_execution_to_end(execution)
        execution = self.client.executions.get(execution.id)

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

    def test_get_deployments_executions_with_status(self):
        dsl_path = resource("dsl/basic.yaml")
        deployment, execution_id = deploy(dsl_path)

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
            self.assertEquals('', install_execution.error)

        self.do_assertions(assertions, timeout=10)

    def test_execution_parameters(self):
        dsl_path = resource('dsl/workflow_parameters.yaml')
        _id = uuid.uuid1()
        blueprint_id = 'blueprint_{0}'.format(_id)
        deployment_id = 'deployment_{0}'.format(_id)
        self.client.blueprints.upload(dsl_path, blueprint_id)
        self.client.deployments.create(blueprint_id, deployment_id)
        do_retries(verify_deployment_environment_creation_complete, 30,
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
        wait_for_execution_to_end(execution)
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
                                      wait_for_termination=True,
                                      is_wait_for_asleep_node=True):
        dsl_path = resource('dsl/sleep_workflows.yaml')
        _id = uuid.uuid1()
        blueprint_id = 'blueprint_{0}'.format(_id)
        deployment_id = 'deployment_{0}'.format(_id)
        self.client.blueprints.upload(dsl_path, blueprint_id)
        self.client.deployments.create(blueprint_id, deployment_id)
        do_retries(verify_deployment_environment_creation_complete, 30,
                   deployment_id=deployment_id)
        execution = self.client.executions.start(
            deployment_id, workflow_id)

        node_inst_id = self.client.node_instances.list(deployment_id)[0].id

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
            wait_for_execution_to_end(execution)
            execution = self.client.executions.get(execution.id)
        return execution, deployment_id

    def _assert_execution_cancelled(self, execution, deployment_id):
        self.assertEquals(Execution.CANCELLED, execution.status)
        invocations = self.get_plugin_data(
            plugin_name='testmockoperations',
            deployment_id=deployment_id
        )['mock_operation_invocation']
        self.assertEqual(1, len(invocations))
        self.assertDictEqual(invocations[0], {'before-sleep': None})
