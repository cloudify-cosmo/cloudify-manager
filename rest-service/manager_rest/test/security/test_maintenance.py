#########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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

from nose.plugins.attrib import attr

from manager_rest.test import base_test
from manager_rest.test.security.security_test_base import SecurityTestBase


@attr(client_min_version=2.1, client_max_version=base_test.LATEST_API_VERSION)
class MaintenanceSecurityTests(SecurityTestBase):

    def setUp(self):
        super(MaintenanceSecurityTests, self).setUp()
        self.admin_client = self._get_client_by_password('alice',
                                                         'alice_password')

    def test_requested_by_secured(self):
        self.admin_client.maintenance_mode.activate()
        response = self.admin_client.maintenance_mode.status()
        self.assertEqual(response.requested_by, 'alice')

    def _get_client_by_password(self, username, password):
        auth_header = SecurityTestBase.create_auth_header(username=username,
                                                          password=password)
        return self.create_client(headers=auth_header)
