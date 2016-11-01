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
from base64 import urlsafe_b64encode

from manager_rest.test.base_test import LATEST_API_VERSION
from manager_rest.utils import BASIC_AUTH_PREFIX, CLOUDIFY_AUTH_HEADER

from .test_base import SecurityTestBase


@attr(client_min_version=1, client_max_version=LATEST_API_VERSION)
class AuthenticationTests(SecurityTestBase):

    def test_secured_client(self):
        self._assert_user_authorized(username='alice',
                                     password='alice_password')

    def test_wrong_credentials(self):
        self._assert_user_unauthorized(username='alice',
                                       password='wrong_password')

    def test_invalid_three_part_header(self):
        credentials = 'alice:alice_password:extra'
        header = {
            CLOUDIFY_AUTH_HEADER:
                BASIC_AUTH_PREFIX + urlsafe_b64encode(credentials)
        }
        self._assert_user_unauthorized(headers=header)

    def test_invalid_one_part_header(self):
        credentials = 'alice'
        header = {
            CLOUDIFY_AUTH_HEADER:
                BASIC_AUTH_PREFIX + urlsafe_b64encode(credentials)
        }
        self._assert_user_unauthorized(headers=header)

    def test_missing_credentials(self):
        self._assert_user_unauthorized(username=None, password=None)

    def test_missing_user(self):
        self._assert_user_unauthorized(username=None,
                                       password='alice_password')

    def test_missing_password(self):
        self._assert_user_unauthorized(username='alice', password=None)

    def test_valid_token_authentication(self):
        with self.use_secured_client(username='alice',
                                     password='alice_password'):
            token = self.test_client.tokens.get()
        self._assert_user_authorized(token=token.value)

    def test_invalid_token_authentication(self):
        self._assert_user_unauthorized(token='wrong token')

    def test_secured_manager_blueprints_upload(self):
        with self.use_secured_client(username='alice',
                                     password='alice_password'):
            self.test_client.blueprints.upload(
                self.get_mock_blueprint_path(),
                'bp-id'
            )

    @attr(client_min_version=2.1,
          client_max_version=LATEST_API_VERSION)
    def test_requested_by_secured(self):
        with self.use_secured_client(username='alice',
                                     password='alice_password'):
            self.test_client.maintenance_mode.activate()
            response = self.test_client.maintenance_mode.status()
        self.assertEqual(response.requested_by, 'alice')
