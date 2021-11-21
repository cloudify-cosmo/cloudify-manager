#########
# Copyright (c) 2015-2019 Cloudify Platform Ltd. All rights reserved
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

from base64 import b64encode

from manager_rest.storage import management_models
from manager_rest.maintenance import remove_maintenance_state
from manager_rest.constants import (CLOUDIFY_TENANT_HEADER,
                                    BASIC_AUTH_PREFIX,
                                    CLOUDIFY_AUTH_HEADER)
from .test_base import SecurityTestBase
from ..security_utils import ADMIN_ROLE, USER_ROLE

FAILED_LOGINS_NUMBER = 6


class AuthenticationTests(SecurityTestBase):

    def _fetch_alice(self):
        alice = self.sm.list(management_models.User,
                             filters={'username': 'alice'})
        self.assertEqual(len(alice), 1)
        return alice[0]

    def test_secured_client(self):
        login_time = self._fetch_alice().last_login_at
        self.assertIsNone(login_time)
        self._assert_user_authorized(username='alice',
                                     password='alice_password')
        login_time = self._fetch_alice().last_login_at
        self.assertIsNotNone(login_time)

    def test_first_and_last_login(self):
        first_login_time = self._fetch_alice().first_login_at
        last_login_time = self._fetch_alice().last_login_at
        self.assertIsNone(first_login_time)
        self.assertIsNone(last_login_time)

        self._assert_user_authorized(username='alice',
                                     password='alice_password')
        first_login_time = self._fetch_alice().first_login_at
        last_login_time = self._fetch_alice().last_login_at
        self.assertIsNotNone(first_login_time)
        self.assertEqual(first_login_time, last_login_time)

        self._assert_user_authorized(username='alice',
                                     password='alice_password')
        first_login_time = self._fetch_alice().first_login_at
        last_login_time = self._fetch_alice().last_login_at
        self.assertIsNotNone(first_login_time)
        self.assertGreater(last_login_time, first_login_time)

    def test_wrong_credentials(self):
        alice = self._fetch_alice()
        self.assertIsNone(alice.last_failed_login_at)
        self.assertIsNone(alice.last_login_at)
        self.assertEqual(alice.failed_logins_counter, 0)
        self._assert_user_unauthorized(username='alice',
                                       password='wrong_password')
        alice = self._fetch_alice()
        self.assertIsNone(alice.last_login_at)
        self.assertIsNotNone(alice.last_failed_login_at)
        self.assertEqual(alice.failed_logins_counter, 1)

    def test_invalid_three_part_header(self):
        credentials = 'alice:alice_password:extra'
        encoded = b64encode(credentials.encode()).decode()
        header = {
            CLOUDIFY_AUTH_HEADER:
                BASIC_AUTH_PREFIX + encoded
        }
        self._assert_user_unauthorized(headers=header)

    def test_invalid_one_part_header(self):
        credentials = 'alice'
        encoded = b64encode(credentials.encode()).decode()
        header = {
            CLOUDIFY_AUTH_HEADER:
                BASIC_AUTH_PREFIX + encoded
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
            token = self.client.tokens.get()
        self._assert_user_authorized(token=token.value)

    def test_invalid_token_authentication(self):
        self._assert_user_unauthorized(token='wrong token')

    def test_token_returns_role(self):
        with self.use_secured_client(username='alice',
                                     password='alice_password'):
            token = self.client.tokens.get()
        self.assertEqual(token.role, ADMIN_ROLE)

        with self.use_secured_client(username='bob',
                                     password='bob_password'):
            token = self.client.tokens.get()
        self.assertEqual(token.role, USER_ROLE)

    def test_secured_manager_blueprints_upload(self):
        with self.use_secured_client(username='alice',
                                     password='alice_password'):
            self.client.blueprints.upload(
                self.get_mock_blueprint_path(),
                'bp-id',
                async_upload=True
            )

    def test_requested_by_secured(self):
        try:
            with self.use_secured_client(username='alice',
                                         password='alice_password'):
                self.client.maintenance_mode.activate()
                response = self.client.maintenance_mode.status()
            self.assertEqual(response.requested_by, 'alice')
        finally:
            remove_maintenance_state()

    def test_token_does_not_require_tenant_header(self):
        with self.use_secured_client(username='alice',
                                     password='alice_password'):
            # Remove the the tenant header from the client
            self.client._client.headers.pop(CLOUDIFY_TENANT_HEADER, None)
            token = self.client.tokens.get()
        self._assert_user_authorized(token=token.value)

    def test_sequential_authorized_user_calls(self):
        with self.use_secured_client(username='alice',
                                     password='alice_password'):
            self.client._client.headers.pop(CLOUDIFY_TENANT_HEADER, None)
            token = self.client.tokens.get()

        with self.use_secured_client(token=token.value):
            self.client.deployments.list()
            self.client.deployments.list()
