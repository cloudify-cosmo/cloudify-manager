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

import yaml
import tempfile

from unittest import skip

from .security_base import TestAuthenticationBase
from integration_tests.framework.postgresql import user_datastore

# See here for explanation on how to make AD allow simple passwords
# http://serverfault.com/questions/19611/disable-password-complexity-rule-in-active-directory#19613 # NOQA


@skip
class LDAPAuthenticationTest(TestAuthenticationBase):
    def setUp(self):
        super(LDAPAuthenticationTest, self).setUp()

        # Update the config on the manager to include LDAP configurations
        config_file_location = '/opt/manager/cloudify-rest.conf'
        config = yaml.load(self.read_manager_file(config_file_location))
        config['ldap_server'] = 'ldap://52.57.5.220:389/'
        config['ldap_username'] = 'alice'
        config['ldap_password'] = 'alice_new_password'
        config['ldap_domain'] = 'cloudify.com'
        config['ldap_is_active_directory'] = True
        with tempfile.NamedTemporaryFile() as f:
            yaml.dump(config, f)
            f.flush()
            self.copy_file_to_manager(f.name, config_file_location)

    def test_valid_credentials(self):
        # Before the first successful call (and authentication), we should see
        # the old password
        alice = user_datastore.get_user('alice')
        self.assertEqual(alice.password, 'alice_password')

        self._assert_authorized(username='alice',
                                password='alice_new_password')

        # Now we should see the new password
        alice = user_datastore.get_user('alice')
        self.assertEqual(alice.password, 'alice_new_password')

    def test_wrong_credentials(self):
        self._assert_unauthorized(username='alice',
                                  password='wrong_password')

    def test_unknown_user(self):
        self._assert_unauthorized(username='unknown', password='unknown')
        unknown = user_datastore.get_user('unknown')
        self.assertIsNone(unknown)

    def test_new_user(self):
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

    def test_valid_token_authentication(self):
        token = self.client.tokens.get()
        self._assert_authorized(token=token.value, username=None)

    def test_invalid_token_authentication(self):
        self._assert_unauthorized(token='wrong token', username=None)
