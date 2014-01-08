#/*******************************************************************************
# * Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
# *
# * Licensed under the Apache License, Version 2.0 (the "License");
# * you may not use this file except in compliance with the License.
# * You may obtain a copy of the License at
# *
# *       http://www.apache.org/licenses/LICENSE-2.0
# *
# * Unless required by applicable law or agreed to in writing, software
# * distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.
# *******************************************************************************/

import os
import tempfile

__author__ = 'elip'
import unittest
from plugin_installer.tasks import get_plugin_simple_name, create_namespace_path, install_celery_plugin_to_dir
from plugin_installer.tests import get_logger
from cloudify.constants import COSMO_PLUGIN_NAMESPACE

logger = get_logger("PluginInstallerTestCase")


class PluginInstallerTestCase(unittest.TestCase):

    def test_get_plugin_simple_name(self):
        name = "a.b.c"
        self.assertEqual(get_plugin_simple_name(name), "c")

    def test_create_namespace_path(self):

        base_dir = tempfile.NamedTemporaryFile().name

        create_namespace_path(COSMO_PLUGIN_NAMESPACE, base_dir)

        # lets make sure the correct structure was created
        namespace_path = base_dir
        for folder in COSMO_PLUGIN_NAMESPACE:
            namespace_path = os.path.join(namespace_path, folder)
            with open(os.path.join(namespace_path,  "__init__.py")) as f:
                init_data = f.read()
                # we create empty init files
                assert init_data == ""

    def test_install(self):

        plugin = {
            "name": "test.plugin.mock_for_test",
            "url": os.path.join(os.path.dirname(__file__), "mock-plugin"),
        }

        base_dir = tempfile.NamedTemporaryFile().name

        install_celery_plugin_to_dir(plugin=plugin, base_dir=base_dir)

        expected_plugin_path = os.path.join(base_dir, plugin['name'].replace(".", "/"))

        # check the plugin was installed to the correct directory
        assert os.path.exists(expected_plugin_path)

