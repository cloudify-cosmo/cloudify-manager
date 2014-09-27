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

import unittest
import os
from mock import Mock
from nose.tools import nottest

from cloudify import constants
from cloudify.mocks import MockCloudifyContext
from cloudify.utils import setup_default_logger

from windows_agent_installer import tasks, WinRMRunner
from windows_agent_installer.tests import TEST_MACHINE_IP_ENV_VARIABLE
from windows_agent_installer.tasks import AGENT_INCLUDES
from windows_agent_installer.tests.test_winrm_runner import WinRMRunnerTest


PACKAGE_URL = 'https://dl.dropboxusercontent.com/u/3588656/Cloudify.exe'

logger = setup_default_logger('test_tasks')

# Configure mocks
tasks.get_agent_package_url = lambda: PACKAGE_URL
tasks.utils.get_manager_ip = lambda: 'localhost'
tasks.utils.get_manager_file_server_blueprints_root_url = lambda: 'localhost'
tasks.utils.get_manager_file_server_url = lambda: 'localhost'
tasks.utils.get_manager_rest_service_port = lambda: 8080

attempts = 0


def get_worker_stats(worker_name):
    logger.info('Retrieving worker {0} stats'
                .format(worker_name))
    global attempts
    if attempts == 3:
        return Mock()
    attempts += attempts
    return None
tasks.get_worker_stats = get_worker_stats


@nottest
class TestTasks(unittest.TestCase):

    """
    Test cases for the worker installer functionality.
    These tests run PowerShell commands remotely on a WinRM enabled server.

    An existing server must be setup, set the 'TEST_MACHINE_IP'
    environment variable to the server IP,
    otherwise an exception will be raised.

    Note: These tests require a machine with RabbitMQ
    running for the celery worker to start properly.
    """

    @staticmethod
    def _create_context(task_name):

        cloudify_agent = {
            'user': 'Administrator',
            'password': '1408Rokk'
        }

        properties = {
            'ip': os.environ[TEST_MACHINE_IP_ENV_VARIABLE],
            'cloudify_agent': cloudify_agent
        }

        return MockCloudifyContext(
            properties=properties,
            node_id='test-node-id',
            task_name=task_name
        )

    def setUp(self):

        os.environ[TEST_MACHINE_IP_ENV_VARIABLE] = '15.126.205.73'

        if TEST_MACHINE_IP_ENV_VARIABLE not in os.environ:
            raise RuntimeError('TEST_MACHINE_IP environment variable must '
                               'be set and point to an existing server with '
                               'WinRM configured properly')

        self.runner = WinRMRunner(
            session_config=WinRMRunnerTest._create_session()
        )

    def tearDown(self):
        try:
            tasks.stop(ctx=self._create_context('stop'))
        except BaseException as e:
            logger.error(e.message)
        try:
            tasks.uninstall(ctx=self._create_context('uninstall'))
        except BaseException as e:
            logger.warning(e.message)
            self.runner.delete(path=tasks.AGENT_FOLDER_NAME,
                               ignore_missing=True)
            self.runner.delete(
                path='C:\\{0}'.format(tasks.AGENT_EXEC_FILE_NAME),
                ignore_missing=True)

    def test_full_lifecycle(self):
        tasks.install(ctx=self._create_context('install'))
        tasks.start(ctx=self._create_context('start'))

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
        tasks.restart(ctx=self._create_context('restart'))

        # Stop the service
        tasks.stop(ctx=self._create_context('stop'))

        # Uninstall, delete the files
        tasks.uninstall(ctx=self._create_context('uninstall'))

        # Assert files are gone
        self.assertFalse(runner.exists(path=RUNTIME_AGENT_PATH))
        self.assertFalse(
            runner.exists(
                path='C:\{0}'.format(AGENT_EXEC_FILE_NAME)))

    def test_create_env_string(self):

        from windows_agent_installer.tasks import create_env_string

        cloudify_agent = {
            'host': '127.0.0.1'
        }
        import os
        os.environ[
            constants.MANAGER_FILE_SERVER_BLUEPRINTS_ROOT_URL_KEY
        ] = 'url1'
        os.environ[
            constants.MANAGER_FILE_SERVER_URL_KEY
        ] = 'url2'
        os.environ[
            constants.MANAGER_REST_PORT_KEY
        ] = '80'
        env_string = create_env_string(cloudify_agent)
        expected = 'AGENT_IP=127.0.0.1 MANAGEMENT_IP=127.0.0.1 ' \
                   'MANAGER_FILE_SERVER_BLUEPRINTS_ROOT_URL=url1 ' \
                   'MANAGER_FILE_SERVER_URL=url2 MANAGER_REST_PORT=80'
        self.assertEqual(env_string, expected)
