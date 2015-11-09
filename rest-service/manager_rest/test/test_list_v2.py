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

from base_list_test import BaseListTest
from nose.plugins.attrib import attr

API_VERSION = '2'


@attr(client_min_version=2,
      client_max_version=API_VERSION)
class ResourceListTestCase(BaseListTest):

    def setUp(self):
        self.num_of_deployments = 10
        super(ResourceListTestCase, self).setUp()
        self._put_n_deployments(deployment_id="test",
                                number_of_deployments=self.num_of_deployments)

    def test_deployments_list_paginated_first_page(self):
        first = {"_offset": 0,
                 "_size": 3}
        response = self.get('/deployments', query_params=first).json
        self.assertEqual(3, len(response), 'pagination applied, '
                                           'expecting 3 results, got {0}'
                         .format(len(response)))

    def test_deployments_list_paginated_last_page(self):
        last = {"_offset": self.num_of_deployments - 1,
                "_size": 3}
        response = self.get('/deployments', query_params=last).json
        self.assertEqual(1, len(response), 'pagination applied, '
                                           'expecting 1 result, got {0}'
                         .format(len(response)))

    def test_blueprints_list_paginated_last_page(self):
        response = \
            self.client.blueprints.list(_offset=self.num_of_deployments - 1,
                                        _size=3)
        self.assertEqual(1, len(response), 'pagination applied, '
                                           'expecting 1 result, got {0}'
                         .format(len(response)))

    def test_executions_list_paginated_last_page(self):
        response = \
            self.client.executions.list(_offset=self.num_of_deployments - 1,
                                        _size=3)
        self.assertEqual(1, len(response), 'pagination applied, '
                                           'expecting 1 result, got {0}'
                         .format(len(response)))

    def test_nodes_list_paginated_last_page(self):
        response = \
            self.client.nodes.list(_offset=2 * (self.num_of_deployments - 1),
                                   _size=6)
        self.assertEqual(2, len(response), 'pagination applied, '
                                           'expecting 2 results, got {0}'
                         .format(len(response)))

    def test_node_instances_list_paginated_last_page(self):
        response = \
            self.client.node_instances.list(
                _offset=2 * (self.num_of_deployments - 1),
                _size=6)
        self.assertEqual(2, len(response), 'pagination applied, '
                                           'expecting 2 results, got {0}'
                         .format(len(response)))

    def test_deployment_modifications_list_paginated(self):
        response = self._put_deployment_modification(deployment_id="test1")
        self._mark_deployment_modification_finished(
            modification_id=response['id'])
        self._put_deployment_modification(deployment_id="test2")
        response = self.client.deployment_modifications.list(_offset=1,
                                                             _size=2)
        self.assertEqual(1, len(response), 'expecting 1 deployment mod '
                                           'results, got {0}'
                         .format(len(response)))

    def test_deployments_list_paginated_empty_page(self):
        empty = {"_offset": 99,
                 "_size": 3}
        response = self.get('/deployments', query_params=empty).json
        self.assertEqual(0, len(response), 'pagination applied, '
                                           'expecting 0 results, got {0}'
                         .format(len(response)))

    def test_deployments_list_paginated_no_pagination(self):
        no_pagination = {"_offset": 0,
                         "_size": self.num_of_deployments + 1}
        response = self.get('/deployments', query_params=no_pagination).json
        self.assertEqual(
            self.num_of_deployments,
            len(response),
            'no pagination applied, '
            'expecting {0} results, got {1}'
            .format(self.num_of_deployments, len(response)))

    def test_deployments_list_rest_client_paginated_first_page(self):
        response = self.client.deployments.list(_offset=0,
                                                _size=3)
        self.assertEqual(3, len(response), 'pagination applied, '
                                           'expecting 3 results, got {0}'
                         .format(len(response)))

    def test_deployments_list_rest_client_paginated_last_page(self):
        response = \
            self.client.deployments.list(_offset=self.num_of_deployments - 1,
                                         _size=3)
        self.assertEqual(1, len(response), 'pagination applied, '
                                           'expecting 1 result, got {0}'
                         .format(len(response)))

    def test_deployments_list_rest_client_paginated_empty_page(self):
        response = self.client.deployments.list(_offset=99,
                                                _size=3)
        self.assertEqual(0, len(response), 'pagination applied, '
                                           'expecting 0 results, got {0}'
                         .format(len(response)))

    def test_deployments_list_rest_client_paginated_no_pagination(self):
        response = \
            self.client.deployments.list(_offset=0,
                                         _size=self.num_of_deployments + 1)
        self.assertEqual(
            self.num_of_deployments,
            len(response),
            'no pagination applied, '
            'expecting {0} results, got {1}'
            .format(self.num_of_deployments, len(response)))

    def test_snapshots_list_rest_client_paginated_first_page(self):
        self._create_snapshots(5)
        response = self.client.deployments.list(_offset=0,
                                                _size=3)
        self.assertEqual(3, len(response), 'pagination applied, '
                                           'expecting 3 results, got {0}'
                         .format(len(response)))

    def test_snapshots_list_rest_client_paginated_last_page(self):
        self._create_snapshots(5)
        response = \
            self.client.deployments.list(_offset=self.num_of_deployments - 1,
                                         _size=3)
        self.assertEqual(1, len(response), 'pagination applied, '
                                           'expecting 1 result, got {0}'
                         .format(len(response)))

    def test_snapshots_list_rest_client_paginated_empty_page(self):
        self._create_snapshots(5)
        response = self.client.deployments.list(_offset=99,
                                                _size=3)
        self.assertEqual(0, len(response), 'pagination applied, '
                                           'expecting 0 results, got {0}'
                         .format(len(response)))

    def test_snapshots_list_rest_client_paginated_no_pagination(self):
        num_of_snapshots = 3
        self._create_snapshots(num_of_snapshots)
        response = \
            self.client.snapshots.list(_offset=0,
                                       _size=num_of_snapshots + 1)
        self.assertEqual(
            num_of_snapshots,
            len(response),
            'no pagination applied, '
            'expecting {0} results, got {1}'
            .format(num_of_snapshots, len(response)))

    def test_deployments_list_sorted(self):
        self._resource_list_sorted_test('deployments', ['blueprint_id', '-id'])

    def test_blueprints_list_sorted(self):
        self._resource_list_sorted_test('blueprints', '+id')

    def test_executions_list_sorted(self):
        self._resource_list_sorted_test('executions', '-workflow_id')

    def test_nodes_list_sorted(self):
        self._resource_list_sorted_test('nodes', 'blueprint_id')

    def test_node_instances_list_sorted(self):
        self._resource_list_sorted_test('node_instances', ['+node_id', '-id'])

    def test_deployment_modifications_list_sorted(self):
        self._resource_list_sorted_test('deployment_modifications',
                                        '-deployment_id')

    def test_plugins_list_sorted(self):
        self._resource_list_sorted_test('plugins', 'source')

    def test_snapshots_list_sorted(self):
        self._create_snapshots(3)
        self._resource_list_sorted_test('snapshots', 'id')

    def _resource_list_sorted_test(self, resource, sort):
        resource_api = getattr(self.client, resource)
        actual_list = resource_api.list(_sort=sort)

        # apply all sort parameters to unsorted list and compare with
        # sorted list request
        expected_list = resource_api.list()
        if not isinstance(sort, list):
            sort = [sort]
        for sort_param in sort:
            field = sort_param.lstrip('-+')
            is_reverse = True if sort_param[0] == '-' else False
            expected_list.sort(
                key=lambda res: getattr(res, field),
                reverse=is_reverse)

        self.assertListEqual(expected_list, actual_list)

    def _create_snapshots(self, n):
        """Create n snapshots
        """
        for i in range(n):
            self.client.snapshots.create(snapshot_id='oh-snap{0}'.format(i),
                                         include_metrics=False,
                                         include_credentials=False)
