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
import tarfile
import filecmp

import testtools

from cloudify.exceptions import NonRecoverableError
from cloudify.mocks import MockCloudifyContext
from cloudify.utils import LocalCommandRunner
from cloudify.utils import setup_default_logger
from plugin_installer.tasks import install, get_url, update_includes, \
    parse_pip_version, is_pip6_or_higher, extract_plugin_dir
from cloudify.constants import CELERY_WORK_DIR_PATH_KEY
from cloudify.constants import VIRTUALENV_PATH_KEY
from cloudify.constants import LOCAL_IP_KEY
from cloudify.constants import MANAGER_FILE_SERVER_BLUEPRINTS_ROOT_URL_KEY
from plugin_installer.tests.file_server import FileServer
from plugin_installer.tests.file_server import PORT


logger = setup_default_logger('test_plugin_installer')

MOCK_PLUGIN = 'mock-plugin'
MOCK_PLUGIN_WITH_DEPENDENCIES = 'mock-with-dependencies-plugin'
ZIP_SUFFIX = 'zip'
TAR_SUFFIX = 'tar'
TEST_BLUEPRINT_ID = 'mock_blueprint_id'
PLUGINS_DIR = '{0}/plugins'.format(TEST_BLUEPRINT_ID)
MANAGER_FILE_SERVER_BLUEPRINTS_ROOT_URL = 'http://localhost:{0}' \
    .format(PORT)


def _get_local_path(ctx, plugin):
    return os.path.join(dirname(__file__),
                        plugin['source'])


class PluginInstallerTestCase(testtools.TestCase):

    @classmethod
    def setUpClass(cls):
        # create tar files for the mock plugins used by the tests
        cls.create_plugin_tar(MOCK_PLUGIN)
        cls.create_plugin_tar(MOCK_PLUGIN_WITH_DEPENDENCIES)

        test_file_server = None
        try:
            # start file server
            local_dir = dirname(__file__)
            test_file_server = FileServer(local_dir)
            test_file_server.start()
        except Exception as e:
            logger.info('Failed to start local file server, '
                        'reported error: {0}'.format(e.message))
            if test_file_server:
                try:
                    test_file_server.stop()
                except Exception as e:
                    logger.info('failed to stop local file server: {0}'
                                .format(e.message))

    @classmethod
    def tearDownClass(cls):
        local_dir = dirname(__file__)
        test_file_server = FileServer(local_dir)
        if test_file_server:
            try:
                test_file_server.stop()
            except Exception as e:
                logger.info('failed to stop local file server: {0}'
                            .format(e.message))

    def setUp(self):
        super(PluginInstallerTestCase, self).setUp()
        self.temp_folder = tempfile.mkdtemp()

        # Create a virtualenv in a temp folder.
        # this will be used for actually installing plugins of tests.
        os.environ[LOCAL_IP_KEY] = 'localhost'
        LocalCommandRunner().run('virtualenv {0}'.format(self.temp_folder))
        os.environ[VIRTUALENV_PATH_KEY] = self.temp_folder

        self.ctx = MockCloudifyContext(
            blueprint_id=TEST_BLUEPRINT_ID
        )
        os.environ[CELERY_WORK_DIR_PATH_KEY] = self.temp_folder
        os.environ[MANAGER_FILE_SERVER_BLUEPRINTS_ROOT_URL_KEY] \
            = MANAGER_FILE_SERVER_BLUEPRINTS_ROOT_URL

    def tearDown(self):
        if os.path.exists(self.temp_folder):
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
        url = get_url(self.ctx.blueprint.id, {'source': 'http://google.com'})
        self.assertEqual(url, 'http://google.com')

    def test_get_url_https(self):
        url = get_url(self.ctx.blueprint.id, {'source': 'https://google.com'})
        self.assertEqual(url, 'https://google.com')

    def test_get_url_faulty_schema(self):
        self.assertRaises(NonRecoverableError,
                          get_url,
                          self.ctx.blueprint.id,
                          {'source': 'bla://google.com'})

    def test_get_url_local_plugin(self):
        mock_plugin = {
            'source': MOCK_PLUGIN
        }
        url = get_url(self.ctx.blueprint.id, mock_plugin)
        self.assertEqual(url,
                         '{0}/{1}/{2}.{3}'
                         .format(
                             MANAGER_FILE_SERVER_BLUEPRINTS_ROOT_URL,
                             PLUGINS_DIR,
                             MOCK_PLUGIN, ZIP_SUFFIX))

    def test_extract_url(self):
        plugin_source = '{0}/{1}/{2}.{3}'.format(
            MANAGER_FILE_SERVER_BLUEPRINTS_ROOT_URL, PLUGINS_DIR,
            MOCK_PLUGIN, TAR_SUFFIX)
        plugin = {
            'name': MOCK_PLUGIN,
            'source': plugin_source
        }
        url = get_url(self.ctx.blueprint.id, plugin)
        extracted_plugin_dir = extract_plugin_dir(url)
        self.assertTrue(PluginInstallerTestCase.
                        are_dir_trees_equal(MOCK_PLUGIN, extracted_plugin_dir))

    def test_install(self):
        plugin_source = '{0}/{1}/{2}.{3}'.format(
            MANAGER_FILE_SERVER_BLUEPRINTS_ROOT_URL, PLUGINS_DIR,
            MOCK_PLUGIN, TAR_SUFFIX)
        plugin = {
            'name': MOCK_PLUGIN,
            'source': plugin_source
        }

        ctx = MockCloudifyContext(blueprint_id=TEST_BLUEPRINT_ID)
        install(ctx, plugins=[plugin])
        self._assert_plugin_installed(MOCK_PLUGIN, plugin)

        # Assert includes file was written
        out = LocalCommandRunner().run(
            'cat {0}'.format(
                os.path.join(self.temp_folder,
                             'celeryd-includes'))).std_out
        self.assertIn('mock_for_test.module', out)

    def test_install_with_dependencies(self):

        plugin_source = '{0}/{1}/{2}.{3}'.format(
            MANAGER_FILE_SERVER_BLUEPRINTS_ROOT_URL, PLUGINS_DIR,
            MOCK_PLUGIN_WITH_DEPENDENCIES, TAR_SUFFIX)

        plugin = {
            'name': MOCK_PLUGIN_WITH_DEPENDENCIES,
            'source': plugin_source
        }

        ctx = MockCloudifyContext(blueprint_id=TEST_BLUEPRINT_ID)
        install(ctx, plugins=[plugin])
        self._assert_plugin_installed(MOCK_PLUGIN_WITH_DEPENDENCIES,
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

    @staticmethod
    def create_plugin_tar(plugin_dir_name):

        plugin_path_abs = os.path.join(dirname(__file__), plugin_dir_name)

        # create the plugins directory if doesn't exist
        if not os.path.exists(PLUGINS_DIR):
            os.makedirs(PLUGINS_DIR)

        # the tar file will be created under mock_blueprint_id/plugins
        tar_file_path = '{0}/{1}/{2}.{3}'.format(dirname(__file__),
                                                 PLUGINS_DIR,
                                                 plugin_dir_name,
                                                 TAR_SUFFIX)

        # create the file, if it doesn't exist
        if not os.path.exists(tar_file_path):
            plugin_tar_file = tarfile.TarFile(tar_file_path, 'w')
            plugin_tar_file.add(plugin_path_abs)
            plugin_tar_file.close()

    @staticmethod
    def are_dir_trees_equal(dir1, dir2):
        """
        Compare two directories recursively. Files in each directory are
        assumed to be equal if their names and contents are equal.

        @param dir1: First directory path
        @param dir2: Second directory path

        @return: True if the directory trees are the same and
            there were no errors while accessing the directories or files,
            False otherwise.
       """

        # compare file lists in both dirs. If found different lists
        # or "funny" files (failed to compare) - return false
        dirs_cmp = filecmp.dircmp(dir1, dir2)
        if len(dirs_cmp.left_only) > 0 or len(dirs_cmp.right_only) > 0 or \
           len(dirs_cmp.funny_files) > 0:
            return False

        # compare the common files between dir1 and dir2
        (match, mismatch, errors) = filecmp.cmpfiles(
            dir1, dir2, dirs_cmp.common_files, shallow=False)
        if len(mismatch) > 0 or len(errors) > 0:
            return False

        # continue to compare sub-directories, recursively
        for common_dir in dirs_cmp.common_dirs:
            new_dir1 = os.path.join(dir1, common_dir)
            new_dir2 = os.path.join(dir2, common_dir)
            if not PluginInstallerTestCase.are_dir_trees_equal(
                    new_dir1, new_dir2):
                return False

        return True


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
