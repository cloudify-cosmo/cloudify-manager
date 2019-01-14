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
from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource


class TestResumeMgmtworker(AgentlessTestCase):
    wait_message = 'WAITING FOR FILE'
    target_file = '/tmp/continue_test'

    def _create_deployment(self):
        dsl_path = resource("dsl/resumable_mgmtworker.yaml")
        return self.deploy(dsl_path)

    def _start_execution(self, deployment, operation):
        return self.execute_workflow(
            workflow_name='execute_operation',
            wait_for_execution=False,
            deployment_id=deployment.id,
            parameters={'operation': operation,
                        'run_by_dependency_order': True,
                        'operation_kwargs': {
                            'wait_message': self.wait_message,
                            'target_file': self.target_file
                        }})

    def _wait_for_log(self, execution):
        self.logger.info('Waiting for operation to start')
        while True:
            logs = self.client.events.list(
                execution_id=execution.id, include_logs=True)
            if any(self.wait_message == log['message'] for log in logs):
                break
            time.sleep(1)

    def _restart_mgmtworker(self):
        self.logger.info('Stopping mgmtworker')
        self.execute_on_manager('systemctl stop cloudify-mgmtworker')

        self.logger.info('Restarting mgmtworker')
        self.execute_on_manager('touch {0}'.format(self.target_file))
        self.addCleanup(self.execute_on_manager,
                        'rm -rf {0}'.format(self.target_file))
        self.execute_on_manager('systemctl start cloudify-mgmtworker')

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

        self._restart_mgmtworker()
        self.logger.info('Waiting for the execution to finish')
        while True:
            new_exec = self.client.executions.get(execution.id)
            if new_exec.status == 'started':
                time.sleep(1)
                continue
            self.assertEqual(new_exec.status, 'terminated')
            break
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

        self._restart_mgmtworker()
        self.logger.info('Waiting for the execution to fail')
        while True:
            new_exec = self.client.executions.get(execution.id)
            if new_exec.status == 'started':
                time.sleep(1)
                continue
            self.assertEqual(new_exec.status, 'failed')
            break
        self.assertFalse(self.client.node_instances.get(instance.id)
                         .runtime_properties['resumed'])
        self.assertNotIn(
            'marked',
            self.client.node_instances.get(instance2.id).runtime_properties)
