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
from cloudify.context import BootstrapContext

__author__ = 'idanmo'

import unittest
import os
from os import path
from worker_installer import init_worker_installer
from worker_installer import DEFAULT_MIN_WORKERS, DEFAULT_MAX_WORKERS
from worker_installer import FabricRunner
from worker_installer.tasks import create_celery_configuration
from worker_installer.tasks import CELERY_INIT_PATH, CELERY_CONFIG_PATH
from cloudify.mocks import MockCloudifyContext


@init_worker_installer
def m(ctx, runner, worker_config, **kwargs):
    return worker_config


class CeleryWorkerConfigurationTest(unittest.TestCase):

    def setUp(self):
        os.environ['MANAGEMENT_USER'] = 'user'

    def test_deployment_config(self):
        ctx = MockCloudifyContext(deployment_id='deployment_id')
        conf = m(ctx)
        self.assertTrue('base_dir' in conf)
        self.assertTrue('init_file' in conf)
        self.assertTrue('config_file' in conf)

    def test_vm_config_validation(self):
        ctx = MockCloudifyContext(node_id='node',
                                  properties={'worker_config': {}})
        self.assertRaises(ValueError, m, ctx)
        ctx = MockCloudifyContext(node_id='node',
                                  properties={
                                      'worker_config': {},
                                      'ip': '192.168.0.1'
                                  })
        self.assertRaises(ValueError, m, ctx)
        ctx = MockCloudifyContext(node_id='node',
                                  properties={
                                      'worker_config': {'user': 'user'},
                                      'ip': '192.168.0.1'
                                  })
        self.assertRaises(ValueError, m, ctx)
        ctx = MockCloudifyContext(node_id='node',
                                  properties={
                                      'worker_config': {
                                          'user': 'user',
                                          'key': 'key.pem'
                                      },
                                      'ip': '192.168.0.1'
                                  })
        m(ctx)

    def test_worker_config(self):
        node_id = 'node_id'
        ctx = MockCloudifyContext(
            deployment_id='test',
            node_id=node_id,
            runtime_properties={
                'ip': '192.168.0.1'
            },
            properties={
                'worker_config': {
                    'user': 'user',
                    'key': 'key.pem'
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
                'worker_config': {
                    'disable_requiretty': value
                }
            }
        )
        if should_raise_exception:
            self.assertRaises(ValueError, m, ctx)
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
                'worker_config': {
                    'user': 'user',
                    'key': 'key.pem',
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
                'worker_config': {
                    'user': 'user',
                    'key': 'key.pem',
                    'min_workers': 2,
                    'max_workers': 5
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
                'worker_config': {
                    'user': 'user',
                    'key': 'key.pem',
                    'min_workers': 10,
                    'max_workers': 5
                }
            }
        )
        self.assertRaises(ValueError, m, ctx)
        ctx = MockCloudifyContext(
            deployment_id='test',
            node_id=node_id,
            runtime_properties={
                'ip': '192.168.0.1'
            },
            properties={
                'worker_config': {
                    'user': 'user',
                    'key': 'key.pem',
                    'min_workers': 'aaa',
                    'max_workers': 5
                }
            }
        )
        self.assertRaises(ValueError, m, ctx)

    def test_autoscale_from_bootstrap_context(self):
        node_id = 'node_id'
        ctx = MockCloudifyContext(
            deployment_id='test',
            node_id=node_id,
            runtime_properties={
                'ip': '192.168.0.1'
            },
            properties={
                'worker_config': {
                    'user': 'user',
                    'key': 'key.pem',
                }
            },
            bootstrap_context=BootstrapContext({
                'cloudify_agent': {
                    'min_workers': 2,
                    'max_workers': 5
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
                'worker_config': {
                    'user': 'user',
                }
            },
            bootstrap_context=BootstrapContext({
                'cloudify_agent': {
                    'agent_key_path': 'here'
                }
            })
        )
        conf = m(ctx)
        self.assertEqual(conf['key'], 'here')

    def test_user_from_bootstrap_context(self):
        node_id = 'node_id'
        ctx = MockCloudifyContext(
            deployment_id='test',
            node_id=node_id,
            runtime_properties={
                'ip': '192.168.0.1'
            },
            bootstrap_context=BootstrapContext({
                'cloudify_agent': {
                    'agent_key_path': 'here',
                    'user': 'john doe'

                }
            })
        )
        conf = m(ctx)
        self.assertEqual(conf['user'], 'john doe')

    def test_ssh_port_from_bootstrap_context(self):
        node_id = 'node_id'
        ctx = MockCloudifyContext(
            deployment_id='test',
            node_id=node_id,
            runtime_properties={
                'ip': '192.168.0.1'
            },
            bootstrap_context=BootstrapContext({
                'cloudify_agent': {
                    'agent_key_path': 'here',
                    'user': 'john doe',
                    'remote_execution_port': 2222

                }
            })
        )
        conf = m(ctx)
        self.assertEqual(conf['port'], 2222)

    def test_workflows_worker_config(self):
        ctx = MockCloudifyContext(
            deployment_id='test',
            properties={
                'worker_config': {
                    'workflows_worker': 'true'
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
        os.environ['MANAGEMENT_USER'] = 'user'
        os.environ['MANAGER_REST_PORT'] = '8100'
        os.environ['MANAGEMENT_IP'] = '192.168.0.1'
        os.environ['AGENT_IP'] = '192.168.0.2'

    def read_file(self, file_name):
        file_path = path.join(path.dirname(__file__), file_name)
        with open(file_path, 'r') as f:
            return f.read()

    def get_resource(self, resource_name):
        if CELERY_INIT_PATH in resource_name:
            return self.read_file('celeryd-cloudify.init.jinja2')
        elif CELERY_CONFIG_PATH in resource_name:
            return self.read_file('celeryd-cloudify.conf.jinja2')
        return None

    def test_prepare_configuration(self):
        ctx = MockCloudifyContext(deployment_id='deployment_id')
        worker_config = m(ctx)
        runner = MockFabricRunner()
        create_celery_configuration(ctx,
                                    runner,
                                    worker_config,
                                    self.get_resource)
        self.assertEquals(3, len(runner.put_files))
        self.assertTrue(worker_config['init_file'] in runner.put_files)
        self.assertTrue(worker_config['config_file'] in runner.put_files)
        self.assertTrue(worker_config['includes_file'] in runner.put_files)
