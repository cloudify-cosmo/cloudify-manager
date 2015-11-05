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

from wagon.wagon import Wagon

from testenv import TestCase
from testenv.utils import get_resource as resource
from testenv.utils import deploy, execute_workflow


class TestRestServiceListSort(TestCase):

    def test_blueprints_sort(self):
        for i in range(10):
            self.client.blueprints.upload(resource('dsl/sort.yaml'),
                                          'blueprint{0}'.format(i))
        self._test_sort('blueprints', '-id')

    def test_deployments_sort(self):
        for i in range(10):
            deploy(resource('dsl/sort.yaml'))
        self._test_sort('deployments', 'id')

    def test_deployment_modifications_sort(self):
        deployment = deploy(resource('dsl/sort.yaml'))
        for i in range(2, 12):
            modification = self.client.deployment_modifications.start(
                deployment_id=deployment.id,
                nodes={'node': {'instances': i}})
            self.client.deployment_modifications.finish(modification.id)
        self._test_sort('deployment_modifications', 'deployment_id')

    def test_executions_sort(self):
        deployment = deploy(resource('dsl/sort.yaml'))
        for i in range(5):
            execute_workflow('install', deployment.id)
            execute_workflow('uninstall', deployment.id)
        self._test_sort('executions',
                        ['deployment_id', '-status'])

    def test_nodes_sort(self):
        deploy(resource('dsl/sort.yaml'))
        self._test_sort('nodes', '-id')

    def test_node_instances_sort(self):
        deploy(resource('dsl/sort.yaml'))
        self._test_sort('node_instances', ['node_id', '-id'])

    def test_plugins_sort(self):
        for i in range(1, 11):
            tmpdir = tempfile.mkdtemp(prefix='test-sort-')
            with open(os.path.join(tmpdir, 'setup.py'), 'w') as f:
                f.write('from setuptools import setup\n')
                f.write('setup(name="some-package", version={0})'.format(i))
            wagon = Wagon(tmpdir)
            plugin_path = wagon.create(archive_destination_dir=tmpdir)
            self.client.plugins.upload(plugin_path)
            shutil.rmtree(tmpdir)
        self._test_sort('plugins', 'id')

    def _test_sort(self, resource_name, sort):
        api = getattr(self.client, resource_name)
        actual_list = api.list(_sort=sort)
        self.assertGreater(len(actual_list), 0)
        expected_list = api.list()
        # apply all sort parameters to unsorted list and compare with
        # sorted list request
        if not isinstance(sort, list):
            sort = [sort]
        for sort_param in reversed(sort):
            field = sort_param.lstrip('-+')
            is_reverse = True if sort_param[0] == '-' else False
            expected_list.sort(
                key=lambda res: getattr(res, field),
                reverse=is_reverse)
        self.assertListEqual(expected_list.items, actual_list.items)
