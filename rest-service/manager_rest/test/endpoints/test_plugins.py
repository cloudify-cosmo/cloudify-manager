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
from mock import patch
from manager_rest.test.attribute import attr

from manager_rest import manager_exceptions
from manager_rest.test import base_test
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

        delete_response = self.client.plugins.delete(put_response['id'])

        # the yaml path should not be in the delete response
        put_response['yaml_url_path'] = ''
        self.assertEqual(put_response, delete_response)

        plugins_list = self.client.plugins.list()
        self.assertEqual(0, len(plugins_list),
                         'expecting 0 plugin result, '
                         'got {0}'.format(len(plugins_list)))

    @attr(client_min_version=3,
          client_max_version=base_test.LATEST_API_VERSION)
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

    @attr(client_min_version=2,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_upload_and_delete_installation_workflows(self):
        self.upload_plugin(TEST_PACKAGE_NAME, TEST_PACKAGE_VERSION)
        executions = self.client.executions.list(
            include_system_workflows=True).items
        self.assertEqual(1, len(executions))
        execution = executions[0]
        self.assertDictContainsSubset({
            'deployment_id': None,
            'is_system_workflow': True,
            'workflow_id': 'install_plugin'
        }, execution)
        plugin_id = self.client.plugins.list()[0].id
        self.client.plugins.delete(plugin_id=plugin_id)
        executions = self.client.executions.list(
            include_system_workflows=True).items
        self.assertEqual(2, len(executions))
        if executions[0] != execution:
            execution = executions[0]
        else:
            execution = executions[1]
        self.assertDictContainsSubset({
            'deployment_id': None,
            'is_system_workflow': True,
            'workflow_id': 'uninstall_plugin'
        }, execution)

    @attr(client_min_version=2.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_delete_force_with_cda_plugin(self):
        self.upload_plugin(TEST_PACKAGE_NAME, TEST_PACKAGE_VERSION)
        self.put_deployment(blueprint_file_name='uses_script_plugin.yaml')
        plugin = self.client.plugins.list().items[0]
        with self.assertRaises(exceptions.PluginInUseError):
            self.client.plugins.delete(plugin.id)
        self.assertEqual(1, len(self.client.plugins.list()))
        self.client.plugins.delete(plugin_id=plugin.id, force=True)
        self.assertEqual(0, len(self.client.plugins.list()))

    @attr(client_min_version=2.1,
          client_max_version=base_test.LATEST_API_VERSION)
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

    @attr(client_min_version=2,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_install_failure_rollback(self):
        def raises(*args, **kwargs):
            raise RuntimeError('RAISES')
        patch_path = ('manager_rest.resource_manager.ResourceManager.'
                      'install_plugin')
        with patch(patch_path, raises):
            response = self.upload_plugin(TEST_PACKAGE_NAME,
                                          TEST_PACKAGE_VERSION)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json['error_code'],
                         'plugin_installation_error')
        self.assertEqual(0, len(self.client.plugins.list()))

    @attr(client_min_version=2,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_install_timeout(self):
        def raises(*args, **kwargs):
            raise manager_exceptions.ExecutionTimeout('TIMEOUT')
        patch_path = ('manager_rest.resource_manager.ResourceManager.'
                      'install_plugin')
        with patch(patch_path, raises):
            response = self.upload_plugin(TEST_PACKAGE_NAME,
                                          TEST_PACKAGE_VERSION)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json['error_code'],
                         'plugin_installation_timeout')
        self.assertEqual(1, len(self.client.plugins.list()))

    @attr(client_min_version=2.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_uninstall_failure(self):
        def raises(*args, **kwargs):
            raise RuntimeError('RAISES')
        self.upload_plugin(TEST_PACKAGE_NAME, TEST_PACKAGE_VERSION)
        plugin_id = self.client.plugins.list()[0].id
        patch_path = ('manager_rest.resource_manager.ResourceManager.'
                      'remove_plugin')
        with patch(patch_path, raises):
            with self.assertRaises(exceptions.PluginInstallationError):
                self.client.plugins.delete(plugin_id)
        self.assertEqual(1, len(self.client.plugins.list()))

    @attr(client_min_version=2.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_uninstall_timeout(self):
        def raises(*args, **kwargs):
            raise manager_exceptions.ExecutionTimeout('TIMEOUT')
        self.upload_plugin(TEST_PACKAGE_NAME, TEST_PACKAGE_VERSION)
        plugin_id = self.client.plugins.list()[0].id
        patch_path = ('manager_rest.resource_manager.ResourceManager.'
                      'remove_plugin')
        with patch(patch_path, raises):
            with self.assertRaises(exceptions.PluginInstallationTimeout):
                self.client.plugins.delete(plugin_id)
        self.assertEqual(1, len(self.client.plugins.list()))

    @attr(client_min_version=3,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_plugin_upload_progress(self):
        tmp_file_path = self.create_wheel('cloudify-script-plugin', '1.5.3')
        yaml_path = self.get_full_path('mock_blueprint/plugin.yaml')
        zip_path = self.zip_files([tmp_file_path, yaml_path])
        total_size = os.path.getsize(zip_path)

        progress_func = generate_progress_func(
            total_size=total_size,
            assert_equal=self.assertEqual,
            assert_almost_equal=self.assertAlmostEqual)

        try:
            self.client.plugins.upload(zip_path,
                                       progress_callback=progress_func)
        finally:
            self.quiet_delete(tmp_file_path)

    @attr(client_min_version=3,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_plugin_upload_without_yaml(self):
        tmp_file_path = self.create_wheel('wagon', '0.6.1')
        try:
            self.client.plugins.upload(tmp_file_path)
        finally:
            self.quiet_delete(tmp_file_path)

    @attr(client_min_version=3,
          client_max_version=base_test.LATEST_API_VERSION)
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

            progress_func = generate_progress_func(
                total_size=total_size,
                assert_equal=self.assertEqual,
                assert_almost_equal=self.assertAlmostEqual)

            self.client.plugins.download(response.id,
                                         tmp_local_path,
                                         progress_callback=progress_func)
        finally:
            self.quiet_delete(tmp_file_path)
            self.quiet_delete(tmp_local_path)

    @attr(client_min_version=3,
          client_max_version=base_test.LATEST_API_VERSION)
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

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_plugin_upload_fails_with_empty_yaml(self):
        tmp_file_path = self.create_wheel(
            TEST_PACKAGE_NAME,
            TEST_PACKAGE_VERSION)
        yaml_path = self.get_full_path(TEST_PACKAGE_EMPTY_YAML_FILE)
        zip_path = self.zip_files([tmp_file_path, yaml_path])

        with self.assertRaises(exceptions.PluginInstallationError):
            self.client.plugins.upload(zip_path)

        self.quiet_delete(tmp_file_path)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_plugin_upload_fails_with_bad_yaml(self):
        tmp_file_path = self.create_wheel(
            TEST_PACKAGE_NAME,
            TEST_PACKAGE_VERSION)
        yaml_path = self.get_full_path(TEST_PACKAGE_BAD_YAML_FILE)
        zip_path = self.zip_files([tmp_file_path, yaml_path])

        with self.assertRaises(exceptions.PluginInstallationError):
            self.client.plugins.upload(zip_path)

        self.quiet_delete(tmp_file_path)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_plugin_upload_fails_with_inconsistent_with_wagon_yaml(self):
        tmp_file_path = self.create_wheel(
            TEST_PACKAGE_NAME,
            TEST_PACKAGE_VERSION)
        yaml_path = self.get_full_path(
            TEST_PACKAGE_INCONSISTENT_YAML_FILE)
        zip_path = self.zip_files([tmp_file_path, yaml_path])

        with self.assertRaises(exceptions.PluginInstallationError):
            self.client.plugins.upload(zip_path)

        self.quiet_delete(tmp_file_path)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
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

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_plugin_upload_check_default_title(self):
        tmp_file_path = self.create_wheel(
            TEST_PACKAGE_NAME,
            TEST_PACKAGE_VERSION)
        yaml_path = self.get_full_path(TEST_PACKAGE_YAML_FILE)
        zip_path = self.zip_files([tmp_file_path, yaml_path])
        uploaded_plugin = self.client.plugins.upload(zip_path)
        get_plugin_by_id_response = self.client.plugins.get(uploaded_plugin.id)
        self.assertIsNotNone(get_plugin_by_id_response)
        self.assertEqual(get_plugin_by_id_response.title, TEST_PACKAGE_NAME)
