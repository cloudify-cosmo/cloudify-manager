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

from json import loads

from nose.plugins.attrib import attr

from manager_rest.test import base_test


@attr(client_min_version=3, client_max_version=base_test.LATEST_API_VERSION)
class UserTestCase(base_test.BaseServerTestCase):

    def test_get_user(self):
        response = self.get('/user')
        result = loads(response.data)
        self._assert_response(result)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_get_users_by_username(self):

        response = self.get('/users/admin')
        result = loads(response.data)
        self._assert_response(result)

    def _assert_response(self, result):
        self.assertEqual('admin', result['username'])
        self.assertEqual('sys_admin', result['role'])
        self.assertEqual(0, result['groups'])
        self.assertEqual(1, result['tenants'])
        self.assertEqual(True, result['active'])
        self.assertEqual(False, result['is_locked'])
