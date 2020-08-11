#########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

import time
import pytest
from cloudify.plugins.install_utils import INSTALLING_PREFIX
from cloudify.models_states import PluginInstallationState

from cloudify_rest_client.exceptions import CloudifyClientError

from integration_tests import AgentlessTestCase
from integration_tests.tests import utils as test_utils

TEST_PACKAGE_NAME = 'cloudify-aria-plugin'
TEST_PACKAGE_VERSION = '1.1'
TEST_PACKAGE2_NAME = 'cloudify-diamond-plugin'
TEST_PACKAGE2_VERSION = '1.3'


class TestPlugins(AgentlessTestCase):

    def test_get_plugin_by_id(self):
        plugin_id = None
        try:
            put_plugin_response = test_utils.upload_mock_plugin(
                    self.client,
                    TEST_PACKAGE_NAME,
                    TEST_PACKAGE_VERSION
            )
            plugin_id = put_plugin_response.get('id')
            get_plugin_by_id_response = self.client.plugins.get(plugin_id)
            self.assertEquals(put_plugin_response, get_plugin_by_id_response)
        finally:
            if plugin_id:
                self.client.plugins.delete(plugin_id)

    def test_get_plugin_not_found(self):
        with pytest.raises(
                CloudifyClientError,
                match='Requested `Plugin` with ID `DUMMY_PLUGIN_ID` '
                'was not found') as e:
            self.client.plugins.get('DUMMY_PLUGIN_ID')
        assert e.value.status_code == 404

    def test_delete_plugin(self):
        put_response = test_utils.upload_mock_plugin(
                self.client,
                TEST_PACKAGE_NAME,
                TEST_PACKAGE_VERSION)

        plugins_list = self.client.plugins.list()
        self.assertEqual(1, len(plugins_list),
                         'expecting 1 plugin result, '
                         'got {0}'.format(len(plugins_list)))

        delete_response = self.client.plugins.delete(put_response['id'])
        # in delete response, yaml_url_path should be empty
        put_response['yaml_url_path'] = ''
        self.assertEquals(put_response, delete_response)

        plugins_list = self.client.plugins.list()
        self.assertEqual(0, len(plugins_list),
                         'expecting 0 plugin result, '
                         'got {0}'.format(len(plugins_list)))

    def test_delete_plugin_not_found(self):
        with pytest.raises(
                CloudifyClientError,
                match='Requested `Plugin` with ID `DUMMY_PLUGIN_ID` '
                'was not found') as e:
            self.client.plugins.delete('DUMMY_PLUGIN_ID')
        assert e.value.status_code == 404

    def test_install_uninstall_workflows_execution(self):
        test_utils.upload_mock_plugin(self.client,
                                      TEST_PACKAGE_NAME,
                                      TEST_PACKAGE_VERSION)

        plugin = self.client.plugins.list()[0]
        self.client.plugins.delete(plugin.id)
        plugins = self.client.plugins.list()
        self.assertEqual(len(plugins), 0)

    @pytest.mark.usefixtures('cloudmock_plugin')
    def test_plugin_installation_state(self):
        plugins = self.client.plugins.list(package_name='cloudmock')
        states = self.client.plugins.get(plugins[0].id).installation_state
        assert states == []
        self.client.plugins.install(
            plugins[0].id,
            managers=[m.hostname for m in self.client.manager.get_managers()])
        deadline = time.time() + 30
        while time.time() < deadline:
            states = self.client.plugins.get(plugins[0].id).installation_state
            if not states:
                continue
            state = states[0]['state']
            if state == PluginInstallationState.INSTALLED:
                break
            time.sleep(0.5)
        assert state == PluginInstallationState.INSTALLED


class TestPluginsSystemState(AgentlessTestCase):
    def test_installing_corrupted_plugin_doesnt_affect_system_integrity(self):
        self._upload_plugin_and_assert_values(TEST_PACKAGE_NAME,
                                              TEST_PACKAGE_VERSION,
                                              plugins_count=0,
                                              wagon_files_count=1,
                                              corrupt_plugin=True)
        plugin = self._upload_plugin_and_assert_values(TEST_PACKAGE_NAME,
                                                       TEST_PACKAGE_VERSION,
                                                       plugins_count=1,
                                                       wagon_files_count=3)
        plugin2 = self._upload_plugin_and_assert_values(TEST_PACKAGE2_NAME,
                                                        TEST_PACKAGE2_VERSION,
                                                        plugins_count=2,
                                                        wagon_files_count=2)
        self._uninstall_plugin_and_assert_values(plugin, 1)
        self._uninstall_plugin_and_assert_values(plugin2, 0)

    def _upload_plugin_and_assert_values(self,
                                         package_name,
                                         package_version,
                                         plugins_count,
                                         wagon_files_count,
                                         corrupt_plugin=False):
        plugin = test_utils.upload_mock_plugin(
            self.client,
            package_name,
            package_version,
            corrupt_plugin=corrupt_plugin)
        wagon_file = plugin.archive_name[len(INSTALLING_PREFIX):]

        execution = self._get_latest_execution('install_plugin')
        if corrupt_plugin:
            with self.assertRaisesRegexp(
                    RuntimeError, 'Workflow execution failed: .*'):
                self.wait_for_execution_to_end(execution)
            execution = self._get_latest_execution('uninstall_plugin')
        self.wait_for_execution_to_end(execution)

        find_output = self._find_file_on_manager(wagon_file)
        self.assertEqual(len(find_output), wagon_files_count)
        plugins = self.client.plugins.list()
        self.assertEqual(len(plugins), plugins_count)
        return plugin

    def _find_file_on_manager(self, wagon_file):
        find_output = self.execute_on_manager(
            "find / -name '{0}'".format(wagon_file)).stdout.split('\n')
        if find_output and not find_output[-1]:
            find_output.pop()
        return find_output

    def _uninstall_plugin_and_assert_values(self, plugin, plugins_count):
        self.client.plugins.delete(plugin.id)
        execution = self._get_latest_execution('uninstall_plugin')
        self.wait_for_execution_to_end(execution)
        plugins = self.client.plugins.list()
        self.assertEqual(len(plugins), plugins_count)
        self.assertNotIn(plugin.id, plugins)
