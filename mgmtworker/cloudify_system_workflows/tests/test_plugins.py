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
from unittest.mock import patch, MagicMock, PropertyMock, call

from cloudify.models_states import ExecutionState

from cloudify_system_workflows.plugins import (update as update_func,
                                               install as install_func,
                                               uninstall as uninstall_func)


class TestPlugins(unittest.TestCase):
    def setUp(self):
        operate_on_plugin_patcher = patch(
            'cloudify_system_workflows.plugins._operate_on_plugin')
        self.mock_operate_on_plugin = operate_on_plugin_patcher.start()
        self.mock_operate_on_plugin.side_effect = lambda *_: _
        self.addCleanup(operate_on_plugin_patcher.stop)
        rest_client_patcher = patch(
            'cloudify_system_workflows.plugins.get_rest_client')
        self.mock_rest_client = MagicMock()
        rest_client_patcher.start().return_value = self.mock_rest_client
        self.addCleanup(rest_client_patcher.stop)

    def test_uninstall_returns_execution_result(self):
        return_value = list(uninstall_func(None, {}, ignores_this=None))
        desired_call_args = [None, {}, 'uninstall']
        self.mock_operate_on_plugin.assert_called_once_with(*desired_call_args)
        self.assertListEqual(desired_call_args, return_value)

    def test_install_returns_execution_result(self):
        return_value = list(install_func(None, {}, ignores_this=None))
        desired_call_args = [None, {}, 'install']
        self.mock_operate_on_plugin.assert_called_once_with(*desired_call_args)
        self.assertListEqual(desired_call_args, return_value)

    def test_install_deletes_plugin_upon_failure(self):
        class _Exception(Exception):
            pass

        def raise_custom_exception(*_):
            raise _Exception()

        plugin = {'id': 'some_id'}
        self.mock_operate_on_plugin.side_effect = raise_custom_exception
        mock_ctx = MagicMock()
        with self.assertRaises(_Exception):
            install_func(mock_ctx, plugin, ignores_this=None)
        desired_operate_on_call_args = [mock_ctx, plugin, 'install']
        self.mock_operate_on_plugin.assert_called_once_with(
            *desired_operate_on_call_args)
        self.mock_rest_client.plugins.delete.assert_called_once_with(
            plugin_id=plugin['id'], force=True)


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

    @patch('cloudify_system_workflows.plugins.get_tenant_name')
    def test_plugins_update_continues_when_one_deployment_update_fails(
            self, get_tenant_name_fn):
        def get_execution_mock(execution_id):
            """
            :return: a mock of an execution object where its status is
            TERMINATED if the execution shouldn't fail, and FAILED/CANCELLED
            if it should.
            """
            if execution_id == failed_execution_id:
                return PropertyMock(
                    status=execution_status['curr_exec_status'])
            return PropertyMock(status=ExecutionState.TERMINATED)

        def _assert_update_func():
            update_func(MagicMock(),
                        'my_update_id', None, dep_ids, {}, False, False, True)
            should_call_these = [call(deployment_id=i,
                                      blueprint_id=None,
                                      skip_install=True,
                                      skip_uninstall=True,
                                      skip_reinstall=True,
                                      force=False,
                                      auto_correct_types=False,
                                      reevaluate_active_statuses=True)
                                 for i in dep_ids]
            self.deployment_update_mock.assert_has_calls(should_call_these)

        get_tenant_name_fn.return_value = 'default_tenant'
        execution_status = {'curr_exec_status': ExecutionState.FAILED}

        dep_ids = list(range(5))
        failed_execution_id = 3
        self.mock_rest_client.executions.get \
            .side_effect = get_execution_mock

        _assert_update_func()
        execution_status['curr_exec_status'] = ExecutionState.CANCELLED
        _assert_update_func()

    @patch('cloudify_system_workflows.plugins.get_tenant_name')
    def test_doesnt_stop_updating(self, get_tenant_name_fn):
        get_tenant_name_fn.return_value = 'default_tenant'
        finalize_update_mock = MagicMock()
        dep_ids = list(range(5))
        self.mock_rest_client.plugins_update.finalize_plugins_update \
            = finalize_update_mock
        self.mock_rest_client.executions.get \
            .return_value = PropertyMock(status=ExecutionState.TERMINATED)
        update_func(MagicMock(),
                    '12345678', None, dep_ids, {}, False, False, False)
        should_call_these = [call(deployment_id=i,
                                  blueprint_id=None,
                                  skip_install=True,
                                  skip_uninstall=True,
                                  skip_reinstall=True,
                                  force=False,
                                  auto_correct_types=False,
                                  reevaluate_active_statuses=False)
                             for i in range(len(dep_ids))]
        self.deployment_update_mock.assert_has_calls(should_call_these)
        finalize_update_mock.assert_called_with('12345678')
