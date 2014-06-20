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


__author__ = 'elip'


import unittest
from windows_agent_installer import winrm_runner


class WinRMRunnerTest(unittest.TestCase):

    def test_defaults(self):

        session_config = {
            'host': 'test_host',
            'user': 'test_user',
            'password': 'test_password'
        }

        from windows_agent_installer.winrm_runner import defaults
        defaults(session_config)
        self.assertEquals(session_config['protocol'], winrm_runner.DEFAULT_WINRM_PROTOCOL)
        self.assertEquals(session_config['uri'], winrm_runner.DEFAULT_WINRM_URI)
        self.assertEquals(session_config['port'], winrm_runner.DEFAULT_WINRM_PORT)

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

        session_config = {
            'host': '15.126.232.188',
            'user': 'Administrator',
            'password': '1408Rokk'
        }

        from windows_agent_installer.winrm_runner import WinRMRunner
        runner = WinRMRunner(session_config=session_config)
        response = runner.run('echo Hello!')
        self.assertEqual('Hello!\r\n', response.std_out)
        self.assertEqual(0, response.status_code)
        self.assertEqual('', response.std_err)


    def test_run_error(self):

        session_config = {
            'host': '15.126.232.188',
            'user': 'Administrator',
            'password': '1408Rokk'
        }

        from windows_agent_installer.winrm_runner import WinRMRunner
        from windows_agent_installer.winrm_runner import WinRMExecutionException
        runner = WinRMRunner(session_config=session_config)
        try:
            runner.run('Bad command')
            self.fail('Expected WinRMExecutionException due to bad command')
        except WinRMExecutionException as e:
            self.assertEqual(1, e.code)


    def test_download(self):

        session_config = {
            'host': '15.126.232.188',
            'user': 'Administrator',
            'password': '1408Rokk'
        }

        from windows_agent_installer.winrm_runner import WinRMRunner
        runner = WinRMRunner(session_config=session_config)
        response = runner.download(
            url='https://github.com/cloudify-cosmo/cloudify-dsl-parser/archive/develop.zip',
            output_path='C:\Users\Administrator\\parser.zip')
        self.assertEqual(0, response.status_code)
        self.assertEqual('', response.std_err)

