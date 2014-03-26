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

from workflow_tests.testenv import (TestCase,
                                    get_resource as resource,
                                    deploy_application as deploy,
                                    get_execution,
                                    cancel_execution,
                                    execute_install,
                                    get_deployment_executions)


class BasicWorkflowsTest(TestCase):

    def test_cancel_execution(self):
        dsl_path = resource("dsl/sleep_workflow.yaml")
        _, execution_id = deploy(dsl_path,
                                 wait_for_execution=False)
        cancel_execution(execution_id)
        execution = get_execution(execution_id)
        endtime = time.time() + 10
        while execution.status not in ['terminated', 'failed'] and \
                time.time() < endtime:
            execution = get_execution(execution_id)
            time.sleep(1)

        self.assertEquals(execution.status, 'terminated')

    def test_get_deployments_executions_with_status(self):
        dsl_path = resource("dsl/basic.yaml")
        deployment, execution_id = deploy(dsl_path)
        deployments_executions = get_deployment_executions(deployment.id,
                                                           True)

        self.assertEquals(1, len(deployments_executions))
        self.assertEquals(execution_id, deployments_executions[0].id)
        self.assertEquals('terminated', deployments_executions[0].status)
        self.assertEquals('None', deployments_executions[0].error)

    def test_execute_more_than_one_workflow_fails(self):
        dsl_path = resource("dsl/sleep_workflow.yaml")
        deployment, execution_id = deploy(dsl_path,
                                          wait_for_execution=False)
        try:
            execute_install(deployment.id,
                            force=False,
                            wait_for_execution=False)
            self.fail('Expected error')
        except Exception, e:
            print e
            pass

    def test_execute_more_than_one_workflow_succeeds_with_force(self):
        self.fail()