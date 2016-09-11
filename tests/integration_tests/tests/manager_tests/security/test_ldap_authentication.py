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

from .test_base import TestAuthenticationBase
from integration_tests.postgresql import user_datastore

# See here for explanation on how to make AD allow simple passwords
# http://serverfault.com/questions/19611/disable-password-complexity-rule-in-active-directory#19613 # NOQA


class LDAPAuthenticationTest(TestAuthenticationBase):
    def get_manager_blueprint_inputs(self):
        inputs = \
            super(LDAPAuthenticationTest, self).get_manager_blueprint_inputs()
        inputs['ldap_server'] = 'ldap://52.57.5.220:389/'
        inputs['ldap_username'] = 'alice'
        inputs['ldap_password'] = 'alice_new_password'
        inputs['ldap_domain'] = 'cloudify.com'
        inputs['ldap_is_active_directory'] = True

    def test_ldap_authentication(self):
        self.bootstrap_secured_manager()
        self._test_credentials_authentication()
        self._test_token_authentication()

    def _test_credentials_authentication(self):
        self._test_valid_credentials()
        self._test_wrong_credentials()
        self._test_unknown_user()
        self._test_new_user()

    def _test_token_authentication(self):
        self._test_valid_token_authentication()
        self._test_invalid_token_authentication()

    def _test_valid_credentials(self):
        # Before the first successful call (and authentication), we should see
        # the old password
        alice = user_datastore.get_user('alice')
        self.assertEqual(alice.password, 'alice_password')

        self._assert_authorized(username='alice',
                                password='alice_new_password')

        # Now we should see the new password
        alice = user_datastore.get_user('alice')
        self.assertEqual(alice.password, 'alice_new_password')

    def _test_wrong_credentials(self):
        self._assert_unauthorized(username='alice',
                                  password='wrong_password')

    def _test_unknown_user(self):
        self._assert_unauthorized(username='unknown', password='unknown')
        unknown = user_datastore.get_user('unknown')
        self.assertIsNone(unknown)

    def _test_new_user(self):
        # The user is not present in the userstore
        eve = user_datastore.get_user('eve')
        self.assertIsNone(eve)
        self._assert_unauthorized(username='eve',
                                  password='eve_wrong_password')

        # The user should only be added to the userstore upon successful
        # LDAP authentication
        eve = user_datastore.get_user('eve')
        self.assertIsNone(eve)

        # Now using correct credentials, so the user should be added to the
        # userstore, but it lacks a role, so the GET should still fail
        self._assert_unauthorized(username='eve',
                                  password='eve_new_password')
        eve = user_datastore.get_user('eve')
        self.assertEqual(eve.password, 'eve_new_password')

        # After adding a role, the GET should succeed
        user_datastore.add_role_to_user(eve, 'administrator')
        self._assert_authorized(username='eve',
                                password='eve_new_password')

    def _test_valid_token_authentication(self):
        token = self.client.tokens.get()
        self._assert_authorized(token=token.value, username=None)

    def _test_invalid_token_authentication(self):
        self._assert_unauthorized(token='wrong token', username=None)
