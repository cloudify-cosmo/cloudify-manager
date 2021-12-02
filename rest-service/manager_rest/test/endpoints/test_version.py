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

from manager_rest import utils
from manager_rest.version import get_version_data
from manager_rest.test.security_utils import get_admin_user
from manager_rest.test.base_test import BaseServerTestCase


class VersionTestCase(BaseServerTestCase):
    def setUp(self):
        super(VersionTestCase, self).setUp()
        self._expected = get_version_data()
        # Adding some values, for backwards compatibility with older clients
        self._expected['build'] = None
        self._expected['date'] = None
        self._expected['commit'] = None

    def test_get_version(self):
        assert self.client.manager.get_version() == self._expected

    def test_version_does_not_require_tenant_header(self):
        # create a client without the tenant header
        admin = get_admin_user()
        no_tenant_client = self.create_client(headers=utils.create_auth_header(
            username=admin['username'],
            password=admin['password'],
        ))
        assert no_tenant_client.manager.get_version() == self._expected
