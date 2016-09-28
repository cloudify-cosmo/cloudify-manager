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
from manager_rest.test.security_utils import get_test_users, get_test_roles


class SecurityTestBase(BaseServerTestCase):
    test_client = None

    @staticmethod
    def _get_app(flask_app):
        # Overriding the base class' app, because otherwise a custom
        # auth header is set on every use of the client
        return flask_app.test_client()

    @contextmanager
    def use_secured_client(self, headers=None, **kwargs):
        try:
            self.test_client = self.get_secured_client(headers, **kwargs)
            yield
        finally:
            self.test_client = None

    def get_secured_client(self, headers=None, **kwargs):
        headers = headers or create_auth_header(**kwargs)
        return self.create_client(headers)

    @staticmethod
    def _get_users():
        return get_test_users()

    @staticmethod
    def _get_roles():
        return get_test_roles()

    def _assert_user_authorized(self, headers=None, **kwargs):
        with self.use_secured_client(headers, **kwargs):
            self.test_client.deployments.list()

    def _assert_user_unauthorized(self, headers=None, **kwargs):
        with self.use_secured_client(headers, **kwargs):
            self.assertRaises(
                    UserUnauthorizedError,
                    self.test_client.deployments.list
                )
