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

import uuid
import time
from integration_tests import AgentTestCase
from integration_tests.tests.utils import get_resource as resource


class TestResumeMgmtworker(AgentTestCase):
    wait_message = 'hello1'

    def _start_execution(self, deployment, operation):
        return self.execute_workflow(
            workflow_name='execute_operation',
            wait_for_execution=False,
            deployment_id=deployment.id,
            parameters={'operation': operation,
                        'run_by_dependency_order': True,
                        'operation_kwargs': {
                            'wait_message': self.wait_message
                        }})

    def _wait_for_log(self, execution, wait_message=None):
        if wait_message is None:
            wait_message = self.wait_message
        while True:
            logs = self.client.events.list(
                execution_id=execution.id, include_logs=True)
            if any(self.wait_message == log['message'] for log in logs):
                break
            time.sleep(1)

    def _stop_mgmtworker(self):
        self.logger.info('Stopping mgmtworker')
        self.execute_on_manager('systemctl stop cloudify-mgmtworker')

    def _start_mgmtworker(self):
        self.logger.info('Restarting mgmtworker')
        self.execute_on_manager('systemctl start cloudify-mgmtworker')

    def test_resume_agent_op(self):
        # start a workflow
        deployment_id = 'd{0}'.format(uuid.uuid4())
        dsl_path = resource('dsl/resumable_agent.yaml')
        deployment, execution_id = self.deploy_application(
            dsl_path, deployment_id=deployment_id)
        execution = self._start_execution(deployment, 'interface1.op1')

        # wait until the agent starts executing operations
        self._wait_for_log(execution)
        instance = self.client.node_instances.list(
            node_id='agent_host', deployment_id=deployment.id)[0]
        self.assertFalse(instance.runtime_properties['resumed'])

        # restart mgmtworker
        self._stop_mgmtworker()
        self._start_mgmtworker()

        # check that we resume waiting for the agent operation
        self._wait_for_log(execution, self.wait_message[::-1])
        self.wait_for_execution_to_end(execution)
        instance = self.client.node_instances.get(instance.id)[0]
        self.assertTrue(instance.runtime_properties['resumed'])
