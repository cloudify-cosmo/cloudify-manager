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
import time

from worker_installer.tests import get_logger, get_remote_runner, get_local_runner, id_generator, remote_worker_config, remote_cloudify_runtime, local_cloudify_runtime, local_worker_config


__author__ = 'elip'

import os

from celery import Celery

from worker_installer.tasks import install, start, build_env_string

logger = get_logger("test_worker_installer")


def _extract_registered_plugins(broker_url):

    c = Celery(broker=broker_url, backend=broker_url)
    logger.info("Querying celery for registered tasks")
    tasks = c.control.inspect.registered(c.control.inspect())

    # retry a few times
    attempt = 0
    while tasks is None and attempt <= 3:
        logger.info("Could not find tasks. Querying celery again for registered tasks")
        tasks = c.control.inspect.registered(c.control.inspect())
        attempt += 1
        time.sleep(3)
    if tasks is None:
        return set()

    plugins = set()
    for node, node_tasks in tasks.items():
        for task in node_tasks:
            plugin_name = task.split('.')[0]
            full_plugin_name = '{0}@{1}'.format(node, plugin_name)
            plugins.add(full_plugin_name)
    return plugins


def _test_install(worker_config, cloudify_runtime, local=False):

    __cloudify_id = "management_host"

    # this should install the plugin installer inside the celery worker

    logger.info("installing worker {0} with id {1}. local={2}".format(worker_config, __cloudify_id, local))
    install(worker_config, __cloudify_id, cloudify_runtime, local=local)

    logger.info("starting worker {0} with id {1}. local={2}".format(worker_config, __cloudify_id, local))
    start(worker_config, cloudify_runtime, __cloudify_id, local=local)

    # lets make sure it did
    logger.info("extracting plugins from newly installed worker")
    plugins = _extract_registered_plugins(worker_config['env']['BROKER_URL'])
    if not plugins:
        raise AssertionError("No plugins were detected on the installed worker")

    logger.info("Detected plugins : {0}".format(plugins))

    # check built in agent plugins are registered
    assert 'celery.{0}@plugin_installer'.format(__cloudify_id) in plugins
    assert 'celery.{0}@kv_store'.format(__cloudify_id) in plugins


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
        _test_install(remote_worker_config, remote_cloudify_runtime, local=False)


class TestLocalInstallerCase(unittest.TestCase):

    RUNNER = None

    @classmethod
    def setUpClass(cls):
        cls.RUNNER = get_local_runner()
        os.environ["BROKER_URL"] = "localhost"
        os.environ["MANAGEMENT_IP"] = "localhost"

    def test_install_worker(self):
        _test_install(local_worker_config, local_cloudify_runtime, local=True)

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

if __name__ == '__main__':
    unittest.main()