#########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
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

from flask_security.utils import verify_password

from manager_rest.storage import user_datastore
from manager_rest.constants import DEFAULT_TENANT_NAME

from integration_tests import AgentlessTestCase
from integration_tests.framework.flask_utils import setup_flask_app
from integration_tests.tests.constants import ADMIN_ROLE, USER_ROLE


class UsersTest(AgentlessTestCase):
    test_username = 'test_username'
    test_password = 'test_password'
    test_group_name = 'test_group_name'

    @staticmethod
    def _get_user_dict(username,
                       role=USER_ROLE,
                       groups=None,
                       active=True,
                       tenants=None,
                       get_data=False):
        groups = groups if groups is not None else []
        groups = groups if get_data else len(groups)
        tenants = tenants if tenants is not None else {}
        tenants = tenants if get_data else len(tenants)

        return {
            'username': username,
            'role': role,
            'groups': groups,
            'active': active,
            'tenants': tenants
        }

    def _validate_user(self,
                       username,
                       role=USER_ROLE,
                       groups=None,
                       active=True,
                       tenants=None):
        user = self.client.users.get(username)
        self.assertDictContainsSubset(
            self._get_user_dict(
                username=username,
                role=role,
                groups=groups,
                active=active,
                tenants=tenants
            ),
            user
        )
        return user

    def _add_and_validate_test_user(self):
        self.client.users.create(
            self.test_username,
            self.test_password,
            USER_ROLE
        )
        return self._validate_user(self.test_username)

    def test_default_user(self):
        users = self.client.users.list()
        # Admin + the Manager Status Reporter
        self.assertEqual(len(users), 2)
        self.assertDictContainsSubset(
            self._get_user_dict(
                'admin',
                role=ADMIN_ROLE,
                tenants=[DEFAULT_TENANT_NAME]
            ),
            users[0]
        )

    def test_create_users_default_role(self):
        self._add_and_validate_test_user()

    def test_set_role(self):
        self._add_and_validate_test_user()

        self.client.users.set_role(self.test_username, ADMIN_ROLE)
        self._validate_user(self.test_username, role=ADMIN_ROLE)

    def test_add_and_remove_group(self):
        self._add_and_validate_test_user()

        self.client.user_groups.create(self.test_group_name, USER_ROLE)
        self.client.user_groups.add_user(self.test_username,
                                         self.test_group_name)

        self._validate_user(self.test_username, groups=[self.test_group_name])

        self.client.user_groups.remove_user(self.test_username,
                                            self.test_group_name)
        self._validate_user(self.test_username)

    def test_set_password(self):
        setup_flask_app()
        self._add_and_validate_test_user()
        storage_user = user_datastore.get_user(self.test_username)
        self.assertTrue(verify_password(self.test_password,
                                        storage_user.password))
        user_datastore.commit()

        self.client.users.set_password(self.test_username, 'new_password')
        storage_user = user_datastore.get_user(self.test_username)
        self.assertTrue(verify_password('new_password', storage_user.password))
        user_datastore.commit()

    def _test_list_users(self, get_data):
        # Only the manager status reporter exists at this point
        status_reporters_cnt = 1
        for i in range(1, 6):
            self.client.users.create(
                username='{0}_{1}'.format(self.test_username, i),
                password='{0}_{1}'.format(self.test_password, i),
                role=USER_ROLE
            )

        users = sorted(
            self.client.users.list(_get_data=get_data).items,
            key=lambda k: k['username']
        )
        # admin + 5 new users + status reporters
        self.assertEqual(len(users), 6 + status_reporters_cnt)
        for i in range(1 + status_reporters_cnt, 6 + status_reporters_cnt):
            test_user_index = i - status_reporters_cnt
            user_dict = self._get_user_dict(
                username='{0}_{1}'.format(self.test_username, test_user_index),
                get_data=get_data
            )
            self.assertDictContainsSubset(user_dict, users[i])

    def test_list_users_get_data(self):
        self._test_list_users(get_data=True)

    def test_list_users_no_get_data(self):
        self._test_list_users(get_data=False)
