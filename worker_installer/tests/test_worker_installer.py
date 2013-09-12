import getpass
import random
import string
import unittest

__author__ = 'elip'

import os
import tempfile

from celery import Celery

from worker_installer.tasks import install, start, build_env_string
from worker_installer.tasks import create_namespace_path
from worker_installer.tests import get_remote_runner, get_local_runner, VAGRANT_MACHINE_IP
from worker_installer.tests import get_logger

PLUGIN_INSTALLER = 'cloudify.tosca.artifacts.plugin.plugin_installer'

remote_suite_logger = get_logger("TestRemoteInstallerCase")
local_suite_logger = get_logger("TestLocalInstallerCase")


def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for x in range(size))


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


def _test_install(worker_config, cloudify_runtime, local=False):

    logger = remote_suite_logger
    if local:
        logger = local_suite_logger

    __cloudify_id = "management_host"

    # this should install the plugin installer inside the celery worker

    logger.info("installing worker {0} with id {1}. local={2}".format(worker_config, __cloudify_id, local))
    install(worker_config, __cloudify_id, cloudify_runtime, local=local)

    logger.info("starting worker {0} with id {1}. local={2}".format(worker_config, __cloudify_id, local))
    start(worker_config, cloudify_runtime, local=local)

    # lets make sure it did
    logger.info("extracting plugins from newly installed worker")
    plugins = _extract_registered_plugins(worker_config['broker'])
    if plugins is None:
        raise AssertionError("No plugins were detected on the installed worker")
    assert 'celery.{0}@cloudify.tosca.artifacts.plugin.plugin_installer'.format(__cloudify_id) in plugins


def _test_create_namespace_path(runner):

    base_dir = tempfile.NamedTemporaryFile().name

    namespace_parts = ["cloudify", "tosca", "artifacts", "plugin"]
    create_namespace_path(runner, namespace_parts, base_dir)

    # lets make sure the correct strcture was created
    namespace_path = base_dir
    for folder in namespace_parts:
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

    def test_install(self):

        worker_config = {
            "user": "vagrant",
            "port": 22,
            "key": "~/.vagrant.d/insecure_private_key",
            "management_ip": VAGRANT_MACHINE_IP,
            "broker": "amqp://guest:guest@10.0.0.1:5672//"
        }

        cloudify_runtime = {
            "test_id": {
                "ip": VAGRANT_MACHINE_IP
            }
        }

        _test_install(worker_config, cloudify_runtime)

    def test_create_namespace_path(self):

        _test_create_namespace_path(self.RUNNER)


class TestLocalInstallerCase(unittest.TestCase):

    RUNNER = None

    @classmethod
    def setUpClass(cls):
        cls.RUNNER = get_local_runner()

    def test_install(self):

        # no need to specify port and key file. we are installing locally
        local_ip = "127.0.0.1"

        worker_config = {
            "user": getpass.getuser(),
            "management_ip": local_ip,
            "broker": "amqp://"
        }

        cloudify_runtime = {
            "test_id": {
                "ip": local_ip
            }
        }

        _test_install(worker_config, cloudify_runtime, True)

    def test_create_namespace_path(self):

        _test_create_namespace_path(self.RUNNER)

    def test_create_env_string(self):
        env = {
            "TEST_KEY1": "TEST_VALUE2",
            "TEST_KEY2": "TEST_VALUE2"
        }

        expected_string = "TEST_KEY2=TEST_VALUE2\nTEST_KEY1=TEST_VALUE2\n"

        assert expected_string == build_env_string(env)


if __name__ == '__main__':
    unittest.main()