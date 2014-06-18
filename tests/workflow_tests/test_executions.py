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


from testenv import (TestCase,
                     get_resource as resource,
                     deploy_application as deploy)


class ExecutionsTest(TestCase):

    def test_cancel_execution(self):
        dsl_path = resource("dsl/sleep_workflow.yaml")
        _, execution_id = deploy(dsl_path,
                                 wait_for_execution=False)
        execution = self.client.executions.cancel(execution_id)
        wait_for_execution_to_end(execution)
        self.assertEquals('terminated', execution.status)

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
            self.assertEquals('terminated', install_execution.status)
            self.assertEquals('', install_execution.error)

        self.do_assertions(assertions, timeout=10)

    def test_update_execution_status(self):
        dsl_path = resource("dsl/basic.yaml")
        _, execution_id = deploy(dsl_path,
                                 wait_for_execution=True)
        execution = self.client.executions.get(execution_id)
        self.assertEquals('terminated', execution.status)
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
