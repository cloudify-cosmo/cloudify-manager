import getpass
import json
import os
import platform
import shutil
import subprocess
import tempfile
import time
import uuid

import unittest as unittest

from celery import Celery

from cloudify.celery import celery
from cloudify.mocks import MockCloudifyContext
from cloudify.state import current_ctx
from cloudify.utils import setup_logger, LocalCommandRunner

from cloudify_agent.api import defaults
from cloudify_agent.installer.config import configuration as agent_config


_PACKAGE_URL = ('http://46.101.245.114/cfy/konrad/'
                'ubuntu-{0}-agent-snapshots-freeze-33m5.tar.gz')
_INSTALL_SCRIPT_PATH = 'resources/rest-service/cloudify/install_agent.py'


def with_agent(f):
    def wrapper(self, **kwargs):
        agent = self.get_agent()
        try:
            f(self, agent, **kwargs)
        finally:
            self.cleanup_agent(agent)
    wrapper.__name__ = f.__name__
    return wrapper


class InstallerTestBase(unittest.TestCase):

    def setUp(self):
        self.logger = setup_logger('InstallerTest')
        current_ctx.set(MockCloudifyContext())
        self.runner = LocalCommandRunner(self.logger)
        self.base_dir = tempfile.mkdtemp()
        self.logger.info('Base dir: {0}'.format(self.base_dir))
        fd, self.script_path = tempfile.mkstemp(dir=self.base_dir,
                                                suffix='.py')
        os.close(fd)
        repo_path = os.environ['REPOSITORY_PATH']
        repo_script = os.path.join(repo_path, _INSTALL_SCRIPT_PATH)
        shutil.copyfile(repo_script, self.script_path)

    def tearDown(self):
        shutil.rmtree(self.base_dir)

    def get_agent(self):
        _, _, dist = platform.dist()
        package = _PACKAGE_URL.format(dist)
        self.logger.info('Package url: {0}'.format(package))
        result = {
            'local': True,
            'package_url': _PACKAGE_URL.format(dist),
            'user': getpass.getuser(),
            'basedir': self.base_dir,
            'manager_ip': '127.0.0.1',
            'name': 'agent_{0}'.format(uuid.uuid4()),
            'broker_url': 'amqp://'
        }
        agent_config.prepare_connection(result)
        # We specify base_dir and user directly, so runner is not needed.
        agent_config.prepare_agent(result, None)
        fd, agent_file_path = tempfile.mkstemp(dir=self.base_dir)
        os.close(fd)
        with open(agent_file_path, 'a') as agent_file:
            agent_file.write(json.dumps(result))
        result['agent_file'] = agent_file_path
        return result

    def cleanup_agent(self, agent):
        os.remove(agent['agent_file'])

    def call(self, operation, agent):
        agent_config_path = agent['agent_file']
        command = ('python {0} --operation={1} --config={2} '
                   '--ignore-result').format(
            self.script_path,
            operation,
            agent_config_path)
        self.logger.info('Calling: "{0}"'.format(command))
        self.runner.run(command)


class SingleWorkerInstallerTest(InstallerTestBase):

    @with_agent
    def test_installer(self, agent):
        worker_name = 'celery@{0}'.format(agent['name'])
        inspect = celery.control.inspect(destination=[worker_name])
        self.assertFalse(inspect.active())
        self.call('install', agent)
        self.assertTrue(inspect.active())
        self.call('uninstall', agent)
        self.assertFalse(inspect.active())


class DoubleWorkerInstallerTest(InstallerTestBase):

    def setUp(self):
        super(DoubleWorkerInstallerTest, self).setUp()
        self.server = subprocess.Popen(
            ['python', '-m', 'SimpleHTTPServer', '8000'],
            cwd=self.base_dir)
        # Wait for http server to start:
        time.sleep(1)

    def tearDown(self):
        self.server.kill()
        self.server.communicate()
        super(DoubleWorkerInstallerTest, self).tearDown()

    @with_agent
    def test_double_installer(self, agent):

        @with_agent
        def _double_agents_test(self, agent, parent_agent):
            parent_name = 'celery@{0}'.format(parent_agent['name'])
            inspect = celery.control.inspect(destination=[parent_name])
            self.assertFalse(inspect.active())
            self.call('install', parent_agent)
            self.assertTrue(inspect.active())
            self.logger.info('Agent {0} active.'.format(parent_agent['name']))
            try:
                # Must end with .py:
                installer_name = 'installer.py'
                output = os.path.join(self.base_dir, installer_name)
                shutil.copyfile(self.script_path, output)
                worker_name = 'celery@{0}'.format(agent['name'])
                worker_inspect = celery.control.inspect(
                    destination=[worker_name])
                self.assertFalse(worker_inspect.active())
                celery_app = Celery(broker='amqp://', backend='amqp://')
                task_expire = defaults.CELERY_TASK_RESULT_EXPIRES
                celery_app.conf.update(
                    CELERY_TASK_RESULT_EXPIRES=task_expire)
                self.logger.info('Sending installer task')
                self.logger.info('Url: {0}'.format(
                    'http://localhost:8000/{0}'.format(installer_name)))
                result = celery_app.send_task(
                    'script_runner.tasks.run',
                    args=['http://localhost:8000/{0}'.format(installer_name)],
                    kwargs={'cloudify_agent': agent},
                    queue=parent_agent['queue'])
                result.get(timeout=600)
                self.assertTrue(worker_inspect.active())
                self.logger.info('Inner agent {0} active.'.format(
                    agent['name']))
                self.call('uninstall', agent)
                self.assertFalse(worker_inspect.active())
            finally:
                self.call('uninstall', parent_agent)
                self.assertFalse(inspect.active())
        _double_agents_test(self, parent_agent=agent)
