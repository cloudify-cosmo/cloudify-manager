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

import pytest
import retrying
import yaml

from cloudify.models_states import PluginInstallationState

from cloudify_rest_client.exceptions import CloudifyClientError

from integration_tests import AgentlessTestCase
from integration_tests.framework import docker as docker_utils
from integration_tests.tests import utils as test_utils

pytestmark = pytest.mark.group_plugins

TEST_PACKAGE_NAME = 'cloudify-aria-plugin'
TEST_PACKAGE_VERSION = '1.1'
TEST_PACKAGE2_NAME = 'cloudify-diamond-plugin'
TEST_PACKAGE2_VERSION = '1.3'


@retrying.retry(
    wait_fixed=500,
    # plugins should install fairly quickly, on the order of seconds.
    # Let's wait for up to a minute.
    stop_max_delay=60000,
)
def _fetch_plugin(client, plugin_id):
    """Wait until the plugin has finished installing, and return it.

    This waits until the plugin installation state resolves, to either
    an successful, or an error state.
    """
    plugin_retrieved = client.plugins.get(plugin_id)
    # installation_state is a list of dicts that have at least the
    # 'state' key, and 'manager' or 'agent' keys
    assert 'installation_state' in plugin_retrieved
    installation_state = plugin_retrieved['installation_state']
    if any(
        state_spec['state'] in {
            PluginInstallationState.PENDING,
            PluginInstallationState.INSTALLING,
            PluginInstallationState.PENDING_UNINSTALL,
            PluginInstallationState.UNINSTALLING,
        } for state_spec in installation_state
    ):
        raise RuntimeError(f'Plugin still pending: {installation_state}')
    return plugin_retrieved


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
            self.assertEqual(put_plugin_response, get_plugin_by_id_response)
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

        self.client.plugins.delete(put_response['id'])
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

        plugin_retrieved = _fetch_plugin(self.client, plugins[0].id)
        state = plugin_retrieved.installation_state[0]['state']
        assert state == PluginInstallationState.INSTALLED

    @pytest.mark.usefixtures('dsl_backcompat_plugin')
    def test_plugin_backward_compatibility_generation(self):
        bp13_path = test_utils.get_resource('dsl/dsl_versions_test_1_3.yaml')
        bp14_path = test_utils.get_resource('dsl/dsl_versions_test_1_4.yaml')
        self.client.blueprints.upload(bp13_path, 'bp13')
        test_utils.wait_for_blueprint_upload('bp13', self.client)
        self.client.blueprints.upload(bp14_path, 'bp14')
        test_utils.wait_for_blueprint_upload('bp14', self.client)

    @pytest.mark.usefixtures('with_properties_plugin')
    def test_plugin_with_properties(self):
        bp_path = test_utils.get_resource('dsl/plugin_properties.yaml')
        self.client.blueprints.upload(bp_path, 'bp')
        test_utils.wait_for_blueprint_upload('bp', self.client)
        self.client.deployments.create('bp', 'd1')
        test_utils.wait_for_deployment_creation_to_complete(
            self.env.container_id, 'd1', self.client)
        execution = self.client.executions.start(deployment_id='d1',
                                                 workflow_id='install')
        self.wait_for_execution_to_end(execution)
        output_file_name = f'/tmp/execution-{execution.id}-test_node.yaml'
        output_text = docker_utils.read_file(self.env.container_id,
                                             output_file_name)
        properties_used = yaml.safe_load(output_text)
        assert properties_used == {
            'string_property': 'foo',
            'list_property': [1, 2, 3],
        }

    @pytest.mark.usefixtures('with_properties_plugin')
    def test_plugin_with_properties_namespaced(self):
        bp_path = test_utils.get_resource(
            'dsl/plugin_properties_namespaced.yaml')
        self.client.blueprints.upload(bp_path, 'bp')
        test_utils.wait_for_blueprint_upload('bp', self.client)
        self.client.deployments.create('bp', 'd2')
        test_utils.wait_for_deployment_creation_to_complete(
            self.env.container_id, 'd2', self.client)
        execution = self.client.executions.start(deployment_id='d2',
                                                 workflow_id='install')
        self.wait_for_execution_to_end(execution)
        output_file_name_ns1 = f'/tmp/execution-{execution.id}-node_ns1.yaml'
        output_text_ns1 = docker_utils.read_file(self.env.container_id,
                                                 output_file_name_ns1)
        output_file_name_ns2 = f'/tmp/execution-{execution.id}-node_ns2.yaml'
        output_text_ns2 = docker_utils.read_file(self.env.container_id,
                                                 output_file_name_ns2)
        properties_used_ns1 = yaml.safe_load(output_text_ns1)
        assert properties_used_ns1 == {
            'ns1--string_property': 'foo',
            'ns1--list_property': [1, 2, 3],
        }
        properties_used_ns2 = yaml.safe_load(output_text_ns2)
        assert properties_used_ns2 == {
            'ns2--string_property': 'bar',
            'ns2--list_property': [9, 8, 7],
        }


class TestPluginsSystemState(AgentlessTestCase):
    def test_installing_corrupted_plugin_doesnt_affect_system_integrity(self):
        self._upload_plugin_and_assert_values(TEST_PACKAGE_NAME,
                                              TEST_PACKAGE_VERSION,
                                              plugins_count=0,
                                              corrupt_plugin=True)
        plugin = self._upload_plugin_and_assert_values(TEST_PACKAGE_NAME,
                                                       TEST_PACKAGE_VERSION,
                                                       plugins_count=1)
        plugin2 = self._upload_plugin_and_assert_values(TEST_PACKAGE2_NAME,
                                                        TEST_PACKAGE2_VERSION,
                                                        plugins_count=2)
        self._uninstall_plugin_and_assert_values(plugin, 1)
        self._uninstall_plugin_and_assert_values(plugin2, 0)

    def _upload_plugin_and_assert_values(self,
                                         package_name,
                                         package_version,
                                         plugins_count,
                                         corrupt_plugin=False):
        plugin = test_utils.upload_mock_plugin(
            self.client,
            package_name,
            package_version,
            corrupt_plugin=corrupt_plugin)

        self.client.plugins.install(
            plugin.id,
            managers=[m.hostname for m in self.client.manager.get_managers()])

        plugin_retrieved = _fetch_plugin(self.client, plugin.id)

        if corrupt_plugin:
            log_path = '/var/log/cloudify/mgmtworker/mgmtworker.log'
            tmp_log_path = str(self.workdir / 'test_log')
            self.copy_file_from_manager(log_path, tmp_log_path)
            with open(tmp_log_path) as f:
                data = f.readlines()
            last_log_lines = str(data[-20:])
            message = 'Failed installing managed plugin: {0}'.format(plugin.id)
            assert message in last_log_lines

            expected_state = 'error'
        else:
            expected_state = 'installed'

        for s in plugin_retrieved['installation_state']:
            assert s['state'] == expected_state, (
                f'expected all state entries to be `{expected_state}`; '
                f'plugin was: {plugin_retrieved}'
            )

        if corrupt_plugin:
            self.client.plugins.delete(plugin.id)

        plugins = self.client.plugins.list()
        assert len(plugins) == plugins_count
        return plugin

    def _uninstall_plugin_and_assert_values(self, plugin, plugins_count):
        self.client.plugins.delete(plugin.id)
        plugins = self.client.plugins.list()
        assert len(plugins) == plugins_count
        assert plugin.id not in plugins
