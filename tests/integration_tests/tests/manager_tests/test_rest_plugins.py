########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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

import os
import shutil

from integration_tests import ManagerTestCase
from integration_tests.tests.utils import get_resource as resource


class RestPluginsTests(ManagerTestCase):

    def test_install_rest_plugins(self):
        self.bootstrap(modify_blueprint_func=self._modify_manager_blueprint)
        self._assert_plugins_installed()

    def _modify_manager_blueprint(self, patcher, manager_blueprint_dir):
        src_plugin_dir = resource('plugins/mock-rest-plugin')
        shutil.copytree(
            src_plugin_dir,
            os.path.join(manager_blueprint_dir, 'mock-rest-plugin'))
        plugins = {
            'plugin1': {
                # testing plugin installation from remote url
                'source': 'https://github.com/cloudify-cosmo/'
                          'cloudify-plugin-template/archive/{0}.zip'
                          .format(self.env.core_branch_name)
            },
            'plugin2': {
                # testing plugin installation in manager blueprint directory
                'source': 'mock-rest-plugin',
                # testing install_args, without the following, plugin
                # installation should fail
                'install_args': "--install-option='--do-not-fail'"
            }
        }
        plugins_path = 'node_templates.rest_service.properties.plugins'
        patcher.set_value(plugins_path, plugins)

    def _assert_plugins_installed(self):
        local_script_path = resource('scripts/test_rest_plugins.sh')
        remote_script_path = '/root/test_rest_plugins.sh'
        self.copy_file_to_manager(source=local_script_path,
                                  target=remote_script_path)
        output = self.execute_on_manager('bash {0}'.format(remote_script_path))
        # This tells us that plugin-template was successfully installed
        self.assertIn('imported_plugin_tasks', output)
        # This tells us that mock-rest-plugin was successfully installed
        self.assertIn('mock_attribute_value', output)
