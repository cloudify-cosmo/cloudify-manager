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

from testenv import TestCase
from testenv.utils import get_resource as resource
from testenv.utils import deploy_application as deploy

from nose.plugins.attrib import attr

API_VERSION = '2'


@attr(client_min_version=2,
      client_max_version=API_VERSION)
class TestRestServiceListPagination(TestCase):

    def setUp(self):
        super(TestRestServiceListPagination, self).setUp()
        self._put_n_deployments(10)

    def _put_n_deployments(self, number_of_deployments):
        dsl_path = resource("dsl/deployment_modification_operations.yaml")
        for i in range(0, number_of_deployments):
            a, b = deploy(dsl_path)

    def test_deployments_list_rest_client_paginated_first_page(self):
        response = self.client.deployments.list(_offset=0,
                                                _size=3)
        self.assertEqual(3, len(response), 'pagination applied, '
                                           'expecting 3 results, got {0}'
                         .format(len(response)))

    def test_deployments_list_rest_client_paginated_last_page(self):
        response = self.client.deployments.list(_offset=9,
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
        response = self.client.deployments.list(_offset=0,
                                                _size=11)
        self.assertEqual(10, len(response), 'no pagination applied, '
                                            'expecting 10 results, got {0}'
                         .format(len(response)))
