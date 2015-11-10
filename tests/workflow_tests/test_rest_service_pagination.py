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

from testenv import TestCase
from testenv.utils import get_resource as resource
from testenv.utils import deploy, execute_workflow


class TestRestServiceListPagination(TestCase):

    def test_blueprints_pagination(self):
        for i in range(10):
            self.client.blueprints.upload(resource('dsl/pagination.yaml'),
                                          'blueprint{0}'.format(i))
        self._test_pagination(self.client.blueprints.list)

    def test_deployments_pagination(self):
        for i in range(10):
            deploy(resource('dsl/pagination.yaml'))
        self._test_pagination(self.client.deployments.list)

    def test_deployment_modifications_pagination(self):
        deployment = deploy(resource('dsl/pagination.yaml'))
        for i in range(2, 12):
            modification = self.client.deployment_modifications.start(
                deployment_id=deployment.id,
                nodes={'node': {'instances': i}})
            self.client.deployment_modifications.finish(modification.id)
        self._test_pagination(partial(
            self.client.deployment_modifications.list,
            deployment_id=deployment.id))

    def test_executions_pagination(self):
        deployment = deploy(resource('dsl/pagination.yaml'))
        for i in range(5):
            execute_workflow('install', deployment.id)
            execute_workflow('uninstall', deployment.id)
        self._test_pagination(partial(self.client.executions.list,
                                      deployment_id=deployment.id))

    def test_nodes_pagination(self):
        deployment = deploy(resource('dsl/pagination-nodes.yaml'))
        self._test_pagination(partial(self.client.nodes.list,
                                      deployment_id=deployment.id))

    def test_node_instances_pagination(self):
        deployment = deploy(resource('dsl/pagination-node-instances.yaml'))
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
        all_results = list_func().items
        num_all = len(all_results)
        # sanity
        self.assertGreaterEqual(num_all, 10)
        for offset in range(num_all + 1):
            for size in range(num_all + 1):
                response = list_func(_offset=offset, _size=size)
                self.assertEqual(response.metadata.pagination.total, num_all)
                self.assertEqual(response.metadata.pagination.offset, offset)
                self.assertEqual(response.metadata.pagination.size, size)
                self.assertEqual(response.items,
                                 all_results[offset:offset+size])
