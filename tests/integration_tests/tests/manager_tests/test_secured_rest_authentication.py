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
#

from contextlib import contextmanager

from cloudify_rest_client import exceptions

from integration_tests import utils
from integration_tests.tests.manager_tests.test_secured_rest_base import (
    TestSecuredRestBase)


class AuthenticationTest(TestSecuredRestBase):

    test_client = None

    def test_authentication(self):
        self.bootstrap_secured_manager()
        self._test_credentials_authentication()
        self._test_token_authentication()

    def _test_credentials_authentication(self):
        self._assert_valid_credentials_authenticate()
        self._assert_invalid_credentials_fails()
        self._assert_empty_credentials_fails()
        self._assert_no_credentials_fails()

    def _test_token_authentication(self):
        self._assert_valid_token_authenticates()
        self._assert_invalid_token_fails()
        self._assert_empty_token_fails()

    def _assert_valid_credentials_authenticate(self):
        with self._login_client(username=self.get_username(),
                                password=self.get_password()):
            self.test_client.manager.get_status()

    def _assert_invalid_credentials_fails(self):
        with self._login_client(username='wrong_username',
                                password='wrong_password'):
            self._assert_unauthorized(self.test_client.manager.get_status)

    def _assert_empty_credentials_fails(self):
        with self._login_client(username='',
                                password=''):
            self._assert_unauthorized(self.test_client.manager.get_status)

    def _assert_no_credentials_fails(self):
        with self._login_client(username=False,
                                password=False):
            self._assert_unauthorized(self.test_client.manager.get_status)

    def _assert_valid_token_authenticates(self):
        token = self.client.tokens.get().value
        with self._login_client(token=token):
            self.test_client.manager.get_status()

    def _assert_invalid_token_fails(self):
        with self._login_client(token='wrong_token'):
            self._assert_unauthorized(self.test_client.manager.get_status)

    def _assert_empty_token_fails(self):
        with self._login_client(token=''):
            self._assert_unauthorized(self.test_client.manager.get_status)

    def _assert_unauthorized(self, method, *args, **kwargs):
        with self.assertRaises(exceptions.UserUnauthorizedError):
            method(*args, **kwargs)

    @contextmanager
    def _login_client(self, username=None, password=None, token=None):
        self.logger.info('performing login to test client with username: {0}, '
                         'password: {1}, token: {2}'
                         .format(username, password, token))
        try:
            self.test_client = utils.create_rest_client(username=username,
                                                        password=password,
                                                        token=token)
            yield
        finally:
            self.test_client = None

    def get_userstore_driver(self):
        implementation = 'flask_securest.userstores.simple:SimpleUserstore'
        users = [{'username': self.get_username(),
                  'password': self.get_password()}]
        return {
            'implementation': implementation,
            'properties': {'userstore': {'users': users}}
        }

    def get_authorization_provider(self):
        # overriding default authorization provider
        return ''
