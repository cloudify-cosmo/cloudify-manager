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
import pytest

from integration_tests.framework import utils
from .security_base import TestAuthenticationBase

pytestmark = pytest.mark.group_premium


class AuthenticationTest(TestAuthenticationBase):
    def test_valid_credentials_authenticate(self):
        profile_context = utils.get_profile_context(self.env.container_id)
        self._assert_authorized(username=profile_context['manager_username'],
                                password=profile_context['manager_password'])

    def test_invalid_credentials_fails(self):
        self._assert_unauthorized(username='wrong_username',
                                  password='wrong_password')

    def test_empty_credentials_fails(self):
        self._assert_unauthorized(username='', password='')

    def test_no_credentials_fails(self):
        # This is different from empty credentials, because of how the
        # client getter function is built
        self._assert_unauthorized(username=None, password=None)

    def test_valid_token_authenticates(self):
        token = self.client.tokens.create().value
        self._assert_authorized(token=token, username=None)

    def test_invalid_token_fails(self):
        self._assert_unauthorized(token='wrong_token', username=None)

    def test_empty_token_fails(self):
        self._assert_unauthorized(token='', username=None)
