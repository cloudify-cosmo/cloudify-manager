########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
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
from contextlib import contextmanager

from cloudify.workflows import tasks
from cloudify_rest_client.executions import Execution

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource
from integration_tests.tests.constants import PROVIDER_NAME


class TestResumeMgmtworker(AgentlessTestCase):
    wait_message = 'WAITING FOR FILE'
    target_file = '/tmp/continue_test'

    @contextmanager
    def _set_retries(self, retries, retry_interval=0):
        context = self.client.manager.get_context()['context']
        original_workflows = context['cloudify']['workflows'].copy()
        context['cloudify']['workflows'].update({
            'task_retries': retries,
            'subgraph_retries': retries,
            'task_retry_interval': retry_interval
        })
        self.client.manager.update_context(PROVIDER_NAME, context)
        try:
            yield
        finally:
            context['cloudify']['workflows'] = original_workflows
            self.client.manager.update_context(PROVIDER_NAME, context)

    def _create_deployment(self):
        dsl_path = resource("dsl/resumable_mgmtworker.yaml")
        return self.deploy(dsl_path)

    def _start_execution(self, deployment, operation, node_ids=None):
        parameters = {
            'operation': operation,
            'run_by_dependency_order': True,
            'operation_kwargs': {
                'wait_message': self.wait_message,
                'target_file': self.target_file
            }
        }
        if node_ids:
            parameters['node_ids'] = node_ids
        return self.execute_workflow(
            workflow_name='execute_operation',
            wait_for_execution=False,
            deployment_id=deployment.id,
            parameters=parameters)

    def _wait_for_log(self, execution):
        self.logger.info('Waiting for operation to start')
        while True:
            logs = self.client.events.list(
                execution_id=execution.id, include_logs=True)
            if any(self.wait_message == log['message'] for log in logs):
                break
            time.sleep(1)

    def _find_remote_operation(self, graph_id):
        """Find the only remote operation in the given graph"""
        remote_operations = [
            op for op in self.client.operations.list(graph_id)
            if op.type == 'RemoteWorkflowTask'
        ]
        self.assertEqual(len(remote_operations), 1)
        return remote_operations[0]

    def _stop_mgmtworker(self):
        self.logger.info('Stopping mgmtworker')
        self.execute_on_manager('systemctl stop cloudify-mgmtworker')

    def _create_target_file(self):
        self.execute_on_manager('touch {0}'.format(self.target_file))
        self.addCleanup(self.execute_on_manager,
                        'rm -rf {0}'.format(self.target_file))

    def _start_mgmtworker(self):
        self.logger.info('Restarting mgmtworker')
        self.execute_on_manager('systemctl start cloudify-mgmtworker')

    def test_cancel_updates_operation(self):
        """When a workflow is cancelled, the operations that are actually
        finish are still updated to 'succeeded'."""
        dep = self._create_deployment()
        execution = self._start_execution(
            dep, 'interface1.op_resumable', node_ids=['node1'])
        self._wait_for_log(execution)
        self.client.executions.cancel(execution.id)
        execution = self.wait_for_execution_to_end(execution)
        self.assertEqual(execution.status, Execution.CANCELLED)

        graphs = self.client.tasks_graphs.list(
            execution.id, name='execute_operation')
        self.assertEqual(len(graphs), 1)

        # check that the task is started
        task = self._find_remote_operation(graphs[0].id)
        self.assertEqual(task.state, tasks.TASK_STARTED)

        self._create_target_file()

        # and now wait for the task to finish. It polls every 1 second, so
        # allow a 3 seconds wait.
        time.sleep(3)
        task = self._find_remote_operation(graphs[0].id)
        self.assertEqual(task.state, tasks.TASK_SUCCEEDED)

    def test_resumable_mgmtworker_op(self):
        # start a workflow, stop mgmtworker, restart mgmtworker, check that
        # one operation was resumed and another was other executed
        dep = self._create_deployment()
        instance = self.client.node_instances.list(
            deployment_id=dep.id, node_id='node1')[0]
        instance2 = self.client.node_instances.list(
            deployment_id=dep.id, node_id='node2')[0]
        execution = self._start_execution(dep, 'interface1.op_resumable')
        self._wait_for_log(execution)

        self.assertFalse(self.client.node_instances.get(instance.id)
                         .runtime_properties['resumed'])
        self.assertNotIn(
            'marked',
            self.client.node_instances.get(instance2.id).runtime_properties)

        self._stop_mgmtworker()
        self._create_target_file()
        self._start_mgmtworker()

        self.logger.info('Waiting for the execution to finish')
        execution = self.wait_for_execution_to_end(execution)
        self.assertEqual(execution.status, 'terminated')

        self.assertTrue(self.client.node_instances.get(instance.id)
                        .runtime_properties['resumed'])
        self.assertTrue(self.client.node_instances.get(instance2.id)
                        .runtime_properties['marked'])

    def test_nonresumable_mgmtworker_op(self):
        # start a workflow, stop mgmtworker, restart mgmtworker, check that
        # the operation which is nonresumable did not run again, and the
        # dependent operation didn't run either
        dep = self._create_deployment()
        instance = self.client.node_instances.list(
            deployment_id=dep.id, node_id='node1')[0]
        instance2 = self.client.node_instances.list(
            deployment_id=dep.id, node_id='node2')[0]
        execution = self._start_execution(dep, 'interface1.op_nonresumable')
        self._wait_for_log(execution)

        self._stop_mgmtworker()
        self._create_target_file()
        self._start_mgmtworker()

        self.logger.info('Waiting for the execution to fail')
        self.assertRaises(RuntimeError,
                          self.wait_for_execution_to_end, execution)

        self.assertFalse(self.client.node_instances.get(instance.id)
                         .runtime_properties['resumed'])
        self.assertNotIn(
            'marked',
            self.client.node_instances.get(instance2.id).runtime_properties)

    def test_resume_failed(self):
        dep = self._create_deployment()
        instance = self.client.node_instances.list(
            deployment_id=dep.id, node_id='node1')[0]
        instance2 = self.client.node_instances.list(
            deployment_id=dep.id, node_id='node2')[0]
        execution = self._start_execution(dep, 'interface1.op_failing')

        self.logger.info('Waiting for the execution to fail')
        self.assertRaises(RuntimeError,
                          self.wait_for_execution_to_end, execution)

        self._create_target_file()
        self.client.executions.resume(execution.id, force=True)
        execution = self.wait_for_execution_to_end(execution)
        self.assertEqual(execution.status, 'terminated')

        self.assertTrue(self.client.node_instances.get(instance.id)
                        .runtime_properties['resumed'])
        self.assertTrue(self.client.node_instances.get(instance2.id)
                        .runtime_properties['marked'])

    def test_resume_no_duplicates(self):
        """Check that retried tasks aren't duplicated after a resume.

        Run a workflow that, for node instance 1, retries the operation
        once and then fails.
        Resume the workflow with reset-operations (force) and check that
        the operation was ran only once after the resume.
        """
        dep = self._create_deployment()
        instance = self.client.node_instances.list(
            deployment_id=dep.id, node_id='node1')[0]
        instance2 = self.client.node_instances.list(
            deployment_id=dep.id, node_id='node2')[0]
        with self._set_retries(5):
            execution = self._start_execution(dep, 'interface1.op_retrying')

            self.logger.info('Waiting for the execution to fail')
            self.assertRaises(RuntimeError,
                              self.wait_for_execution_to_end, execution)

        self.assertNotIn(
            'marked',
            self.client.node_instances.get(instance2.id).runtime_properties)
        self.assertEqual(self.client.node_instances.get(instance.id)
                         .runtime_properties['count'], 2)

        self.client.executions.resume(execution.id, force=True)
        execution = self.wait_for_execution_to_end(execution)
        self.assertEqual(execution.status, 'terminated')

        # if it is 4, that means the task ran twice after resume
        self.assertEqual(self.client.node_instances.get(instance.id)
                         .runtime_properties['count'], 3)
        self.assertTrue(self.client.node_instances.get(instance2.id)
                        .runtime_properties['marked'])

    def test_resume_cancelled_resumable(self):
        dep = self._create_deployment()
        instance = self.client.node_instances.list(
            deployment_id=dep.id, node_id='node1')[0]
        instance2 = self.client.node_instances.list(
            deployment_id=dep.id, node_id='node2')[0]
        execution = self._start_execution(dep, 'interface1.op_resumable')
        self._wait_for_log(execution)
        self.client.executions.cancel(execution.id, kill=True)
        self.logger.info('Waiting for the execution to fail')
        execution = self.wait_for_execution_to_end(execution)
        self.assertEqual(execution.status, 'cancelled')

        self._create_target_file()
        execution = self.client.executions.resume(execution.id)
        execution = self.wait_for_execution_to_end(execution)
        self.assertEqual(execution.status, 'terminated')

        self.assertTrue(self.client.node_instances.get(instance.id)
                        .runtime_properties['resumed'])
        self.assertTrue(self.client.node_instances.get(instance2.id)
                        .runtime_properties['marked'])

    def test_resume_cancelled_nonresumable(self):
        dep = self._create_deployment()
        instance = self.client.node_instances.list(
            deployment_id=dep.id, node_id='node1')[0]
        instance2 = self.client.node_instances.list(
            deployment_id=dep.id, node_id='node2')[0]
        execution = self._start_execution(dep, 'interface1.op_nonresumable')
        self._wait_for_log(execution)
        self.client.executions.cancel(execution.id, kill=True)
        self.logger.info('Waiting for the execution to fail')
        execution = self.wait_for_execution_to_end(execution)
        self.assertEqual(execution.status, 'cancelled')

        self._create_target_file()
        execution = self.client.executions.resume(execution.id)
        self.assertRaises(RuntimeError,
                          self.wait_for_execution_to_end, execution)

        self.assertFalse(self.client.node_instances.get(instance.id)
                         .runtime_properties['resumed'])
        self.assertNotIn('marked',
                         self.client.node_instances.get(instance2.id)
                         .runtime_properties)

    def test_force_resume_cancelled_nonresumable(self):
        dep = self._create_deployment()
        instance = self.client.node_instances.list(
            deployment_id=dep.id, node_id='node1')[0]
        instance2 = self.client.node_instances.list(
            deployment_id=dep.id, node_id='node2')[0]
        execution = self._start_execution(dep, 'interface1.op_nonresumable')
        self._wait_for_log(execution)
        self.client.executions.cancel(execution.id)
        self.logger.info('Waiting for the execution to fail')
        execution = self.wait_for_execution_to_end(execution)
        self.assertEqual(execution.status, 'cancelled')

        self._create_target_file()
        execution = self.client.executions.resume(execution.id, force=True)
        execution = self.wait_for_execution_to_end(execution)
        self.assertEqual(execution.status, 'terminated')

        self.assertTrue(self.client.node_instances.get(instance.id)
                        .runtime_properties['resumed'])
        self.assertTrue(self.client.node_instances.get(instance2.id)
                        .runtime_properties['marked'])
