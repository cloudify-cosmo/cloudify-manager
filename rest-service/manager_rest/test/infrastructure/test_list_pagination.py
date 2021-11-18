#########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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
#
from manager_rest.test import base_test
from manager_rest.test.infrastructure.base_list_test import BaseListTest


class ResourceListTestCase(BaseListTest):

    def _test_pagination(self, list_func, total, sort_keys=None):
        if sort_keys is None:
            sort_keys = ['id']
        all_results = list_func(_sort=sort_keys).items
        num_all = len(all_results)
        # sanity
        self.assertGreaterEqual(num_all, total)
        for offset in range(num_all + 1):
            for size in range(num_all + 1):
                response = list_func(_offset=offset, _size=size,
                                     _sort=sort_keys)
                self.assertEqual(response.metadata.pagination.total, num_all)
                self.assertEqual(response.metadata.pagination.offset, offset)
                self.assertEqual(response.metadata.pagination.size, size)
                self.assertEqual(response.items,
                                 all_results[offset:offset + size])

    def test_deployments_list_paginated(self):
        self._put_n_deployments(id_prefix='test', number_of_deployments=4)
        self._test_pagination(self.client.deployments.list, 4,
                              sort_keys=['id', 'blueprint_id'])

    def test_blueprints_list_paginated(self):
        self._put_n_deployments(id_prefix='test', number_of_deployments=2)
        self._test_pagination(self.client.blueprints.list, 2)

    def test_executions_list_paginated(self):
        self._put_n_deployments(id_prefix='test', number_of_deployments=2)
        self._test_pagination(self.client.executions.list, 2,
                              sort_keys=['id', 'deployment_id',
                                         'blueprint_id'])

    def test_nodes_list_paginated(self):
        self._put_n_deployments(id_prefix='test', number_of_deployments=3)
        self._test_pagination(self.client.nodes.list, 6,
                              sort_keys=['id', 'deployment_id',
                                         'blueprint_id'])

    def test_node_instances_list_paginated(self):
        self._put_n_deployments(id_prefix='test', number_of_deployments=3)
        self._test_pagination(self.client.node_instances.list, 6,
                              sort_keys=['id', 'deployment_id'])

    def test_deployment_modifications_list_paginated(self):
        self._put_n_deployments(id_prefix='test', number_of_deployments=2)
        response = self._put_deployment_modification(
            deployment_id='test0_deployment')
        self._mark_deployment_modification_finished(
            modification_id=response['id'])
        self._put_deployment_modification(deployment_id='test1_deployment')
        self._test_pagination(self.client.deployment_modifications.list, 2,
                              sort_keys=['id', 'deployment_id'])

    def test_plugins_list_paginated(self):
        self._put_n_plugins(number_of_plugins=3)
        self._test_pagination(self.client.plugins.list, 3)

    def test_snapshots_list_paginated(self):
        self._put_n_snapshots(3)
        self._test_pagination(self.client.snapshots.list, 3)
