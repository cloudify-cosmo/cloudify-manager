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
from nose.plugins.attrib import attr

from manager_rest.test import base_test
from base_test import BaseServerTestCase

from cloudify_rest_client.exceptions import CloudifyClientError

TEST_PACKAGE_NAME = 'cloudify-script-plugin'
TEST_PACKAGE_VERSION = '1.2'
OLD_TEST_PACKAGE_VERSION = '1.1'


@attr(client_min_version=2, client_max_version=base_test.LATEST_API_VERSION)
class PluginsTest(BaseServerTestCase):
    """
    Test plugins upload and download.
    """
    def test_get_plugin_by_id(self):
        put_plugin_response = self.upload_plugin(TEST_PACKAGE_NAME,
                                                 TEST_PACKAGE_VERSION).json
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
            self.assertEquals(404, e.status_code)

    def test_delete_plugin(self):
        put_response = self.upload_plugin(TEST_PACKAGE_NAME,
                                          TEST_PACKAGE_VERSION).json

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
            self.assertEquals(404, e.status_code)

    def test_put_same_plugin_module_twice_response_status(self):
        ok_response = self.upload_plugin(TEST_PACKAGE_NAME,
                                         TEST_PACKAGE_VERSION)
        self.assertEquals('201 CREATED', ok_response._status)
        error_response = self.upload_plugin(TEST_PACKAGE_NAME,
                                            TEST_PACKAGE_VERSION)
        self.assertEquals('409 CONFLICT', error_response._status)

    def test_post_plugin_package_different_versions(self):
        response_a = self.upload_plugin(TEST_PACKAGE_NAME,
                                        TEST_PACKAGE_VERSION)
        self.assertEquals('201 CREATED', response_a._status)
        response_b = self.upload_plugin(TEST_PACKAGE_NAME,
                                        OLD_TEST_PACKAGE_VERSION)
        self.assertEquals('201 CREATED', response_b._status)
        self.assertNotEquals(response_a.json.get('package_version'),
                             response_b.json.get('package_version'))
        self.assertNotEquals(response_a.json.get('archive_name'),
                             response_b.json.get('archive_name'))
