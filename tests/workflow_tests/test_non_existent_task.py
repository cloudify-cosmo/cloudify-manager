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
from testenv.utils import deploy_application as deploy
from testenv.utils import execute_workflow
from testenv.utils import undeploy_application as undeploy


from testenv.utils import logger


class TestUninstallWorkflow(TestCase):

    def test_uninstall(self):
        dsl_path = resource("dsl/basic_stop_not_exists.yaml")
        deployment, _ = deploy(dsl_path)
        undeploy(deployment.id)
        logger.info('Successfully executed undeploy')


class TestInstallWorkflow(TestCase):

    def test_install(self):
        dsl_path = resource("dsl/basic_start_not_exists.yaml")
        try:
            deployment, _ = deploy(dsl_path)
            self.fail('RuntimeError expected')
        except RuntimeError as e:
            logger.info('Deploy failed as expected')
            self.assertIn("RuntimeError: Workflow failed: "
                          "Task failed 'cloudmock.tasks.non_existent' "
                          "-> non_existent operation "
                          "[cloudmock.tasks.non_existent]",
                          e.message)


class TestCustomWorkflow(TestCase):

    def _test_custom_workflow(self, workflow, error_expected=False):
        dsl_path = resource("dsl/basic_task_not_exist.yaml")
        deployment, _ = deploy(dsl_path)
        expected_error_message = 'non_existent operation [{0}]'\
            .format('cloudmock.tasks.non_existent')
        try:
            execute_workflow(workflow, deployment.id)
            logger.info('Successfully executed workflow [{0}]'
                        .format(workflow))
            if error_expected:
                self.fail('RuntimeError expected')
        except RuntimeError as e:
            logger.info('Failed to execute workflow [{0}]'.format(workflow))
            actual_message = str(e.message)
            if not error_expected:
                self.fail('Success expected. error message: {0}'
                          .format(e.message))
            self.assertIn(expected_error_message, actual_message,
                          'expected error message: {0}, '
                          'actual error message: {1}'
                          .format(expected_error_message, actual_message))

    def test_not_exist_operation_workflow(self):
        self._test_custom_workflow('not_exist_operation_workflow', True)

    def test_not_exist_operation_graph_mode_workflow(self):
        self._test_custom_workflow(
            'not_exist_operation_graph_mode_workflow', True)

    def test_not_exist_stop_operation_workflow(self):
        self._test_custom_workflow('not_exist_stop_operation_workflow', True)

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
