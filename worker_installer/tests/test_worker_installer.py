import getpass

__author__ = 'elip'

import os
import tempfile

from celery import Celery

from worker_installer.tasks import install
from worker_installer.tasks import create_namespace_path
from worker_installer.tests import get_remote_runner, get_local_runner, VAGRANT_MACHINE_IP


PLUGIN_INSTALLER = 'cloudify.tosca.artifacts.plugin.plugin_installer'


def _extract_registered_plugins(borker_url):

    c = Celery(broker=borker_url, backend=borker_url)
    tasks = c.control.inspect.registered(c.control.inspect())
    print "tasks = {0}".format(tasks)

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

    __cloudify_id = "management_host"

    # this should install the plugin installer inside the celery worker
    install(worker_config, __cloudify_id, cloudify_runtime, local=local)

    # lets make sure it did
    plugins = _extract_registered_plugins(worker_config['broker'])
    print plugins
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


class TestRemoteInstallerCase:

    VM_ID = "TestRemoteInstallerCase"
    RUNNER = None

    @classmethod
    def setup_class(cls):
        from vagrant_helper import launch_vagrant
        launch_vagrant(cls.VM_ID)
        cls.RUNNER = get_remote_runner()

    @classmethod
    def teardown_class(cls):
        from vagrant_helper import terminate_vagrant
        terminate_vagrant(cls.VM_ID)

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


class TestLocalInstallerCase:

    RUNNER = None

    @classmethod
    def setup_class(cls):
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