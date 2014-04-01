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
from os import path
from worker_installer import init_worker_installer
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
