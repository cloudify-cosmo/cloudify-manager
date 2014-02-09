#/***************************************************************************
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
# ***************************************************************************/

import os
from os.path import dirname
import sys
import tempfile


__author__ = 'elip'

import unittest
from plugin_installer.tasks import get_plugin_simple_name, \
    install_celery_plugin, uninstall_celery_plugin, \
    extract_plugin_name, append_to_includes, extract_module_paths
from plugin_installer.tests import get_logger
from cloudify.constants import VIRTUALENV_PATH_KEY


logger = get_logger("PluginInstallerTestCase")


class PluginInstallerTestCase(unittest.TestCase):

    plugins = {
        "plugin": {
            "name": "mock-plugin",
            "url": os.path.join(os.path.dirname(__file__), "mock-plugin")
        },
        "plugin_with_dependencies": {
            "name": "mock-with-dependencies-plugin",
            "url": os.path.join(os.path.dirname(__file__),
                                "mock-with-dependencies-plugin")
        }
    }

    def setUp(self):
        python_home = dirname(dirname(sys.executable))

        logger.info("Setting virtualenv path to {0}".format(python_home))

        os.environ[VIRTUALENV_PATH_KEY] = python_home

    def tearDown(self):

        logger.info("Uninstalling all plugins that were installed by the test")

        for plugin in self.plugins.itervalues():
            try:
                uninstall_celery_plugin(plugin_name=plugin['name'])
            except BaseException as e:
                logger.warning("Failed to uninstall plugin {0} : {1}"
                               .format(plugin['name'], e.message))

    def test_get_plugin_simple_name(self):
        name = "a.b.c"
        self.assertEqual(get_plugin_simple_name(name), "c")

    def test_install(self):

        install_celery_plugin(plugin=self.plugins['plugin'])

        # check the plugin was installed
        from mock_for_test import module as m
        print m.var

    def test_install_with_dependencies(self):

        install_celery_plugin(plugin=self.plugins['plugin_with_dependencies'])

        # check the plugin was installed
        from mock_with_dependencies_for_test import module as m
        print m.var

        # check the dependency was installed
        from python_webserver_installer import tasks as t
        t.get_ip

    def test_extract_plugin_name(self):
        name = extract_plugin_name(self.plugins['plugin']['url'])
        assert name == "mock-plugin"

    def test_append_to_empty_includes(self):

        temp_folder = os.path.join(tempfile.gettempdir())
        try:
            append_to_includes("a.tasks,b.tasks", "{0}/celeryd-includes".format(temp_folder))
            with open("{0}/celeryd-includes".format(temp_folder), mode='r') as f:
                includes = f.read()
                self.assertEquals("INCLUDES=a.tasks,b.tasks", includes)

        finally:
            os.remove("{0}/celeryd-includes".format(temp_folder))

    def test_append_to_existing_includes(self):
        temp_folder = os.path.join(tempfile.gettempdir())
        try:
            with open("{0}/celeryd-includes".format(temp_folder), mode='w') as f:
                f.write("INCLUDES=test.tasks")
            append_to_includes("a.tasks,b.tasks", "{0}/celeryd-includes".format(temp_folder))
            with open("{0}/celeryd-includes".format(temp_folder), mode='r') as f:
                includes = f.read()
                self.assertEquals("INCLUDES=test.tasks\nINCLUDES=test.tasks,a.tasks,b.tasks", includes)

        finally:
            os.remove("{0}/celeryd-includes".format(temp_folder))

    def test_extract_module_paths(self):

        install_celery_plugin(self.plugins['plugin'])

        assert "mock_for_test.module" in extract_module_paths("mock-plugin")
