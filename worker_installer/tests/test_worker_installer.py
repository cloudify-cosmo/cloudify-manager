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

import unittest
from worker_installer.tests import get_logger, get_remote_runner, get_local_runner, id_generator, remote_worker_config, remote_cloudify_runtime, local_cloudify_runtime, local_worker_config

__author__ = 'elip'

import os
import tempfile

from celery import Celery

from worker_installer.tasks import install, start, build_env_string
from worker_installer.tasks import create_namespace_path
from cloudify.constants import COSMO_PLUGIN_NAMESPACE

PLUGIN_INSTALLER = 'cloudify.plugins.plugin_installer'

remote_suite_logger = get_logger("TestRemoteInstallerCase")
local_suite_logger = get_logger("TestLocalInstallerCase")


def _extract_registered_plugins(borker_url):

    c = Celery(broker=borker_url, backend=borker_url)
    tasks = c.control.inspect.registered(c.control.inspect())
    if tasks is None:
        return set()

    plugins = set()
    for node, node_tasks in tasks.items():
        for task in node_tasks:
            plugin_name_split = task.split('.')[:-1]
            if not plugin_name_split[0] == 'cosmo':
                continue
            if not plugin_name_split[-1] == 'tasks':
                continue
            plugin_name = '.'.join(plugin_name_split[1:-1])
            full_plugin_name = '{0}@{1}'.format(node, plugin_name)
            plugins.add(full_plugin_name)
    return list(plugins)


def _test_install(runner, worker_config, cloudify_runtime, local=False, virtualenv=False):

    logger = remote_suite_logger
    if local:
        logger = local_suite_logger

    try:
        # try and stop any celery processes that may have started due to other tests.
        runner.sudo("service celeryd stop")
    except BaseException as e:
        logger.warning("Failed to stop celery process : {0}".format(e.message))

    __cloudify_id = "management_host"

    # this should install the plugin installer inside the celery worker

    logger.info("installing worker {0} with id {1}. local={2}".format(worker_config, __cloudify_id, local))
    install(worker_config, __cloudify_id, cloudify_runtime, local=local, virtualenv=virtualenv)

    logger.info("starting worker {0} with id {1}. local={2}".format(worker_config, __cloudify_id, local))
    start(worker_config, cloudify_runtime, local=local)

    # lets make sure it did
    logger.info("extracting plugins from newly installed worker")
    plugins = _extract_registered_plugins(worker_config['broker'])
    if plugins is None:
        raise AssertionError("No plugins were detected on the installed worker")
    assert 'celery.{0}@cloudify.plugins.plugin_installer'.format(__cloudify_id) in plugins


def _test_create_namespace_path(runner):

    base_dir = tempfile.NamedTemporaryFile().name

    create_namespace_path(runner, COSMO_PLUGIN_NAMESPACE, base_dir)

    # lets make sure the correct strcture was created
    namespace_path = base_dir
    for folder in COSMO_PLUGIN_NAMESPACE:
        namespace_path = os.path.join(namespace_path, folder)
        init_data = runner.get(os.path.join(namespace_path,  "__init__.py"))
        # we create empty init files
        assert init_data == "\n"


class TestRemoteInstallerCase(unittest.TestCase):

    VM_ID = "TestRemoteInstallerCase"
    RUNNER = None
    RAN_ID = id_generator(3)

    @classmethod
    def setUpClass(cls):
        from vagrant_helper import launch_vagrant
        launch_vagrant(cls.VM_ID, cls.RAN_ID)
        cls.RUNNER = get_remote_runner()

    @classmethod
    def tearDownClass(cls):
        from vagrant_helper import terminate_vagrant
        terminate_vagrant(cls.VM_ID, cls.RAN_ID)

    def test_install_worker(self):
        _test_install(self.RUNNER, remote_worker_config, remote_cloudify_runtime, local=False, virtualenv=False)

    def test_create_namespace_path(self):
        _test_create_namespace_path(self.RUNNER)

    def test_install_virtual_env(self):
        _test_install(self.RUNNER, remote_worker_config, remote_cloudify_runtime, local=False, virtualenv=True)


class TestLocalInstallerCase(unittest.TestCase):

    RUNNER = None

    @classmethod
    def setUpClass(cls):
        cls.RUNNER = get_local_runner()
        os.environ["BROKER_URL"] = "localhost"
        os.environ["MANAGEMENT_IP"] = "localhost"

    def test_install_worker(self):
        _test_install(self.RUNNER, local_worker_config, local_cloudify_runtime, local=True, virtualenv=False)

    def test_create_namespace_path(self):
        _test_create_namespace_path(self.RUNNER)

    def test_create_env_string(self):
        env = {
            "TEST_KEY1": "TEST_VALUE1",
            "TEST_KEY2": "TEST_VALUE2"
        }

        expected_string = "export TEST_KEY2=\"TEST_VALUE2\"\nexport TEST_KEY1=\"TEST_VALUE1\"\n"

        assert expected_string == build_env_string(env)

    def test_create_empty_env_string(self):

        expected_string = ""

        assert expected_string == build_env_string({})

    def test_install_virtual_env(self):
        _test_install(self.RUNNER, local_worker_config, local_cloudify_runtime, local=True, virtualenv=True)

if __name__ == '__main__':
    unittest.main()