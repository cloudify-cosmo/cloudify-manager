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

from cloudify_rest_client.exceptions import CloudifyClientError

from integration_tests.tests import utils as test_utils
from integration_tests import AgentlessTestCase

TEST_PACKAGE_NAME = 'cloudify-script-plugin'
TEST_PACKAGE_VERSION = '1.2'


class TestPlugins(AgentlessTestCase):

    def test_get_plugin_by_id(self):
        put_plugin_response = test_utils.upload_mock_plugin(
                TEST_PACKAGE_NAME,
                TEST_PACKAGE_VERSION)
        plugin_id = put_plugin_response.get('id')
        self.assertIsNotNone(plugin_id)
        self.assertEquals(put_plugin_response.get('package_name'),
                          TEST_PACKAGE_NAME)
        self.assertEquals(put_plugin_response.get('package_version'),
                          TEST_PACKAGE_VERSION)
        get_plugin_by_id_response = self.client.plugins.get(plugin_id)

        self.assertEquals(put_plugin_response, get_plugin_by_id_response)

    def test_get_plugin_not_found(self):
        try:
            self.client.plugins.get('DUMMY_PLUGIN_ID')
        except CloudifyClientError as e:
            self.assertEquals(
                u'Requested `Plugin` with ID `DUMMY_PLUGIN_ID` was not found',
                e.message
            )
            self.assertEquals(404, e.status_code)

    def test_delete_plugin(self):
        put_response = test_utils.upload_mock_plugin(
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
        try:
            self.client.plugins.delete('DUMMY_PLUGIN_ID')
        except CloudifyClientError as e:
            self.assertEquals(
                u'Requested `Plugin` with ID `DUMMY_PLUGIN_ID` was not found',
                e.message
            )
            self.assertEquals(404, e.status_code)

    def _get_execution(self, workflow_id):
        executions = self.client.executions.list(include_system_workflows=True)
        ex_list = [e for e in executions if e.workflow_id == workflow_id]
        self.assertEqual(len(ex_list), 1,
                         msg='Expected to find 1 execution with workflow_id '
                             '`{workflow_id}`, but found: '
                             '{ex_list}'.format(
                             workflow_id=workflow_id, ex_list=ex_list)
                         )
        return ex_list[0]

    def test_install_uninstall_workflows_execution(self):
        test_utils.upload_mock_plugin(TEST_PACKAGE_NAME, TEST_PACKAGE_VERSION)

        ex = self._get_execution('install_plugin')
        self.wait_for_execution_to_end(ex)

        plugin = self.client.plugins.list()[0]
        self.client.plugins.delete(plugin.id)

        ex = self._get_execution('uninstall_plugin')
        self.wait_for_execution_to_end(ex)

        plugins = self.client.plugins.list()
        self.assertEqual(len(plugins), 0)
