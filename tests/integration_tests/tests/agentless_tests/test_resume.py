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
import pytest
from contextlib import contextmanager

from cloudify.workflows import tasks
from cloudify_rest_client.executions import Execution
from cloudify_rest_client.exceptions import CloudifyClientError

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource

pytestmark = pytest.mark.group_workflows


@pytest.mark.usefixtures('cloudmock_plugin')
class TestResumeMgmtworker(AgentlessTestCase):
    @contextmanager
    def _set_retries(self, retries, retry_interval=0):
        original_config = {
            c.name: c.value for c in
            self.get_config(scope='workflow')
        }
        self.client.manager.put_config('task_retries', retries)
        self.client.manager.put_config('subgraph_retries', retries)
        self.client.manager.put_config('task_retry_interval', retry_interval)
        try:
            yield
        finally:
            for name, value in original_config.items():
                self.client.manager.put_config(name, value)

    def _create_deployment(self, client=None):
        dsl_path = resource("dsl/resumable_mgmtworker.yaml")
        return self.deploy(dsl_path, client=None)

    def _start_execution(self, deployment, operation, node_ids=None,
                         client=None):
        parameters = {
            'operation': operation,
            'run_by_dependency_order': True,
            'operation_kwargs': {
            }
        }
        if node_ids:
            parameters['node_ids'] = node_ids
        return self.execute_workflow(
            workflow_name='execute_operation',
            wait_for_execution=False,
            deployment_id=deployment.id,
            parameters=parameters,
            client=client)

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
        service_command = self.get_service_management_command()
        self.execute_on_manager(
            '{0} stop cloudify-mgmtworker'.format(service_command)
        )

    def _unlock_operation(self, operation_name, node_ids=None, client=None):
        """Allow an operation to run.

        Add the operation name to runtime properties - operations (inside
        of cloudmock/tasks.py) check that to see if they're allowed to
        run.
        This is because the tests want to control when does an operation
        run and when does it finish, without relying on sleeping.
        """
        node_ids = node_ids or ['node1', 'node2']
        client = client or self.client
        for node_id in node_ids:
            node_instances = client.node_instances.list(node_id=node_id)
            for node_instance in node_instances:
                while True:
                    # retry in case the operation also updates runtime props
                    properties = node_instance.runtime_properties
                    unlock = properties.setdefault('unlock', [])
                    if operation_name not in unlock:
                        unlock.append(operation_name)
                    try:
                        client.node_instances.update(
                            node_instance.id,
                            runtime_properties=properties,
                            version=node_instance.version)
                    except CloudifyClientError as e:
                        if e.status_code != 409:
                            raise
                        node_instance = client.node_instances.get(
                            node_instance.id)
                    else:
                        break
        # and now wait for the task to finish. It polls every 1 second, so
        # allow a 3 seconds wait.
        time.sleep(3)

    def _start_mgmtworker(self):
        self.logger.info('Starting mgmtworker')
        service_command = self.get_service_management_command()
        self.execute_on_manager(
            '{0} start cloudify-mgmtworker'.format(service_command)
        )

    def test_cancel_updates_operation(self):
        """When a workflow is cancelled, the operations that are actually
        finish are still updated to 'succeeded'."""
        dep = self._create_deployment()
        execution = self._start_execution(
            dep, 'interface1.op_resumable', node_ids=['node1'])
        self.wait_for_event(execution, 'WAITING')
        self.client.executions.cancel(execution.id)
        execution = self.wait_for_execution_to_end(execution)
        self.assertEqual(execution.status, Execution.CANCELLED)

        graphs = self.client.tasks_graphs.list(
            execution.id, name='execute_operation_interface1.op_resumable')
        self.assertEqual(len(graphs), 1)

        # check that the task is started
        task = self._find_remote_operation(graphs[0].id)
        self.assertEqual(task.state, tasks.TASK_STARTED)

        self._unlock_operation('interface1.op_resumable', node_ids=['node1'])

        task = self._find_remote_operation(graphs[0].id)
        self.assertEqual(task.state, tasks.TASK_RESPONSE_SENT)

    def test_resumable_mgmtworker_op(self):
        # start a workflow, stop mgmtworker, restart mgmtworker, check that
        # one operation was resumed and another was other executed
        dep = self._create_deployment()
        instance = self.client.node_instances.list(
            deployment_id=dep.id, node_id='node1')[0]
        instance2 = self.client.node_instances.list(
            deployment_id=dep.id, node_id='node2')[0]
        execution = self._start_execution(dep, 'interface1.op_resumable')
        self.wait_for_event(execution, 'WAITING')

        self.assertFalse(self.client.node_instances.get(instance.id)
                         .runtime_properties['resumed'])
        self.assertNotIn(
            'marked',
            self.client.node_instances.get(instance2.id).runtime_properties)

        self._stop_mgmtworker()
        self._unlock_operation('interface1.op_resumable')
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
        self.wait_for_event(execution, 'WAITING')

        self._stop_mgmtworker()
        self._unlock_operation('interface1.op_nonresumable')
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

        self._unlock_operation('interface1.op_failing')
        self.client.executions.resume(execution.id, force=True)
        execution = self.wait_for_execution_to_end(execution)
        self.assertEqual(execution.status, 'terminated')

        self.assertTrue(self.client.node_instances.get(instance.id)
                        .runtime_properties['resumed'])
        self.assertTrue(self.client.node_instances.get(instance2.id)
                        .runtime_properties['marked'])

    def test_resume_no_duplicates(self):
        self._resume_no_duplicates_test(self.client)

    def _create_user(self, username, password, tenant, role='user'):
        self.client.users.create(username, password, role='default')
        self.client.tenants.add_user(username, tenant, role)

    def test_resume_retried_user(self):
        # like test_resume_cancelled_resumable, but with a non-admin user
        username = 'test-user'
        password = 'test-password'
        self._create_user(username, password, 'default_tenant')
        user_client = self.create_rest_client(
            username=username, password=password, tenant='default_tenant',
        )
        self._resume_no_duplicates_test(user_client)

    def _resume_no_duplicates_test(self, client):
        """Check that retried tasks aren't duplicated after a resume.

        Run a workflow that, for node instance 1, retries the operation
        once and then fails.
        Resume the workflow with reset-operations (force) and check that
        the operation was ran only once after the resume.
        """
        dep = self._create_deployment(client)
        instance = client.node_instances.list(
            deployment_id=dep.id, node_id='node1')[0]
        instance2 = client.node_instances.list(
            deployment_id=dep.id, node_id='node2')[0]
        with self._set_retries(5):
            execution = self._start_execution(
                dep, 'interface1.op_retrying', client=client)

            self.logger.info('Waiting for the execution to fail')
            self.assertRaises(
                RuntimeError, self.wait_for_execution_to_end,
                execution, client=client)

        self.assertNotIn(
            'marked',
            client.node_instances.get(instance2.id).runtime_properties)
        self.assertEqual(client.node_instances.get(instance.id)
                         .runtime_properties['count'], 2)

        client.executions.resume(execution.id, force=True)
        execution = self.wait_for_execution_to_end(execution, client=client)
        self.assertEqual(execution.status, 'terminated')

        # if it is 4, that means the task ran twice after resume
        self.assertEqual(client.node_instances.get(instance.id)
                         .runtime_properties['count'], 3)
        self.assertTrue(client.node_instances.get(instance2.id)
                        .runtime_properties['marked'])

    def test_force_resume_cancelled_nonresumable(self):
        dep = self._create_deployment()
        instance = self.client.node_instances.list(
            deployment_id=dep.id, node_id='node1')[0]
        instance2 = self.client.node_instances.list(
            deployment_id=dep.id, node_id='node2')[0]
        execution = self._start_execution(dep, 'interface1.op_nonresumable')
        self.wait_for_event(execution, 'WAITING')
        self.client.executions.cancel(execution.id)
        self.logger.info('Waiting for the execution to fail')
        execution = self.wait_for_execution_to_end(execution)
        self.assertEqual(execution.status, 'cancelled')

        self._unlock_operation('interface1.op_nonresumable')
        execution = self.client.executions.resume(execution.id, force=True)
        execution = self.wait_for_execution_to_end(execution)
        self.assertEqual(execution.status, 'terminated')

        self.assertTrue(self.client.node_instances.get(instance.id)
                        .runtime_properties['resumed'])
        self.assertTrue(self.client.node_instances.get(instance2.id)
                        .runtime_properties['marked'])

    def test_resume_restart_workflow(self):
        """Test that the restart builtin workflow can be resumed.

        We'll test resuming at both the "stop" stage and the "start" stage.
        If an operation doesn't run when we expect it to, then the
        wait_for_event will timeout - the fact that it doesn't, is essentially
        the assert in this test.
        """
        dep = self._create_deployment()
        execution = self.execute_workflow(
            workflow_name='restart',
            wait_for_execution=False,
            parameters={'node_ids': ['node1']},  # no need for both
            deployment_id=dep.id)

        # wait for the 'stop' operation to begin, and cancel
        self.wait_for_event(execution, 'cloudify.interfaces.lifecycle.stop')
        self.client.executions.cancel(execution.id)
        self.wait_for_execution_to_end(execution)

        # now allow stop to finish, and resume...
        self._unlock_operation('cloudify.interfaces.lifecycle.stop')
        self.client.executions.resume(execution.id)

        # ..,and wait for the start operation to begin, then cancel again
        self.wait_for_event(execution, 'cloudify.interfaces.lifecycle.stop')
        self.client.executions.cancel(execution.id)
        self.wait_for_execution_to_end(execution)

        # resume again and check that the execution finishes
        self._unlock_operation('cloudify.interfaces.lifecycle.start')
        self.client.executions.resume(execution.id)

        execution = self.wait_for_execution_to_end(execution)
        self.assertEqual(execution.status, 'terminated')
