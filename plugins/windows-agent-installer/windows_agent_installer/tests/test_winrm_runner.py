#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

TEST_WORKING_DIRECTORY = 'C:\work'

__author__ = 'elip'


import unittest
from windows_agent_installer import winrm_runner
from windows_agent_installer.tests import TEST_MACHINE_IP_ENV_VARIABLE
from nose.tools import nottest


TEST_FILE_DOWNLOAD_URL = 'https://github.com/cloudify-cosmo' \
                         '/cloudify-dsl-parser/archive/master.zip'


@nottest
class WinRMRunnerTest(unittest.TestCase):

    """
    Test cases for WinRM execution functionality.
    These tests run PowerShell commands remotely on a WinRM enabled server.

    An existing server must be setup, set the
    'TEST_MACHINE_IP' environment variable to the server IP.
    Otherwise, an exception will be raised.

    """

    runner = None

    @classmethod
    def setUpClass(cls):

        if TEST_MACHINE_IP_ENV_VARIABLE not in os.environ:
            raise RuntimeError('TEST_MACHINE_IP environment variable must '
                               'be set and point to an existing server with '
                               'WinRM configured properly')
        from windows_agent_installer.winrm_runner import WinRMRunner
        cls.runner = WinRMRunner(session_config=cls._create_session())

    def setUp(self):

        # Create the new working directory for this test.
        if self.runner.exists(path=TEST_WORKING_DIRECTORY):
            self.runner.delete(path=TEST_WORKING_DIRECTORY)
        self.runner.new_dir(path=TEST_WORKING_DIRECTORY)

    def tearDown(self):

        # Delete the working directory for this test.
        self.runner.delete(path=TEST_WORKING_DIRECTORY)

    @staticmethod
    def _create_session():
        return {
            'host': os.environ[TEST_MACHINE_IP_ENV_VARIABLE],
            'user': 'Administrator',
            'password': '1408Rokk'
        }

    def test_defaults(self):

        session_config = {
            'host': 'test_host',
            'user': 'test_user',
            'password': 'test_password'
        }

        from windows_agent_installer.winrm_runner import defaults
        defaults(session_config)
        self.assertEquals(
            session_config['protocol'],
            winrm_runner.DEFAULT_WINRM_PROTOCOL)
        self.assertEquals(
            session_config['uri'],
            winrm_runner.DEFAULT_WINRM_URI)
        self.assertEquals(
            session_config['port'],
            winrm_runner.DEFAULT_WINRM_PORT)

    def test_validate_host(self):

        # Missing host
        session_config = {
            'user': 'test_user',
            'password': 'test_password'
        }

        from windows_agent_installer.winrm_runner import validate
        try:
            validate(session_config)
            self.fail('Expected ValueError for missing host')
        except ValueError as e:
            self.assertEqual('Missing host in session_config', e.message)

    def test_validate_user(self):

        # Missing user
        session_config = {
            'host': 'test_host',
            'password': 'test_password'
        }

        from windows_agent_installer.winrm_runner import validate
        try:
            validate(session_config)
            self.fail('Expected ValueError for missing user')
        except ValueError as e:
            self.assertEqual('Missing user in session_config', e.message)

    def test_validate_password(self):

        # Missing password
        session_config = {
            'host': 'test_host',
            'user': 'test_user'
        }

        from windows_agent_installer.winrm_runner import validate
        try:
            validate(session_config)
            self.fail('Expected ValueError for missing password')
        except ValueError as e:
            self.assertEqual('Missing password in session_config', e.message)

    def test_run_success(self):

        response = self.runner.run('echo Hello!')
        self.assertEqual('Hello!\r\n', response.std_out)
        self.assertEqual(0, response.return_code)
        self.assertEqual('', response.std_err)

    def test_run_error(self):

        from windows_agent_installer.winrm_runner import \
            WinRMExecutionException
        try:
            self.runner.run('Bad command')
            self.fail('Expected WinRMExecutionException due to bad command')
        except WinRMExecutionException as e:
            self.assertEqual(1, e.code)

    def test_download(self):

        response = self.runner.download(
            url=TEST_FILE_DOWNLOAD_URL,
            output_path='{0}\parser.zip'.format(TEST_WORKING_DIRECTORY))
        self.assertEqual(0, response.return_code)
        self.assertEqual('', response.std_err)
        self.assertTrue(
            self.runner.exists(
                path='{0}\parser.zip'.format(TEST_WORKING_DIRECTORY)))

    def test_exists(self):

        # Assert does not exists.
        self.assertFalse(
            self.runner.exists(
                '{0}\k'.format(TEST_WORKING_DIRECTORY)))

        # Create the dir
        self.runner.new_dir(path='{0}\k'.format(TEST_WORKING_DIRECTORY))

        # Assert does exist.
        self.assertTrue(
            self.runner.exists(
                path='{0}\k'.format(TEST_WORKING_DIRECTORY)))

    def test_move(self):

        # Download the file.
        self.runner.download(
            TEST_FILE_DOWNLOAD_URL,
            '{0}\parser.zip'.format(TEST_WORKING_DIRECTORY))

        # Move it.
        self.runner.move(src='{0}\parser.zip'.format(TEST_WORKING_DIRECTORY),
                         dest='{0}\moved.zip'.format(TEST_WORKING_DIRECTORY))

        # Assert
        self.assertTrue(
            self.runner.exists(
                path='{0}\moved.zip'.format(TEST_WORKING_DIRECTORY)))
        self.assertFalse(
            self.runner.exists(
                path='{0}\parser.zip'.format(TEST_WORKING_DIRECTORY)))

    def test_delete(self):

        # Download the file.
        self.runner.download(
            url=TEST_FILE_DOWNLOAD_URL,
            output_path='{0}\parser.zip'.format(TEST_WORKING_DIRECTORY))

        # Assert file exists.
        self.assertTrue(
            self.runner.exists(
                path='{0}\parser.zip'.format(TEST_WORKING_DIRECTORY)))

        # Delete it.
        self.runner.delete('{0}\parser.zip'.format(TEST_WORKING_DIRECTORY))

        # Assert file does not exist.
        self.assertFalse(
            self.runner.exists(
                '{0}\parser.zip'.format(TEST_WORKING_DIRECTORY)))

    def test_new_file(self):

        # Assert file does not exists
        self.assertFalse(
            self.runner.exists(
                path='{0}\k.txt'.format(TEST_WORKING_DIRECTORY)))

        # Create the file
        self.runner.new_file(path='{0}\k.txt'.format(TEST_WORKING_DIRECTORY))

        # Assert file exists
        self.assertTrue(
            self.runner.exists(
                path='{0}\k.txt'.format(TEST_WORKING_DIRECTORY)))

    def test_new_dir(self):

        # Assert folder does not exists
        self.assertFalse(
            self.runner.exists(
                path='{0}\k'.format(TEST_WORKING_DIRECTORY)))

        # Create the folder
        self.runner.new_dir(path='{0}\k'.format(TEST_WORKING_DIRECTORY))

        # Assert folder exists
        self.assertTrue(
            self.runner.exists(
                path='{0}\k'.format(TEST_WORKING_DIRECTORY)))

    def test_copy(self):

        # Create a directory with a file inside
        self.runner.new_dir(path='{0}\k'.format(TEST_WORKING_DIRECTORY))
        self.runner.new_file(path='{0}\k\k.txt'.format(TEST_WORKING_DIRECTORY))

        # Copy the entire directory to a new one
        self.runner.copy(
            src='{0}\k'.format(TEST_WORKING_DIRECTORY),
            dest='{0}\e'.format(TEST_WORKING_DIRECTORY))

        # Assert new directory exists and contains the file
        self.assertTrue(
            self.runner.exists(
                path='{0}\e'.format(TEST_WORKING_DIRECTORY)))
        self.assertTrue(
            self.runner.exists(
                path='{0}\e\k.txt'.format(TEST_WORKING_DIRECTORY)))

    def test_copy_create_missing_directories(self):

        # Create a directory with a file inside
        self.runner.new_dir(path='{0}\k'.format(TEST_WORKING_DIRECTORY))
        self.runner.new_file(path='{0}\k\k.txt'.format(TEST_WORKING_DIRECTORY))

        # Copy the entire directory to a new one
        self.runner.copy(src='{0}\k'.format(TEST_WORKING_DIRECTORY),
                         dest='{0}\q\e'.format(TEST_WORKING_DIRECTORY),
                         create_missing_directories=True)

        # Assert new directory exists and contains the file
        self.assertTrue(
            self.runner.exists(
                path='{0}\q\e'.format(TEST_WORKING_DIRECTORY)))
        self.assertTrue(
            self.runner.exists(
                path='{0}\q\e\k.txt'.format(TEST_WORKING_DIRECTORY)))

    def test_service_state(self):

        state = self.runner.service_state('WinRM')
        self.assertEqual(state, 'Running')
