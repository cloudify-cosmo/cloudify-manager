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

import getpass
import unittest
import time
import os
from os import path
from worker_installer.utils import FabricRunner
from worker_installer.tests import \
    id_generator, get_local_context, \
    get_remote_context, VAGRANT_MACHINE_IP, MANAGER_IP

from cloudify.constants import MANAGER_FILE_SERVER_BLUEPRINTS_ROOT_URL_KEY
from cloudify.constants import MANAGER_FILE_SERVER_URL_KEY
# from cloudify.tests.file_server import PORT

from celery import Celery
from worker_installer import tasks as t
from cloudify import manager


# agent is created and served via python simple http server when
# tests run in travis.
FILE_SERVER = 'http://localhost:8000'
AGENT_PACKAGE_URL = '{0}/Ubuntu-agent.tar.gz'.format(FILE_SERVER)
DISABLE_REQUIRETTY_SCRIPT_URL = '{0}/plugins/agent-installer/worker_installer/tests/Ubuntu-disable-require-tty.sh'.format(FILE_SERVER)  # NOQA
MOCK_SUDO_PLUGIN_INCLUDE = 'sudo_plugin.sudo'
os.environ[MANAGER_FILE_SERVER_URL_KEY] = FILE_SERVER
os.environ[MANAGER_FILE_SERVER_BLUEPRINTS_ROOT_URL_KEY] = FILE_SERVER  # NOQA


def _get_custom_agent_package_url(distro):
    return AGENT_PACKAGE_URL


def _get_custom_disable_requiretty_script_url(distro):
    return DISABLE_REQUIRETTY_SCRIPT_URL


def _get_custom_celery_includes_list():
    includes_list = t.CELERY_INCLUDES_LIST[:]
    includes_list.append(MOCK_SUDO_PLUGIN_INCLUDE)
    return includes_list


def _extract_registered_plugins(worker_name):

    # c = Celery(broker=broker_url, backend=broker_url)
    broker_url = 'amqp://guest:guest@localhost:5672//'
    c = Celery(broker=broker_url, backend=broker_url)
    tasks = c.control.inspect.registered(c.control.inspect())

    # retry a few times
    attempt = 0
    while tasks is None and attempt <= 3:
        tasks = c.control.inspect.registered(c.control.inspect())
        attempt += 1
        time.sleep(3)
    if tasks is None:
        return set()

    plugins = set()
    full_worker_name = "celery.{0}".format(worker_name)
    if full_worker_name in tasks:
        worker_tasks = tasks.get(full_worker_name)
        for worker_task in worker_tasks:
            plugin_name = worker_task.split('.')[0]
            full_plugin_name = '{0}@{1}'.format(worker_name, plugin_name)
            plugins.add(full_plugin_name)
    return plugins


def read_file(file_name):
    file_path = path.join(path.dirname(__file__), file_name)
    with open(file_path, 'r') as f:
        return f.read()


def get_resource(resource_name):
    if 'celeryd-cloudify.init' in resource_name:
        return read_file('Ubuntu-celeryd-cloudify.init.jinja2')
    elif 'celeryd-cloudify.conf' in resource_name:
        return read_file('Ubuntu-celeryd-cloudify.conf.jinja2')
    return None


class WorkerInstallerTestCase(unittest.TestCase):

    def assert_installed_plugins(self, ctx):
        worker_name = ctx.properties['cloudify_agent']['name']
        ctx.logger.info("extracting plugins from newly installed worker")
        plugins = _extract_registered_plugins(worker_name)
        if not plugins:
            raise AssertionError(
                "No plugins were detected on the installed worker")
        ctx.logger.info("Detected plugins : {0}".format(plugins))
        # check built in agent plugins are registered
        self.assertTrue(
            '{0}@plugin_installer'.format(worker_name) in plugins)
        self.assertTrue(
            '{0}@worker_installer'.format(worker_name) in plugins)


class TestRemoteInstallerCase(WorkerInstallerTestCase):

    VM_ID = "TestRemoteInstallerCase"
    RAN_ID = id_generator(3)

    @classmethod
    def setUpClass(cls):
        os.environ['MANAGEMENT_USER'] = 'vagrant'
        os.environ['MANAGER_REST_PORT'] = '8100'
        os.environ['MANAGEMENT_IP'] = MANAGER_IP
        os.environ['AGENT_IP'] = VAGRANT_MACHINE_IP
        manager.get_resource = get_resource
        t.get_agent_package_url = _get_custom_agent_package_url
        t.get_disable_requiretty_script_url = \
            _get_custom_disable_requiretty_script_url()
        t.get_celery_includes_list = _get_custom_celery_includes_list
        from vagrant_helper import launch_vagrant
        launch_vagrant(cls.VM_ID, cls.RAN_ID)

    @classmethod
    def tearDownClass(cls):
        from vagrant_helper import terminate_vagrant
        terminate_vagrant(cls.VM_ID, cls.RAN_ID)

    def test_install_vm_worker(self):
        ctx = get_remote_context()

        t.install(ctx)
        t.start(ctx)

        self.assert_installed_plugins(ctx)

    def test_install_same_worker_twice(self):
        ctx = get_remote_context()

        t.install(ctx)
        t.start(ctx)

        t.install(ctx)
        t.start(ctx)

        self.assert_installed_plugins(ctx)

    def test_install_multiple_workers(self):
        ctx1 = get_remote_context()
        ctx2 = get_remote_context()

        # install first worker
        t.install(ctx1)
        t.start(ctx1)

        # install second worker
        t.install(ctx2)
        t.start(ctx2)

        self.assert_installed_plugins(ctx1)
        self.assert_installed_plugins(ctx2)

    def test_remove_worker(self):
        ctx = get_remote_context()

        # install first worker
        t.install(ctx)
        t.start(ctx)
        t.stop(ctx)
        t.uninstall(ctx)

        agent_config = ctx.properties['cloudify_agent']

        plugins = _extract_registered_plugins(agent_config['name'])
        # make sure the worker has stopped
        self.assertEqual(0, len(plugins))

        # make sure files are deleted
        service_file_path = "/etc/init.d/celeryd-{0}".format(
            agent_config['name'])
        defaults_file_path = "/etc/default/celeryd-{0}".format(
            agent_config['name'])
        worker_home = agent_config['base_dir']

        runner = FabricRunner(agent_config)

        self.assertFalse(runner.exists(service_file_path))
        self.assertFalse(runner.exists(defaults_file_path))
        self.assertFalse(runner.exists(worker_home))

    def test_uninstall_non_existing_worker(self):
        ctx = get_remote_context()
        t.uninstall(ctx)

    def test_stop_non_existing_worker(self):
        ctx = get_remote_context()
        t.stop(ctx)


class TestLocalInstallerCase(WorkerInstallerTestCase):

    @classmethod
    def setUpClass(cls):
        os.environ['MANAGEMENT_USER'] = getpass.getuser()
        os.environ['MANAGER_REST_PORT'] = '8100'
        os.environ['MANAGEMENT_IP'] = 'localhost'
        os.environ['AGENT_IP'] = 'localhost'
        manager.get_resource = get_resource
        t.get_agent_package_url = _get_custom_agent_package_url
        t.get_disable_requiretty_script_url = \
            _get_custom_disable_requiretty_script_url
        t.get_celery_includes_list = _get_custom_celery_includes_list

    def test_install_worker(self):
        ctx = get_local_context()
        t.install(ctx)
        t.start(ctx)
        self.assert_installed_plugins(ctx)

    def test_install_same_worker_twice(self):
        ctx = get_local_context()
        t.install(ctx)
        t.start(ctx)

        t.install(ctx)
        t.start(ctx)

        self.assert_installed_plugins(ctx)

    def test_remove_worker(self):
        ctx = get_local_context()

        t.install(ctx)
        t.start(ctx)
        t.stop(ctx)
        t.uninstall(ctx)

        agent_config = ctx.properties['cloudify_agent']

        plugins = _extract_registered_plugins(agent_config['name'])
        # make sure the worker has stopped
        self.assertEqual(0, len(plugins))

        # make sure files are deleted
        service_file_path = "/etc/init.d/celeryd-{0}".format(
            agent_config['name'])
        defaults_file_path = "/etc/default/celeryd-{0}".format(
            agent_config['name'])
        worker_home = agent_config['base_dir']

        runner = FabricRunner(ctx, agent_config)

        self.assertFalse(runner.exists(service_file_path))
        self.assertFalse(runner.exists(defaults_file_path))
        self.assertFalse(runner.exists(worker_home))

    def test_uninstall_non_existing_worker(self):
        ctx = get_local_context()
        t.uninstall(ctx)

    def test_stop_non_existing_worker(self):
        ctx = get_local_context()
        t.stop(ctx)

    def test_install_worker_with_sudo_plugin(self):
        ctx = get_local_context()
        t.install(ctx)
        t.start(ctx)
        self.assert_installed_plugins(ctx)

        broker_url = 'amqp://guest:guest@localhost:5672//'
        c = Celery(broker=broker_url, backend=broker_url)
        kwargs = {'command': 'ls -l'}
        result = c.send_task(name='sudo_plugin.sudo.run',
                             kwargs=kwargs,
                             queue=ctx.properties['cloudify_agent']['name'])
        self.assertRaises(Exception, result.get, timeout=10)
        ctx = get_local_context()
        ctx.properties['cloudify_agent']['disable_requiretty'] = True
        t.install(ctx)
        t.start(ctx)
        self.assert_installed_plugins(ctx)

        broker_url = 'amqp://guest:guest@localhost:5672//'
        c = Celery(broker=broker_url, backend=broker_url)
        kwargs = {'command': 'ls -l'}
        result = c.send_task(name='sudo_plugin.sudo.run',
                             kwargs=kwargs,
                             queue=ctx.properties['cloudify_agent']['name'])
        result.get(timeout=10)

    def test_get_agent_resource_url(self):
        ctx = get_local_context()
        ctx.properties['cloudify_agent'].update({'distro': 'Ubuntu'})
        t.AGENT_RESOURCES.update(
            {'agent_package_path': '/Ubuntu-agent.tar.gz'})
        p = t.get_agent_resource_url(
            ctx, ctx.properties['cloudify_agent'], 'agent_package_path')
        self.assertEquals(p, AGENT_PACKAGE_URL)

    def test_get_agent_missing_resource(self):
        ctx = get_local_context()
        ctx.properties['cloudify_agent'].update({'distro': 'Ubuntu'})
        t.AGENT_RESOURCES.update(
            {'agent_package_path': '/MISSING_RESOURCE.file'})
        p = t.get_agent_resource_url(
            ctx, ctx.properties['cloudify_agent'], 'agent_package_path')
        self.assertEquals(p, None)

    def test_get_agent_missing_resource_origin(self):
        ctx = get_local_context()
        ctx.properties['cloudify_agent'].update({'distro': 'Ubuntu'})
        self.assertRaises(
            KeyError, t.get_agent_resource_url, ctx,
            ctx.properties['cloudify_agent'], 'nonexisting_resource_key')


if __name__ == '__main__':
    unittest.main()
