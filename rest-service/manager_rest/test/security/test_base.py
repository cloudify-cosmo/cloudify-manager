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

from cloudify_rest_client.exceptions import UserUnauthorizedError
from manager_rest.test.base_test import BaseServerTestCase


class SecurityTestBase(BaseServerTestCase):
    @staticmethod
    def _get_app(flask_app, user=None):
        # security tests use a not-authenticated client by default
        if user is None:
            user = {'username': '', 'password': ''}
        return BaseServerTestCase._get_app(flask_app, user=user)

    def _assert_user_authorized(self, headers=None, **kwargs):
        with self.use_secured_client(headers, **kwargs):
            self.client.deployments.list()

    def _assert_user_unauthorized(self, headers=None, **kwargs):
        with self.use_secured_client(headers, **kwargs):
            self.assertRaises(
                UserUnauthorizedError,
                self.client.deployments.list
            )

    @classmethod
    def create_configuration(cls):
        test_config = super(SecurityTestBase, cls).create_configuration()
        test_config.failed_logins_before_account_lock = 5
        test_config.account_lock_period = 30

        return test_config
