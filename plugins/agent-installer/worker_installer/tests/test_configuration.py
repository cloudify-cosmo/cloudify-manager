#########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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

__author__ = 'idanmo'

import unittest
import os
import getpass
from os import path
from worker_installer import init_worker_installer
from worker_installer import DEFAULT_MIN_WORKERS, DEFAULT_MAX_WORKERS
from worker_installer import FabricRunner
from worker_installer.tasks import create_celery_configuration
# from worker_installer.tasks import CELERY_INIT_PATH, CELERY_CONFIG_PATH
from cloudify.mocks import MockCloudifyContext
from cloudify.context import BootstrapContext
from cloudify.exceptions import NonRecoverableError


# for tests purposes, need a path to a file which will always exist
KEY_FILE_PATH = '/var/log/syslog'


@init_worker_installer
def m(ctx, runner, agent_config, **kwargs):
    return agent_config


class CeleryWorkerConfigurationTest(unittest.TestCase):

    def setUp(self):
        os.environ['MANAGEMENT_USER'] = getpass.getuser()

    def test_deployment_config(self):
        ctx = MockCloudifyContext(deployment_id='deployment_id')
        conf = m(ctx)
        self.assertTrue('base_dir' in conf)
        self.assertTrue('init_file' in conf)
        self.assertTrue('config_file' in conf)

    def test_vm_config_validation(self):
        ctx = MockCloudifyContext(node_id='node',
                                  properties={'cloudify_agent': {
                                      'distro': 'Ubuntu', }})
        self.assertRaises(NonRecoverableError, m, ctx)
        ctx = MockCloudifyContext(node_id='node',
                                  properties={'cloudify_agent': {
                                      'distro': 'Ubuntu'},
                                      'ip': '192.168.0.1'
                                  })
        self.assertRaises(NonRecoverableError, m, ctx)
        ctx = MockCloudifyContext(node_id='node',
                                  properties={
                                      'cloudify_agent': {
                                          'distro': 'Ubuntu',
                                          'user': getpass.getuser()},
                                      'ip': '192.168.0.1'
                                  })
        self.assertRaises(NonRecoverableError, m, ctx)
        ctx = MockCloudifyContext(node_id='node',
                                  properties={
                                      'cloudify_agent': {
                                          'user': getpass.getuser(),
                                          'key': KEY_FILE_PATH,
                                          'distro': 'Ubuntu',
                                      },
                                      'ip': '192.168.0.1'
                                  })
        m(ctx)

    def test_agent_config(self):
        node_id = 'node_id'
        ctx = MockCloudifyContext(
            deployment_id='test',
            node_id=node_id,
            runtime_properties={
                'ip': '192.168.0.1'
            },
            properties={
                'cloudify_agent': {
                    'user': getpass.getuser(),
                    'key': KEY_FILE_PATH,
                    'distro': 'Ubuntu',
                }
            }
        )
        conf = m(ctx)
        self.assertTrue('base_dir' in conf)
        self.assertTrue('init_file' in conf)
        self.assertTrue('config_file' in conf)
        self.assertTrue('includes_file' in conf)

    def test_disable_requiretty_config(self):
        self._test_disable_requiretty_config('true', True)
        self._test_disable_requiretty_config('false', False)
        self._test_disable_requiretty_config('true', True)
        self._test_disable_requiretty_config('true', True)
        self._test_disable_requiretty_config(True, True)
        self._test_disable_requiretty_config(False, False)
        self._test_disable_requiretty_config(value=None,
                                             should_raise_exception=True)
        self._test_disable_requiretty_config(value='1234',
                                             should_raise_exception=True)

    def _test_disable_requiretty_config(self,
                                        value=None,
                                        expected=None,
                                        should_raise_exception=False):
        ctx = MockCloudifyContext(
            deployment_id='test',
            properties={
                'cloudify_agent': {
                    'disable_requiretty': value,
                    'distro': 'Ubuntu',
                }
            }
        )
        if should_raise_exception:
            self.assertRaises(NonRecoverableError, m, ctx)
        else:
            conf = m(ctx)
            self.assertEqual(expected, conf['disable_requiretty'])

    def test_autoscale_configuration(self):
        node_id = 'node_id'
        ctx = MockCloudifyContext(
            deployment_id='test',
            node_id=node_id,
            runtime_properties={
                'ip': '192.168.0.1'
            },
            properties={
                'cloudify_agent': {
                    'user': getpass.getuser(),
                    'key': KEY_FILE_PATH,
                    'distro': 'Ubuntu',
                }
            }
        )
        conf = m(ctx)
        self.assertEqual(conf['min_workers'], DEFAULT_MIN_WORKERS)
        self.assertEqual(conf['max_workers'], DEFAULT_MAX_WORKERS)
        ctx = MockCloudifyContext(
            deployment_id='test',
            node_id=node_id,
            runtime_properties={
                'ip': '192.168.0.1'
            },
            properties={
                'cloudify_agent': {
                    'user': getpass.getuser(),
                    'key': KEY_FILE_PATH,
                    'min_workers': 2,
                    'max_workers': 5,
                    'distro': 'Ubuntu',
                }
            }
        )
        conf = m(ctx)
        self.assertEqual(conf['min_workers'], 2)
        self.assertEqual(conf['max_workers'], 5)

    def test_illegal_autoscale_configuration(self):
        node_id = 'node_id'
        ctx = MockCloudifyContext(
            deployment_id='test',
            node_id=node_id,
            runtime_properties={
                'ip': '192.168.0.1'
            },
            properties={
                'cloudify_agent': {
                    'user': getpass.getuser(),
                    'key': KEY_FILE_PATH,
                    'min_workers': 10,
                    'max_workers': 5,
                    'distro': 'Ubuntu',
                }
            }
        )
        self.assertRaises(NonRecoverableError, m, ctx)
        ctx = MockCloudifyContext(
            deployment_id='test',
            node_id=node_id,
            runtime_properties={
                'ip': '192.168.0.1'
            },
            properties={
                'cloudify_agent': {
                    'user': getpass.getuser(),
                    'key': KEY_FILE_PATH,
                    'min_workers': 'aaa',
                    'max_workers': 5,
                    'distro': 'Ubuntu',
                }
            }
        )
        self.assertRaises(NonRecoverableError, m, ctx)

    def test_autoscale_from_bootstrap_context(self):
        node_id = 'node_id'
        ctx = MockCloudifyContext(
            deployment_id='test',
            node_id=node_id,
            runtime_properties={
                'ip': '192.168.0.1'
            },
            properties={
                'cloudify_agent': {
                    'user': getpass.getuser(),
                    'key': KEY_FILE_PATH,
                    'distro': 'Ubuntu',
                }
            },
            bootstrap_context=BootstrapContext({
                'cloudify_agent': {
                    'min_workers': 2,
                    'max_workers': 5,
                }
            })
        )
        conf = m(ctx)
        self.assertEqual(conf['min_workers'], 2)
        self.assertEqual(conf['max_workers'], 5)

    def test_key_from_bootstrap_context(self):
        node_id = 'node_id'
        ctx = MockCloudifyContext(
            deployment_id='test',
            node_id=node_id,
            runtime_properties={
                'ip': '192.168.0.1'
            },
            properties={
                'cloudify_agent': {
                    'user': getpass.getuser(),
                    'distro': 'Ubuntu',
                }
            },
            bootstrap_context=BootstrapContext({
                'cloudify_agent': {
                    'agent_key_path': KEY_FILE_PATH
                }
            })
        )
        conf = m(ctx)
        self.assertEqual(conf['key'], KEY_FILE_PATH)

    def test_user_from_bootstrap_context(self):
        node_id = 'node_id'
        ctx = MockCloudifyContext(
            deployment_id='test',
            node_id=node_id,
            runtime_properties={
                'ip': '192.168.0.1'
            },
            properties={
                'cloudify_agent': {
                    'distro': 'Ubuntu',
                },
            },
            bootstrap_context=BootstrapContext({
                'cloudify_agent': {
                    'agent_key_path': KEY_FILE_PATH,
                    'user': getpass.getuser()

                }
            })
        )
        conf = m(ctx)
        self.assertEqual(conf['user'], getpass.getuser())

    def test_ssh_port_default(self):
        node_id = 'node_id'
        ctx = MockCloudifyContext(
            deployment_id='test',
            node_id=node_id,
            runtime_properties={
                'ip': '192.168.0.1'
            },
            properties={
                'cloudify_agent': {
                    'distro': 'Ubuntu',
                },
            },
            bootstrap_context=BootstrapContext({
                'cloudify_agent': {
                    'agent_key_path': KEY_FILE_PATH,
                    'user': getpass.getuser(),
                }
            })
        )
        conf = m(ctx)
        self.assertEqual(conf['port'], 22)

    def test_ssh_port_from_bootstrap_context(self):
        node_id = 'node_id'
        ctx = MockCloudifyContext(
            deployment_id='test',
            node_id=node_id,
            runtime_properties={
                'ip': '192.168.0.1'
            },
            properties={
                'cloudify_agent': {
                    'distro': 'Ubuntu',
                },
            },
            bootstrap_context=BootstrapContext({
                'cloudify_agent': {
                    'agent_key_path': KEY_FILE_PATH,
                    'user': getpass.getuser(),
                    'remote_execution_port': 2222

                }
            })
        )
        conf = m(ctx)
        self.assertEqual(conf['port'], 2222)

    def test_ssh_port_from_config_override_bootstrap(self):
        node_id = 'node_id'
        ctx = MockCloudifyContext(
            deployment_id='test',
            node_id=node_id,
            runtime_properties={
                'ip': '192.168.0.1'
            },
            properties={
                'cloudify_agent': {
                    'distro': 'Ubuntu',
                    'port': 3333
                },
            },
            bootstrap_context=BootstrapContext({
                'cloudify_agent': {
                    'agent_key_path': KEY_FILE_PATH,
                    'user': getpass.getuser(),
                    'remote_execution_port': 2222
                }
            })
        )
        conf = m(ctx)
        self.assertEqual(conf['port'], 3333)

    def test_workflows_agent_config(self):
        ctx = MockCloudifyContext(
            deployment_id='test',
            properties={
                'cloudify_agent': {
                    'workflows_worker': 'true',
                    'distro': 'Ubuntu',
                }
            },
            runtime_properties={
                'ip': '192.168.0.1'
            }
        )
        conf = m(ctx)
        self.assertEqual(conf['name'], 'test_workflows')


class MockFabricRunner(FabricRunner):

    def __init__(self):
        self.put_files = {}

    def put(self, file_path, content, sudo=False):
        self.put_files[file_path] = content


class ConfigurationCreationTest(unittest.TestCase):

    def setUp(self):
        os.environ['MANAGEMENT_USER'] = getpass.getuser()
        os.environ['MANAGER_REST_PORT'] = '8100'
        os.environ['MANAGEMENT_IP'] = '192.168.0.1'
        os.environ['AGENT_IP'] = '192.168.0.2'

    def read_file(self, file_name):
        file_path = path.join(path.dirname(__file__), file_name)
        with open(file_path, 'r') as f:
            return f.read()

    def get_resource(self, resource_name):
        if 'celeryd-cloudify.init' in resource_name:
            return self.read_file('Ubuntu-celeryd-cloudify.init.jinja2')
        elif 'celeryd-cloudify.conf' in resource_name:
            return self.read_file('Ubuntu-celeryd-cloudify.conf.jinja2')
        return None

    def test_prepare_configuration(self):
        ctx = MockCloudifyContext(deployment_id='deployment_id')
        agent_config = m(ctx)
        runner = MockFabricRunner()
        create_celery_configuration(ctx,
                                    runner,
                                    agent_config,
                                    self.get_resource)
        self.assertEquals(3, len(runner.put_files))
        self.assertTrue(agent_config['init_file'] in runner.put_files)
        self.assertTrue(agent_config['config_file'] in runner.put_files)
        self.assertTrue(agent_config['includes_file'] in runner.put_files)
