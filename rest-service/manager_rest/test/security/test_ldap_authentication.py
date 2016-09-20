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

from manager_rest.test import base_test
from .test_base import SecurityTestBase
from manager_rest.test.security_utils import get_test_users
from manager_rest.security import authentication, user_datastore

RUNNING_EXECUTIONS_MESSAGE = 'There are running executions for this deployment'
UNAUTHORIZED_ERROR_MESSAGE = '401: User unauthorized'


class MockLdappyUser(object):
    def pretty_data(self):
        return {}

    def get(self, **kwargs):
        return self


class MockLdappy(object):
    def __init__(self):
        self._users = {}
        for user in get_test_users():
            self._users[user['username']] = \
                user['password'].replace('password', 'new_password')
        self._users['eve'] = 'eve_new_password'

    def authenticate(self, username, password):
        return self._users.get(username) == password

    @property
    def user_objects(self):
        return MockLdappyUser()


@attr(client_min_version=1, client_max_version=base_test.LATEST_API_VERSION)
class LDAPAuthenticationTests(SecurityTestBase):
    def setUp(self):
        self._original_ldappy = authentication.get_ldappy
        authentication.get_ldappy = MockLdappy
        super(LDAPAuthenticationTests, self).setUp()

    def tearDown(self):
        authentication.get_ldappy = self._original_ldappy

    def test_ldap_authentication(self):
        # Before the first successful call (and authentication), we should see
        # the old password
        alice = user_datastore.get_user('alice')
        self.assertEqual(alice.password, 'alice_password')

        self._assert_user_authorized(username='alice',
                                     password='alice_new_password')

        # Now we should see the new password
        alice = user_datastore.get_user('alice')
        self.assertEqual(alice.password, 'alice_new_password')

    def test_wrong_credentials(self):
        self._assert_user_unauthorized(username='alice',
                                       password='wrong_password')

    def test_unknown_user(self):
        self._assert_user_unauthorized(username='unknown', password='unknown')
        unknown = user_datastore.get_user('unknown')
        self.assertIsNone(unknown)

    def test_new_user(self):
        # The user is not present in the userstore
        eve = user_datastore.get_user('eve')
        self.assertIsNone(eve)
        self._assert_user_unauthorized(username='eve',
                                       password='eve_wrong_password')

        # The user should only be added to the userstore upon successful
        # LDAP authentication
        eve = user_datastore.get_user('eve')
        self.assertIsNone(eve)

        # Now using correct credentials, so the user should be added to the
        # userstore, but it lacks a role, so the GET should still fail
        self._assert_user_unauthorized(username='eve',
                                       password='eve_new_password')
        eve = user_datastore.get_user('eve')
        self.assertEqual(eve.password, 'eve_new_password')

        # After adding a role, the GET should succeed
        user_datastore.add_role_to_user(eve, 'administrator')
        self._assert_user_authorized(username='eve',
                                     password='eve_new_password')

    def test_valid_token_authentication(self):
        with self.use_secured_client(username='alice',
                                     password='alice_new_password'):
            token = self.test_client.tokens.get()
        self._assert_user_authorized(token=token.value)

    def test_invalid_token_authentication(self):
        self._assert_user_unauthorized(token='wrong token')
