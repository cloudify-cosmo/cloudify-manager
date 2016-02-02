########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

from testenv import TestCase
from testenv.utils import get_resource as resource
from testenv.utils import deploy_application
from testenv.utils import deploy
from testenv.utils import execute_workflow
from testenv.utils import undeploy_application


class TestAgentAliveVerification(TestCase):

    AGENT_ALIVE_FAIL = 'AGENT_ALIVE_FAIL'

    def test_uninstall(self):
        deployment = deploy(resource("dsl/basic_stop_not_exists.yaml"))
        undeploy_application(deployment.id)

    def test_install(self):
        with self.assertRaisesRegexp(RuntimeError, self.AGENT_ALIVE_FAIL):
            deploy_application(resource("dsl/basic_start_not_exists.yaml"))

    def test_not_exist_operation_workflow(self):
        self._test_custom_workflow('not_exist_operation_workflow', True)

    def test_not_exist_operation_graph_mode_workflow(self):
        self._test_custom_workflow(
            'not_exist_operation_graph_mode_workflow', True)

    def test_ignore_handler_on_not_exist_operation_workflow(self):
        self._test_custom_workflow(
            'ignore_handler_on_not_exist_operation_workflow', False)

    def test_retry_handler_on_not_exist_operation_workflow(self):
        self._test_custom_workflow(
            'retry_handler_on_not_exist_operation_workflow', True)

    def test_continue_handler_on_not_exist_operation_workflow(self):
        self._test_custom_workflow(
            'continue_handler_on_not_exist_operation_workflow', False)

    def test_fail_handler_on_not_exist_operation_workflow(self):
        self._test_custom_workflow(
            'fail_handler_on_not_exist_operation_workflow', True)

    def _test_custom_workflow(self, workflow, error_expected=False):
        deployment = deploy(resource("dsl/basic_task_not_exist.yaml"))
        try:
            execute_workflow(workflow, deployment.id)
            if error_expected:
                self.fail('RuntimeError expected')
        except RuntimeError as e:
            if not error_expected:
                self.fail('Success expected. error message: {0}'.format(e))
            self.assertIn(self.AGENT_ALIVE_FAIL, str(e))
