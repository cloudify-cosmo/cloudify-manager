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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from contextlib import contextmanager

from cloudify_rest_client.exceptions import UserUnauthorizedError

from integration_tests import AgentlessTestCase
from integration_tests.framework import postgresql, utils

from manager_rest.config import instance
from manager_rest.storage.models import Tenant
from manager_rest.security import user_datastore
from manager_rest.test.security_utils import get_test_users, get_test_roles
from manager_rest.utils import add_users_and_roles_to_userstore


class TestSecuredRestBase(AgentlessTestCase):
    def setUp(self):
        super(TestSecuredRestBase, self).setUp()
        postgresql.setup_app()
        default_tenant = Tenant.query.filter_by(
            name=instance.default_tenant_name).first()
        add_users_and_roles_to_userstore(
            user_datastore,
            users=get_test_users(),
            roles=get_test_roles(),
            default_tenant=default_tenant
        )


class TestAuthenticationBase(TestSecuredRestBase):
    test_client = None

    @contextmanager
    def _login_client(self, **kwargs):
        self.logger.info('performing login to test client with {0}'.format(
            str(kwargs))
        )
        try:
            self.test_client = utils.create_rest_client(**kwargs)
            yield
        finally:
            self.test_client = None

    def _assert_unauthorized(self, **kwargs):
        with self._login_client(**kwargs):
            self.assertRaises(
                UserUnauthorizedError,
                self.test_client.manager.get_status
            )

    def _assert_authorized(self, **kwargs):
        with self._login_client(**kwargs):
            self.test_client.manager.get_status()
