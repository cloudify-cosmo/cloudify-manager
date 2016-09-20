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


from integration_tests.framework import utils
from .test_base import TestAuthenticationBase


class AuthenticationTest(TestAuthenticationBase):
    def test_authentication(self):
        self.bootstrap_secured_manager()
        self._test_credentials_authentication()
        self._test_token_authentication()

    def _test_credentials_authentication(self):
        self.logger.info('Running _assert_valid_credentials_authenticate')
        self._assert_valid_credentials_authenticate()
        self.logger.info('Running _assert_invalid_credentials_fails')
        self._assert_invalid_credentials_fails()
        self.logger.info('Running _assert_empty_credentials_fails')
        self._assert_empty_credentials_fails()
        self.logger.info('Running _assert_no_credentials_fails')
        self._assert_no_credentials_fails()

    def _test_token_authentication(self):
        self.logger.info('Running _assert_valid_token_authenticates')
        self._assert_valid_token_authenticates()
        self.logger.info('Running _assert_invalid_token_fails')
        self._assert_invalid_token_fails()
        self.logger.info('Running _assert_empty_token_fails')
        self._assert_empty_token_fails()

    def _assert_valid_credentials_authenticate(self):
        self._assert_authorized(username=utils.ADMIN_USERNAME,
                                password=utils.ADMIN_PASSWORD)

    def _assert_invalid_credentials_fails(self):
        self._assert_unauthorized(username='wrong_username',
                                  password='wrong_password')

    def _assert_empty_credentials_fails(self):
        self._assert_unauthorized(username='', password='')

    def _assert_no_credentials_fails(self):
        # This is different from empty credentials, because of how the
        # client getter function is built
        self._assert_unauthorized(username=None, password=None)

    def _assert_valid_token_authenticates(self):
        token = self.client.tokens.get().value
        self._assert_authorized(token=token, username=None)

    def _assert_invalid_token_fails(self):
        self._assert_unauthorized(token='wrong_token', username=None)

    def _assert_empty_token_fails(self):
        self._assert_unauthorized(token='', username=None)
