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
import shutil
import tempfile
from functools import partial

import wagon

from integration_tests.framework import utils
from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource

pytestmark = pytest.mark.group_rest
MAX_RESULT_FOR_TESTING = 9


class TestRestServiceListPagination(AgentlessTestCase):
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
        # since we have set max_results to 9 for this test,
        # we can't add more than 9 modification to the modifications history
        for i in range(1, 11):
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
        total_executions = 11  # create_deployment_environment + 5 install/un
        self._test_pagination(partial(self.client.executions.list,
                                      deployment_id=deployment.id),
                              total=total_executions)

    def test_nodes_pagination(self):
        deployment = self.deploy(resource('dsl/pagination-nodes.yaml'))
        num_of_nodes = 9
        self._test_pagination(partial(self.client.nodes.list,
                                      deployment_id=deployment.id),
                              total=num_of_nodes)

    def test_node_instances_pagination(self):
        deployment = self.deploy(
            resource('dsl/pagination-node-instances.yaml'))
        partial_obj = partial(
            self.client.node_instances.list,
            deployment_id=deployment.id)
        num_of_nodes_instances = 9
        self._test_pagination(partial_obj, total=num_of_nodes_instances)

    def test_plugins_pagination(self):
        for i in range(1, 11):
            tmpdir = tempfile.mkdtemp(prefix='test-pagination-')
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
        self._test_pagination(self.client.plugins.list)

    def _test_pagination(self, list_func, total=10):
        self.wait_for_all_executions_to_end()
        all_results = list_func(_sort=['id'],
                                _offset=0,
                                _size=MAX_RESULT_FOR_TESTING).items
        num_all = len(all_results)
        self.assertLessEqual(num_all, MAX_RESULT_FOR_TESTING)

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
