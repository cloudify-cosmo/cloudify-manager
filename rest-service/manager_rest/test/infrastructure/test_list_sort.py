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

from manager_rest.test.base_test import LATEST_API_VERSION
from manager_rest.test.infrastructure.base_list_test import BaseListTest


class ResourceListTestCase(BaseListTest):

    def setUp(self):
        self.num_of_deployments = 5
        super(ResourceListTestCase, self).setUp()
        self._put_n_deployments(id_prefix="test",
                                number_of_deployments=self.num_of_deployments)

    def test_deployments_list_sorted(self):
        self._resource_list_sorted_test('deployments', ['blueprint_id', '-id'])

    def test_blueprints_list_sorted(self):
        self._resource_list_sorted_test('blueprints', '+id')

    def test_executions_list_sorted(self):
        self._resource_list_sorted_test('executions', ['-workflow_id', 'id'])

    def test_nodes_list_sorted(self):
        self._resource_list_sorted_test('nodes', ['blueprint_id', 'id'])

    def test_node_instances_list_sorted(self):
        self._resource_list_sorted_test('node_instances', ['+node_id', '-id'])

    def test_deployment_modifications_list_sorted(self):
        self._resource_list_sorted_test('deployment_modifications',
                                        ['-deployment_id', 'id'])

    def test_plugins_list_sorted(self):
        self._put_n_plugins(number_of_plugins=3)
        self._resource_list_sorted_test('plugins', '-id')

    def test_snapshots_list_sorted(self):
        self._put_n_snapshots(3)
        self._resource_list_sorted_test('snapshots', 'id')

    def test_sort_snapshots_list(self):
        self._put_n_snapshots(2)

        snapshots = self.client.snapshots.list(sort='created_at')
        self.assertEqual(2, len(snapshots))
        self.assertEqual('oh-snap0', snapshots[0].id)
        self.assertEqual('oh-snap1', snapshots[1].id)

        snapshots = self.client.snapshots.list(
            sort='created_at', is_descending=True)
        self.assertEqual(2, len(snapshots))
        self.assertEqual('oh-snap1', snapshots[0].id)
        self.assertEqual('oh-snap0', snapshots[1].id)

    def _resource_list_sorted_test(self, resource, sort):
        resource_api = getattr(self.client, resource)
        actual_list = resource_api.list(_sort=sort)

        # apply all sort parameters to unsorted list and compare with
        # sorted list request
        expected_list = resource_api.list()
        if not isinstance(sort, list):
            sort = [sort]
        # multiple sorting has to begin from the last sort key
        for sort_param in reversed(sort):
            field = sort_param.lstrip('-+')
            is_reverse = True if sort_param[0] == '-' else False
            expected_list.sort(
                key=lambda res: getattr(res, field),
                reverse=is_reverse)

        self.assertListEqual(expected_list.items, actual_list.items)
