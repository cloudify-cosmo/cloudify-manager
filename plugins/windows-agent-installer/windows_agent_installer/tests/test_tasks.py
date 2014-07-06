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
import os

from nose.tools import nottest

from cloudify.mocks import MockCloudifyContext
from windows_agent_installer import tasks
from windows_agent_installer.tests import TEST_MACHINE_IP_ENV_VARIABLE
from windows_agent_installer.tasks import AGENT_INCLUDES


PACKAGE_URL = 'https://dl.dropboxusercontent.com/u/3588656/CloudifyAgent.exe'

# Configure mocks
tasks.get_agent_package_url = lambda: PACKAGE_URL
tasks.get_manager_ip = lambda: '127.0.0.1'


@nottest
class TestTasks(unittest.TestCase):

    """
    Test cases for the worker installer functionality..
    These tests run PowerShell commands remotely on a WinRM enabled server.

    An existing server must be setup, set the
    'TEST_MACHINE_IP' environment variable to the server IP.
    Otherwise, an exception will be raised.

    Note : These tests require a machine with RabbitMQ
    running for the celery worker to start properly.

    """

    ctx = None

    @classmethod
    def setUpClass(cls):

        if TEST_MACHINE_IP_ENV_VARIABLE not in os.environ:
            raise RuntimeError('TEST_MACHINE_IP environment variable must '
                               'be set and point to an existing server with '
                               'WinRM configured properly')
        cloudify_agent = {
            'user': 'Administrator',
            'password': '1408Rokk'
        }

        properties = {
            'ip': os.environ[TEST_MACHINE_IP_ENV_VARIABLE],
            'cloudify_agent': cloudify_agent
        }

        cls.ctx = MockCloudifyContext(
            properties=properties,
            node_id='test-node-id')

    def test_full_lifecycle(self):
        tasks.install(ctx=self.ctx)
        tasks.start(ctx=self.ctx)

        def _create_session():
            return {
                'host': os.environ[TEST_MACHINE_IP_ENV_VARIABLE],
                'user': 'Administrator',
                'password': '1408Rokk'
            }

        # Retrieve registered plugins
        from windows_agent_installer.winrm_runner import WinRMRunner
        from windows_agent_installer.tasks import RUNTIME_AGENT_PATH
        from windows_agent_installer.tasks import AGENT_EXEC_FILE_NAME
        runner = WinRMRunner(session_config=_create_session())
        response = runner.run(
            '{0}\Scripts\celery.exe inspect registered'
            .format(RUNTIME_AGENT_PATH))

        # Assert agent has necessary includes
        self.assertTrue(AGENT_INCLUDES in response.std_out)

        # Restart the service
        tasks.restart(ctx=self.ctx)

        # Stop the service
        tasks.stop(ctx=self.ctx)

        # Uninstall, delete the files
        tasks.uninstall(ctx=self.ctx)

        # Assert files are gone
        self.assertFalse(runner.exists(path=RUNTIME_AGENT_PATH))
        self.assertFalse(
            runner.exists(
                path='C:\{0}'.format(AGENT_EXEC_FILE_NAME)))
