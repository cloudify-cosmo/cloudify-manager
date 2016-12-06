########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import os
import tempfile
import shutil
from functools import partial

from wagon.wagon import Wagon

from manager_rest import config
from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource
from cloudify_rest_client.exceptions import CloudifyClientError


class TestRestServiceListPagination(AgentlessTestCase):
    @classmethod
    def setup_class(cls):
        super(TestRestServiceListPagination, cls).setUpClass()
        config.instance.max_results = 9
        TestRestServiceListPagination._update_config({'max_results': 9})

    def test_blueprints_pagination(self):
        for i in range(10):
            self.client.blueprints.upload(resource('dsl/pagination.yaml'),
                                          'blueprint{0}'.format(i))
        self._test_pagination(self.client.blueprints.list)

    def test_deployments_pagination(self):
        for i in range(10):
            self.deploy(resource('dsl/pagination.yaml'))
        self._test_pagination(self.client.deployments.list)

    def test_deployment_modifications_pagination(self):
        deployment = self.deploy(resource('dsl/pagination.yaml'))
        for i in range(2, 12):
            modification = self.client.deployment_modifications.start(
                deployment_id=deployment.id,
                nodes={'node': {'instances': i}})
            self.client.deployment_modifications.finish(modification.id)
        self._test_pagination(partial(
            self.client.deployment_modifications.list,
            deployment_id=deployment.id))

    def test_executions_pagination(self):
        deployment = self.deploy(resource('dsl/pagination.yaml'))
        for i in range(5):
            self.execute_workflow('install', deployment.id)
            self.execute_workflow('uninstall', deployment.id)
        self._test_pagination(partial(self.client.executions.list,
                                      deployment_id=deployment.id))

    def test_nodes_pagination(self):
        deployment = self.deploy(resource('dsl/pagination-nodes.yaml'))
        self._test_pagination(partial(self.client.nodes.list,
                                      deployment_id=deployment.id))

    def test_node_instances_pagination(self):
        deployment = self.deploy(
                resource('dsl/pagination-node-instances.yaml'))
        self._test_pagination(partial(
            self.client.node_instances.list,
                              deployment_id=deployment.id))

    def test_plugins_pagination(self):
        for i in range(1, 11):
            tmpdir = tempfile.mkdtemp(prefix='test-pagination-')
            with open(os.path.join(tmpdir, 'setup.py'), 'w') as f:
                f.write('from setuptools import setup\n')
                f.write('setup(name="some-package", version={0})'.format(i))
            wagon = Wagon(tmpdir)
            plugin_path = wagon.create(archive_destination_dir=tmpdir)
            self.client.plugins.upload(plugin_path)
            shutil.rmtree(tmpdir)
        self._test_pagination(self.client.plugins.list)

    def _test_pagination(self, list_func):
        self.assertRaisesRegexp(CloudifyClientError,
                                'Response size',
                                list_func)

        self.assertRaisesRegexp(CloudifyClientError,
                                'Invalid pagination size',
                                list_func,
                                _offset=0,
                                _size=20)

        all_results = list_func(_sort=['id'],
                                _offset=0,
                                _size=9).items
        num_all = len(all_results)
        self.assertGreaterEqual(num_all, 9)
        total = 10

        # sanity
        for offset in range(num_all + 1):
            # inside loop range should take into consideration
            # the fact that `all_results` is not the all results,
            # we used pagination..
            for size in range(num_all + 1 - offset):
                response = list_func(_offset=offset, _size=size, _sort=['id'])
                self.assertEqual(response.metadata.pagination.total, total)
                self.assertEqual(response.metadata.pagination.offset, offset)
                self.assertEqual(response.metadata.pagination.size, size)
                self.assertEqual(response.items,
                                 all_results[offset: offset + size])
