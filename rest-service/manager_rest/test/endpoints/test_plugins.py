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

import os

from manager_rest.test.base_test import BaseServerTestCase

from cloudify_rest_client import exceptions
from .test_utils import generate_progress_func

TEST_PACKAGE_NAME = 'cloudify-script-plugin'
TEST_PACKAGE_VERSION = '1.3'
TEST_PACKAGE_YAML_FILE = 'mock_blueprint/plugin.yaml'
TEST_PACKAGE_NAME2 = 'cloudify-diamond-plugin'
TEST_PACKAGE_VERSION2 = '1.3'
TEST_PACKAGE_YAML_FILE2 = 'mock_blueprint/plugin-cloudify-diamond-plugin.yaml'

TEST_PACKAGE_BAD_YAML_FILE = 'mock_blueprint/plugin_bad.yaml'
TEST_PACKAGE_EMPTY_YAML_FILE = 'mock_blueprint/plugin_empty.yaml'
TEST_PACKAGE_INCONSISTENT_YAML_FILE = \
    'mock_blueprint/plugin_inconsistent_with_wagon.yaml'

OLD_TEST_PACKAGE_VERSION = '1.2'


class PluginsTest(BaseServerTestCase):
    """
    Test plugins upload and download.
    """
    def test_get_plugin_by_id(self):
        put_plugin_response = self.upload_plugin(TEST_PACKAGE_NAME,
                                                 TEST_PACKAGE_VERSION).json
        plugin_id = put_plugin_response.get('id')
        self.assertIsNotNone(plugin_id)
        self.assertEqual(put_plugin_response.get('package_name'),
                         TEST_PACKAGE_NAME)
        self.assertEqual(put_plugin_response.get('package_version'),
                         TEST_PACKAGE_VERSION)
        get_plugin_by_id_response = self.client.plugins.get(plugin_id)

        self.assertEqual(put_plugin_response, get_plugin_by_id_response)

    def test_get_plugin_not_found(self):
        try:
            self.client.plugins.get('DUMMY_PLUGIN_ID')
        except exceptions.CloudifyClientError as e:
            self.assertEqual(404, e.status_code)

    def test_delete_plugin(self):
        put_response = self.upload_plugin(TEST_PACKAGE_NAME,
                                          TEST_PACKAGE_VERSION).json

        plugins_list = self.client.plugins.list()
        self.assertEqual(1, len(plugins_list),
                         'expecting 1 plugin result, '
                         'got {0}'.format(len(plugins_list)))

        self.client.plugins.delete(put_response['id'])

        plugins_list = self.client.plugins.list()
        self.assertEqual(0, len(plugins_list),
                         'expecting 0 plugin result, '
                         'got {0}'.format(len(plugins_list)))

    def test_sort_list_plugins(self):
        self.upload_plugin(TEST_PACKAGE_NAME, OLD_TEST_PACKAGE_VERSION)
        self.upload_plugin(TEST_PACKAGE_NAME, TEST_PACKAGE_VERSION)

        plugins = self.client.plugins.list(sort='uploaded_at')
        self.assertEqual(2, len(plugins))
        self.assertEqual(OLD_TEST_PACKAGE_VERSION, plugins[0].package_version)
        self.assertEqual(TEST_PACKAGE_VERSION, plugins[1].package_version)

        plugins = self.client.plugins.list(
            sort='uploaded_at', is_descending=True)
        self.assertEqual(2, len(plugins))
        self.assertEqual(TEST_PACKAGE_VERSION, plugins[0].package_version)
        self.assertEqual(OLD_TEST_PACKAGE_VERSION, plugins[1].package_version)

    def test_delete_plugin_not_found(self):
        try:
            self.client.plugins.delete('DUMMY_PLUGIN_ID')
        except exceptions.CloudifyClientError as e:
            self.assertEqual(404, e.status_code)

    def test_put_same_plugin_module_twice_response_status(self):
        ok_response = self.upload_plugin(TEST_PACKAGE_NAME,
                                         TEST_PACKAGE_VERSION)
        self.assertEqual('201 CREATED', ok_response._status)
        error_response = self.upload_plugin(TEST_PACKAGE_NAME,
                                            TEST_PACKAGE_VERSION)
        self.assertEqual('409 CONFLICT', error_response._status)

    def test_post_plugin_package_different_versions(self):
        response_a = self.upload_plugin(TEST_PACKAGE_NAME,
                                        TEST_PACKAGE_VERSION)
        self.assertEqual('201 CREATED', response_a._status)
        response_b = self.upload_plugin(TEST_PACKAGE_NAME,
                                        OLD_TEST_PACKAGE_VERSION)
        self.assertEqual('201 CREATED', response_b._status)
        self.assertNotEqual(response_a.json.get('package_version'),
                            response_b.json.get('package_version'))
        self.assertNotEqual(response_a.json.get('archive_name'),
                            response_b.json.get('archive_name'))

    def test_delete_force_with_cda_plugin(self):
        self.upload_plugin(TEST_PACKAGE_NAME, TEST_PACKAGE_VERSION)
        self.put_deployment(blueprint_file_name='uses_script_plugin.yaml')
        plugin = self.client.plugins.list().items[0]
        with self.assertRaises(exceptions.PluginInUseError):
            self.client.plugins.delete(plugin.id)
        self.assertEqual(1, len(self.client.plugins.list()))
        self.client.plugins.delete(plugin_id=plugin.id, force=True)
        self.assertEqual(0, len(self.client.plugins.list()))

    def test_delete_force_with_host_agent_plugin(self):
        self.upload_plugin(TEST_PACKAGE_NAME,
                           TEST_PACKAGE_VERSION,
                           'mock_blueprint/host_agent_plugin.yaml')
        self.put_deployment(blueprint_file_name='host_agent_blueprint.yaml')
        plugin = self.client.plugins.list().items[0]
        with self.assertRaises(exceptions.PluginInUseError):
            self.client.plugins.delete(plugin.id)
        self.assertEqual(1, len(self.client.plugins.list()))
        self.client.plugins.delete(plugin_id=plugin.id, force=True)
        self.assertEqual(0, len(self.client.plugins.list()))

    def test_plugin_upload_progress(self):
        tmp_file_path = self.create_wheel('cloudify-script-plugin', '1.5.3')
        yaml_path = self.get_full_path('mock_blueprint/plugin.yaml')
        zip_path = self.zip_files([tmp_file_path, yaml_path])
        total_size = os.path.getsize(zip_path)

        progress_func = generate_progress_func(total_size=total_size)

        try:
            self.client.plugins.upload(zip_path,
                                       progress_callback=progress_func)
        finally:
            self.quiet_delete(tmp_file_path)

    def test_plugin_upload_without_yaml(self):
        tmp_file_path = self.create_wheel('wagon', '0.6.1')
        try:
            self.client.plugins.upload(tmp_file_path)
        finally:
            self.quiet_delete(tmp_file_path)

    def test_plugin_download_progress(self):
        tmp_file_path = self.create_wheel(
            TEST_PACKAGE_NAME,
            TEST_PACKAGE_VERSION)
        yaml_path = self.get_full_path(TEST_PACKAGE_YAML_FILE)
        zip_path = self.zip_files([tmp_file_path, yaml_path])
        tmp_local_path = '/tmp/plugin.whl'

        try:
            response = self.client.plugins.upload(zip_path)
            total_size = os.path.getsize(tmp_file_path)

            progress_func = generate_progress_func(total_size=total_size)

            self.client.plugins.download(response.id,
                                         tmp_local_path,
                                         progress_callback=progress_func)
        finally:
            self.quiet_delete(tmp_file_path)
            self.quiet_delete(tmp_local_path)

    def test_caravan_upload(self):
        self.upload_caravan(
            {
                TEST_PACKAGE_NAME:
                    [TEST_PACKAGE_VERSION, TEST_PACKAGE_YAML_FILE],
                TEST_PACKAGE_NAME2:
                    [TEST_PACKAGE_VERSION2, TEST_PACKAGE_YAML_FILE2]
            }
        )
        plugins_list = self.client.plugins.list()
        self.assertEqual(len(plugins_list), 2)

    def test_plugin_upload_with_title(self):
        tmp_file_path = self.create_wheel(
            TEST_PACKAGE_NAME,
            TEST_PACKAGE_VERSION)
        yaml_path = self.get_full_path(TEST_PACKAGE_YAML_FILE)
        zip_path = self.zip_files([tmp_file_path, yaml_path])
        uploaded_plugin = self.client.plugins.upload(zip_path,
                                                     plugin_title='test')
        get_plugin_by_id_response = self.client.plugins.get(uploaded_plugin.id)
        self.assertIsNotNone(get_plugin_by_id_response)
        self.assertEqual(get_plugin_by_id_response.title, 'test')

    def test_plugin_upload_check_default_title(self):
        uploaded_plugin = self.upload_plugin(TEST_PACKAGE_NAME,
                                             TEST_PACKAGE_VERSION).json
        plugin_id = uploaded_plugin.get('id')
        self.assertIsNotNone(plugin_id)
        self.assertEqual(uploaded_plugin.get('title'), TEST_PACKAGE_NAME)
        get_plugin_by_id_response = self.client.plugins.get(plugin_id)
        self.assertIsNotNone(get_plugin_by_id_response)
        self.assertEqual(get_plugin_by_id_response.title, TEST_PACKAGE_NAME)

    def test_plugin_upload_blueprint_labels(self):
        uploaded_plugin = self.upload_plugin(
            TEST_PACKAGE_NAME,
            TEST_PACKAGE_VERSION,
            'mock_blueprint/plugin_labels_and_tags.yaml').json
        plugin_id = uploaded_plugin.get('id')
        plugin = self.client.plugins.get(plugin_id)
        assert plugin.blueprint_labels == {
            'arch': ['docker', 'k8s'],
            'csys-obj-type': ['aws'],
        }
        assert plugin.labels == {
            'arch': ['k8s'],
            'csys-obj-type': ['eks'],
        }
        assert plugin.resource_tags == {
            'key1': 'value1',
            'key2': 'value2',
        }

    def test_plugin_upload_blueprint_invalid_labels(self):
        response = self.upload_plugin(
            TEST_PACKAGE_NAME,
            TEST_PACKAGE_VERSION,
            'mock_blueprint/plugin_invalid_labels.yaml')
        assert response.status_code == 400
