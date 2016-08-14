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

from testenv import utils
from testenv import TestCase

TEST_PACKAGE_NAME = 'cloudify-script-plugin'
TEST_PACKAGE_VERSION = '1.2'


class TestPlugins(TestCase):

    def test_get_plugin_by_id(self):
        put_plugin_response = utils.upload_plugin(TEST_PACKAGE_NAME,
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
                u'Requested Plugin with ID `DUMMY_PLUGIN_ID` was not found',
                e.message
            )
            self.assertEquals(404, e.status_code)

    def test_delete_plugin(self):
        put_response = utils.upload_plugin(TEST_PACKAGE_NAME,
                                           TEST_PACKAGE_VERSION)

        plugins_list = self.client.plugins.list()
        self.assertEqual(1, len(plugins_list),
                         'expecting 1 plugin result, '
                         'got {0}'.format(len(plugins_list)))

        delete_response = self.client.plugins.delete(put_response['id'])
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
                u'Requested Plugin with ID `DUMMY_PLUGIN_ID` was not found',
                e.message
            )
            self.assertEquals(404, e.status_code)

    def test_install_uninstall_workflows_execution(self):
        self.clear_plugin_data('agent')
        utils.upload_plugin(TEST_PACKAGE_NAME, TEST_PACKAGE_VERSION)
        plugins = self.get_plugin_data('agent',
                                       deployment_id='system')['local']
        self.assertEqual(plugins[TEST_PACKAGE_NAME], ['installed'])
        plugin = self.client.plugins.list()[0]
        self.client.plugins.delete(plugin.id)
        plugins = self.get_plugin_data('agent',
                                       deployment_id='system')['local']
        self.assertEqual(plugins[TEST_PACKAGE_NAME], ['installed',
                                                      'uninstalled'])
