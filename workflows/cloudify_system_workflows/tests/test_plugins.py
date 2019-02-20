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

import unittest

from mock import patch, MagicMock, PropertyMock, call

from cloudify.models_states import ExecutionState

from cloudify_system_workflows.plugins import update as update_func


class TestPluginsUpdate(unittest.TestCase):
    def setUp(self):
        wait_for_patcher = patch('cloudify_system_workflows.plugins.wait_for')
        wait_for_patcher.start()
        self.addCleanup(wait_for_patcher.stop)

        get_rest_client_patcher = patch('cloudify_system_workflows.plugins'
                                        '.get_rest_client')
        get_rest_client_mock = get_rest_client_patcher.start()
        self.addCleanup(get_rest_client_patcher.stop)

        self.mock_rest_client = MagicMock()
        get_rest_client_mock.return_value = self.mock_rest_client
        self.deployment_update_mock = MagicMock(
            side_effect=self._update_with_existing_blueprint_mock)
        self.mock_rest_client.deployment_updates \
            .update_with_existing_blueprint \
            .side_effect = self.deployment_update_mock

    @staticmethod
    def _update_with_existing_blueprint_mock(deployment_id, *_, **__):
        return PropertyMock(execution_id=deployment_id)

    def test_stops_updating_when_one_update_fails(self):
        def returns_failed_execution_only_if_is_stop_at(execution_id):
            if execution_id == fail_at_id:
                return PropertyMock(status=test_params['curr_exec_status'])
            return PropertyMock(status=ExecutionState.TERMINATED)

        def _assert_update_func_raises():
            with self.assertRaisesRegexp(
                    RuntimeError,
                    "Deployment update of deployment {0} with execution ID {0}"
                    " failed, stopped this plugins update "
                    "\\(id='my_update_id'\\)\\.".format(fail_at_id)):
                update_func(MagicMock(), 'my_update_id', None, dep_ids)
            should_call_these = [call(deployment_id=i,
                                      blueprint_id=None,
                                      skip_install=True,
                                      skip_uninstall=True,
                                      skip_reinstall=True)
                                 for i in range(fail_at_id)]
            self.deployment_update_mock.assert_has_calls(should_call_these)

            should_not_call_these = [call(deployment_id=i,
                                          blueprint_id=None,
                                          skip_install=True,
                                          skip_uninstall=True,
                                          skip_reinstall=True)
                                     for i in range(
                    fail_at_id + 1, len(dep_ids))]
            for _call in self.deployment_update_mock.mock_calls:
                self.assertNotIn(_call, should_not_call_these)

        test_params = {'curr_exec_status': ExecutionState.FAILED}

        dep_ids = list(range(5))
        fail_at_id = 3
        self.mock_rest_client.executions.get \
            .side_effect = returns_failed_execution_only_if_is_stop_at

        _assert_update_func_raises()
        test_params['curr_exec_status'] = ExecutionState.CANCELLED
        _assert_update_func_raises()

    def test_doesnt_stop_updating(self):
        finalize_update_mock = MagicMock()
        dep_ids = list(range(5))
        self.mock_rest_client.plugins_update.finalize_plugins_update \
            = finalize_update_mock
        self.mock_rest_client.executions.get \
            .return_value = PropertyMock(status=ExecutionState.TERMINATED)
        update_func(MagicMock(), '12345678', None, dep_ids)
        should_call_these = [call(deployment_id=i,
                                  blueprint_id=None,
                                  skip_install=True,
                                  skip_uninstall=True,
                                  skip_reinstall=True)
                             for i in range(len(dep_ids))]
        self.deployment_update_mock.assert_has_calls(should_call_these)
        finalize_update_mock.assert_called_with('12345678')
