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

from manager_rest.test.attribute import attr

from manager_rest.version import get_version_data
from manager_rest.test.security_utils import get_admin_user
from manager_rest.constants import CLOUDIFY_TENANT_HEADER, DEFAULT_TENANT_NAME
from manager_rest.test.base_test import BaseServerTestCase, LATEST_API_VERSION


@attr(client_min_version=1, client_max_version=LATEST_API_VERSION)
class VersionTestCase(BaseServerTestCase):
    def setUp(self):
        super(VersionTestCase, self).setUp()
        admin = get_admin_user()
        self.client = self.create_client_with_tenant(
            username=admin['username'],
            password=admin['password'],
            tenant=DEFAULT_TENANT_NAME
        )

    @staticmethod
    def _get_app(flask_app):
        # Overriding the base class' app, because otherwise a custom
        # auth header is set on every use of the client
        return flask_app.test_client()

    def test_get_version(self):
        self._test_get_version()

    def test_version_does_not_require_tenant_header(self):
        # Remove the the tenant header from the client, and make sure the
        # rest call still works
        self.client._client.headers.pop(CLOUDIFY_TENANT_HEADER, None)
        self._test_get_version()

    def _test_get_version(self):
        version_dict = get_version_data()
        # Adding some values, for backwards compatibility with older clients
        version_dict['build'] = None
        version_dict['date'] = None
        version_dict['commit'] = None
        self.assertDictEqual(self.client.manager.get_version(), version_dict)
