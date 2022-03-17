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

import pytest

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource

pytestmark = pytest.mark.group_agents


@pytest.mark.usefixtures('mock_workflows_plugin')
@pytest.mark.usefixtures('cloudmock_plugin')
class TestAgentAliveVerification(AgentlessTestCase):

    def test_uninstall(self):
        deployment = self.deploy(resource("dsl/basic_stop_not_exists.yaml"))
        self.undeploy_application(deployment.id,
                                  parameters={
                                      'ignore_failure': True
                                  })

    def test_install(self):
        with self.assertRaisesRegex(RuntimeError,
                                    "Workflow execution failed:"):
            self.deploy_application(
                    resource("dsl/basic_start_not_exists.yaml"))

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
        deployment = self.deploy(resource("dsl/basic_task_not_exist.yaml"))
        try:
            self.execute_workflow(workflow, deployment.id)
            if error_expected:
                self.fail('RuntimeError expected')
        except RuntimeError as e:
            if not error_expected:
                self.fail('Success expected. error message: {0}'.format(e))
            self.assertIn("Workflow execution failed:", str(e))
