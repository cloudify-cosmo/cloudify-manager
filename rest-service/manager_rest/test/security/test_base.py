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

from contextlib import contextmanager

from cloudify_rest_client.exceptions import UserUnauthorizedError
from manager_rest.utils import create_auth_header
from manager_rest.test.base_test import BaseServerTestCase
from manager_rest.test.security_utils import get_test_users, add_users_to_db
from manager_rest.constants import DEFAULT_TENANT_NAME, CLOUDIFY_TENANT_HEADER


class SecurityTestBase(BaseServerTestCase):
    def setUp(self):
        super(SecurityTestBase, self).setUp()
        add_users_to_db(get_test_users())

    @staticmethod
    def _get_app(flask_app):
        # Overriding the base class' app, because otherwise a custom
        # auth header is set on every use of the client
        return flask_app.test_client()

    @contextmanager
    def use_secured_client(self, headers=None, **kwargs):
        client = self.client
        try:
            self.client = self.get_secured_client(headers, **kwargs)
            yield
        finally:
            self.client = client

    def get_secured_client(self, headers=None, **kwargs):
        headers = headers or create_auth_header(**kwargs)
        headers.setdefault(CLOUDIFY_TENANT_HEADER, DEFAULT_TENANT_NAME)
        return self.create_client(headers)

    def _assert_user_authorized(self, headers=None, **kwargs):
        with self.use_secured_client(headers, **kwargs):
            self.client.deployments.list()

    def _assert_user_unauthorized(self, headers=None, **kwargs):
        with self.use_secured_client(headers, **kwargs):
            self.assertRaises(
                    UserUnauthorizedError,
                    self.client.deployments.list
                )

    def create_configuration(self):
        test_config = super(SecurityTestBase, self).create_configuration()
        test_config.failed_logins_before_user_lock = 5
        test_config.user_lock_period = 30

        return test_config

    def get_user_using_authorized_user(self, user, headers=None, **kwargs):
        with self.use_secured_client(headers, **kwargs):
            return self.client.users.get(user)

    def unlock_user(self, user, headers=None, **kwargs):
        with self.use_secured_client(headers, **kwargs):
            return self.client.users.unlock(user)
