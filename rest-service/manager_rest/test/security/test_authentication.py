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

from nose.plugins.attrib import attr
from itsdangerous import base64_encode

from manager_rest.test import base_test
from manager_rest.test.security.security_test_base import \
    BASIC_AUTH_PREFIX, CLOUDIFY_AUTH_HEADER, SecurityTestBase
from cloudify_rest_client.exceptions import UserUnauthorizedError


@attr(client_min_version=1, client_max_version=base_test.LATEST_API_VERSION)
class AuthenticationTests(SecurityTestBase):

    @staticmethod
    def get_authorization_provider_configuration():
        return {}

    def test_secured_client(self):
        client = self.create_client(
            headers=SecurityTestBase.create_auth_header(
                username='alice', password='alice_password'))
        client.deployments.list()

    def test_wrong_credentials(self):
        client = self.create_client(
            headers=SecurityTestBase.create_auth_header(
                username='alice', password='wrong_password'))
        self.assertRaises(UserUnauthorizedError, client.deployments.list)

    def test_invalid_three_part_header(self):
        credentials = 'alice:alice_password:extra'
        header = {
            CLOUDIFY_AUTH_HEADER:
                BASIC_AUTH_PREFIX + base64_encode(credentials)
        }
        client = self.create_client(headers=header)
        self.assertRaises(UserUnauthorizedError, client.deployments.list)

    def test_invalid_one_part_header(self):
        credentials = 'alice'
        header = {
            CLOUDIFY_AUTH_HEADER:
                BASIC_AUTH_PREFIX + base64_encode(credentials)
        }
        client = self.create_client(headers=header)
        self.assertRaises(UserUnauthorizedError, client.deployments.list)

    def test_missing_credentials(self):
        client = self.create_client(headers=SecurityTestBase.
                                    create_auth_header(username=None,
                                                       password=None))
        self.assertRaises(UserUnauthorizedError, client.deployments.list)

    def test_missing_user(self):
        auth_header = SecurityTestBase.create_auth_header(
            username=None, password='alice_password')
        client = self.create_client(auth_header)
        self.assertRaises(UserUnauthorizedError, client.deployments.list)

    def test_missing_password(self):
        auth_header = SecurityTestBase.create_auth_header(username='alice',
                                                          password=None)
        client = self.create_client(headers=auth_header)
        self.assertRaises(UserUnauthorizedError, client.deployments.list)

    def test_token_authentication(self):
        auth_header = SecurityTestBase.create_auth_header(
            username='alice', password='alice_password')
        client = self.create_client(headers=auth_header)
        token = client.tokens.get()
        client = self.create_client(headers=SecurityTestBase.
                                    create_auth_header(token=token.value))
        client.blueprints.list()

    def test_secured_manager_blueprints_upload(self):
        auth_header = SecurityTestBase.create_auth_header(
            username='alice', password='alice_password')
        client = self.create_client(headers=auth_header)
        client.blueprints.upload(self.get_mock_blueprint_path(), 'bp-id')
