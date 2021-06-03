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
import pytest
import tempfile
import shutil

import wagon

from integration_tests.framework import utils
from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource

pytestmark = pytest.mark.group_rest


class TestRestServiceListSort(AgentlessTestCase):

    def test_blueprints_sort(self):
        for i in range(10):
            self.client.blueprints.upload(resource('dsl/sort.yaml'),
                                          'blueprint{0}'.format(i))
        self._test_sort('blueprints', '-id')

    def test_deployments_sort(self):
        for i in range(10):
            self.deploy(resource('dsl/sort.yaml'))
        self._test_sort('deployments', 'id')

    def test_deployment_modifications_sort(self):
        deployment = self.deploy(resource('dsl/sort.yaml'))
        for i in range(2, 12):
            modification = self.client.deployment_modifications.start(
                deployment_id=deployment.id,
                nodes={'node': {'instances': i}})
            self.client.deployment_modifications.finish(modification.id)
        self._test_sort('deployment_modifications', 'id')

    def test_executions_sort(self):
        deployment = self.deploy(resource('dsl/sort.yaml'))
        for i in range(5):
            self.execute_workflow('install', deployment.id)
            self.execute_workflow('uninstall', deployment.id)

        sorted_list = self.client.executions.list(_sort=['-workflow_id',
                                                         'status'])

        self.assertGreater(len(sorted_list), 11)

        self.assertEqual(sorted_list[0]['workflow_id'], 'upload_blueprint')

        for i in range(1, 6):
            self.assertEqual(sorted_list[i]['workflow_id'], 'uninstall')

        for i in range(6, 11):
            self.assertEqual(sorted_list[i]['workflow_id'], 'install')

        self.assertEqual(sorted_list[11]['workflow_id'],
                         'create_deployment_environment')

    def test_nodes_sort(self):
        self.deploy(resource('dsl/sort.yaml'))
        self._test_sort('nodes', '-id')

    def test_node_instances_sort(self):
        self.deploy(resource('dsl/sort.yaml'))
        self._test_sort('node_instances', ['node_id', '-id'])

    def test_plugins_sort(self):
        for i in range(1, 11):
            tmpdir = tempfile.mkdtemp(prefix='test-sort-')
            with open(os.path.join(tmpdir, 'setup.py'), 'w') as f:
                f.write('from setuptools import setup\n')
                f.write('setup(name="cloudify-script-plugin", version={0})'
                        .format(i))
            wagon_path = wagon.create(
                tmpdir, archive_destination_dir=tmpdir,
                # mark the wagon as windows-only, so that the manager doesn't
                # attempt to install it - which would be irrelevant for this
                # test, but add additional flakyness and runtime
                wheel_args=['--build-option', '--plat-name=win'])
            yaml_path = resource('plugins/plugin.yaml')
            with utils.zip_files([wagon_path, yaml_path]) as zip_path:
                self.client.plugins.upload(zip_path)
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
