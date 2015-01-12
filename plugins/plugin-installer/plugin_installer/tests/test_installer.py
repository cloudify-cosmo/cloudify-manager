########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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
from os.path import dirname
import tempfile
import shutil

import testtools

from cloudify.exceptions import NonRecoverableError
from cloudify.mocks import MockCloudifyContext
from cloudify.utils import LocalCommandRunner
from cloudify.utils import setup_default_logger
from plugin_installer.tasks import install, update_includes, \
    parse_pip_version, is_pip6_or_higher
from cloudify.constants import CELERY_WORK_DIR_PATH_KEY
from cloudify.constants import VIRTUALENV_PATH_KEY
from cloudify.constants import LOCAL_IP_KEY
from cloudify.constants import MANAGER_FILE_SERVER_BLUEPRINTS_ROOT_URL_KEY


logger = setup_default_logger('test_plugin_installer')


def _get_local_path(ctx, plugin):
    return os.path.join(dirname(__file__),
                        plugin['source'])


class PluginInstallerTestCase(testtools.TestCase):

    TEST_BLUEPRINT_ID = 'test_id'
    MANAGER_FILE_SERVER_BLUEPRINTS_ROOT_URL = 'localhost/blueprints'

    def setUp(self):
        super(PluginInstallerTestCase, self).setUp()
        self.temp_folder = tempfile.mkdtemp()

        # Create a virtualenv in a temp folder.
        # this will be used for actually installing plugins of tests.
        os.environ[LOCAL_IP_KEY] = 'localhost'
        LocalCommandRunner().run('virtualenv {0}'.format(self.temp_folder))
        os.environ[VIRTUALENV_PATH_KEY] = self.temp_folder

        self.ctx = MockCloudifyContext(
            blueprint_id=self.TEST_BLUEPRINT_ID
        )
        os.environ[CELERY_WORK_DIR_PATH_KEY] = self.temp_folder
        os.environ[MANAGER_FILE_SERVER_BLUEPRINTS_ROOT_URL_KEY] \
            = self.MANAGER_FILE_SERVER_BLUEPRINTS_ROOT_URL

    def tearDown(self):
        shutil.rmtree(self.temp_folder)
        super(PluginInstallerTestCase, self).tearDown()

    def _assert_plugin_installed(self, package_name,
                                 plugin, dependencies=None):
        if not dependencies:
            dependencies = []
        runner = LocalCommandRunner()
        out = runner.run(
            '{0}/bin/pip list | grep {1}'
            .format(self.temp_folder, plugin['name'])).std_out
        self.assertIn(package_name, out)
        for dependency in dependencies:
            self.assertIn(dependency, out)

    def test_get_url_http(self):
        from plugin_installer.tasks import get_url
        url = get_url(self.ctx.blueprint.id, {'source': 'http://google.com'})
        self.assertEqual(url, 'http://google.com')

    def test_get_url_https(self):
        from plugin_installer.tasks import get_url
        url = get_url(self.ctx.blueprint.id, {'source': 'https://google.com'})
        self.assertEqual(url, 'https://google.com')

    def test_get_url_faulty_schema(self):
        from plugin_installer.tasks import get_url
        self.assertRaises(NonRecoverableError,
                          get_url,
                          self.ctx.blueprint.id,
                          {'source': 'bla://google.com'})

    def test_get_url_folder(self):
        from plugin_installer.tasks import get_url
        url = get_url(self.ctx.blueprint.id, {'source': 'plugin'})
        self.assertEqual(url,
                         '{0}/{1}/plugins/plugin.zip'
                         .format(
                             self.MANAGER_FILE_SERVER_BLUEPRINTS_ROOT_URL,
                             self.TEST_BLUEPRINT_ID))

    def test_install(self):

        # override get_url to return local paths
        from plugin_installer import tasks
        tasks.get_url = _get_local_path

        plugin = {
            'name': 'mock-plugin',
            'source': 'mock-plugin'
        }

        install(plugins=[plugin])
        self._assert_plugin_installed('mock-plugin', plugin)

        # Assert includes file was written
        out = LocalCommandRunner().run(
            'cat {0}'.format(
                os.path.join(self.temp_folder,
                             'celeryd-includes'))).std_out
        self.assertIn('mock_for_test.module', out)

    def test_install_with_dependencies(self):

        # override get_url to return local paths
        from plugin_installer import tasks
        tasks.get_url = _get_local_path

        plugin = {
            'name': 'mock-with-dependencies-plugin',
            'source': 'mock-with-dependencies-plugin'
        }

        install(plugins=[plugin])
        self._assert_plugin_installed('mock-with-dependencies-plugin',
                                      plugin,
                                      dependencies=['simplejson'])

        # Assert includes file was written
        out = LocalCommandRunner().run(
            'cat {0}'.format(
                os.path.join(self.temp_folder,
                             'celeryd-includes'))).std_out
        self.assertIn('mock_with_dependencies_for_test.module', out)

    def test_write_to_empty_includes(self):

        update_includes(['a.tasks', 'b.tasks'])

        # The includes file will be created
        # in the temp folder for this test
        with open('{0}/celeryd-includes'
                  .format(self.temp_folder), mode='r') as f:
            includes = f.read()
            self.assertEquals("INCLUDES=a.tasks,b.tasks\n", includes)

    def test_write_to_existing_includes(self):

        # Create initial includes file
        update_includes(['test.tasks'])

        # Append to that file
        update_includes(['a.tasks', 'b.tasks'])
        with open('{0}/celeryd-includes'
                  .format(self.temp_folder), mode='r') as f:
            includes = f.read()
            self.assertEquals(
                "INCLUDES=test.tasks,a.tasks,b.tasks\n",
                includes)


class PipVersionParserTestCase(testtools.TestCase):

    def test_parse_long_format_version(self):
        version_tupple = parse_pip_version('1.5.4')
        self.assertEqual(('1', '5', '4'), version_tupple)

    def test_parse_short_format_version(self):
        version_tupple = parse_pip_version('6.0')
        self.assertEqual(('6', '0', ''), version_tupple)

    def test_pip6_not_higher(self):
        result = is_pip6_or_higher('1.5.4')
        self.assertEqual(result, False)

    def test_pip6_exactly(self):
        result = is_pip6_or_higher('6.0')
        self.assertEqual(result, True)

    def test_pip6_is_higher(self):
        result = is_pip6_or_higher('6.0.6')
        self.assertEqual(result, True)

    def test_parse_invalid_major_version(self):
        expected_err_msg = 'Invalid pip version: "a.5.4", major version is ' \
                           '"a" while expected to be a number'
        self.assertRaisesRegex(NonRecoverableError, expected_err_msg,
                               parse_pip_version, 'a.5.4')

    def test_parse_invalid_minor_version(self):
        expected_err_msg = 'Invalid pip version: "1.a.4", minor version is ' \
                           '"a" while expected to be a number'
        self.assertRaisesRegex(NonRecoverableError, expected_err_msg,
                               parse_pip_version, '1.a.4')

    def test_parse_too_short_version(self):
        expected_err_msg = 'Unknown formatting of pip version: "6", expected ' \
                           'dot-delimited numbers \(e.g. "1.5.4", "6.0"\)'
        self.assertRaisesRegex(NonRecoverableError, expected_err_msg,
                               parse_pip_version, '6')

    def test_parse_numeric_version(self):
        expected_err_msg = 'Invalid pip version: 6 is not a string'
        self.assertRaisesRegex(NonRecoverableError, expected_err_msg,
                               parse_pip_version, 6)

    def test_parse_alpha_version(self):
        expected_err_msg = 'Unknown formatting of pip version: "a", expected ' \
                           'dot-delimited numbers \(e.g. "1.5.4", "6.0"\)'
        self.assertRaisesRegex(NonRecoverableError, expected_err_msg,
                               parse_pip_version, 'a')

    def test_parse_wrong_obj(self):
        expected_err_msg = 'Invalid pip version: \[6\] is not a string'
        self.assertRaisesRegex(NonRecoverableError, expected_err_msg,
                               parse_pip_version, [6])
