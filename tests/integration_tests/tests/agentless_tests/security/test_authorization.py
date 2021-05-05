########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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

from os.path import join, dirname

from cloudify_rest_client.exceptions import ForbiddenError
from integration_tests.framework.utils import create_rest_client
from integration_tests.tests.test_cases import AgentlessTestCase
from integration_tests.tests.constants import USER_ROLE, ADMIN_ROLE


TENANT_USER = 'user'
TENANT_VIEWER = 'viewer'
TENANT_MANAGER = 'manager'

USERS = {
    'u1': ADMIN_ROLE,
    'u2': USER_ROLE,
    'u3': USER_ROLE,
    'u4': USER_ROLE,
    'u5': USER_ROLE
}

GROUPS = {'g1': ['u2', 'u4'], 'g2': [], 'g3': ['u1', 'u3'], 'g4': ['u3']}

TENANTS = {
    't1': {
        'users': {
            'u2': TENANT_MANAGER, 'u3': TENANT_USER, 'u4': TENANT_VIEWER
        },
        'groups': {}
    },
    't2': {
        'users': {},
        'groups': {'g3': TENANT_VIEWER, 'g4': TENANT_MANAGER}
    },
    't3': {
        'users': {'u5': TENANT_MANAGER, 'u1': TENANT_VIEWER},
        'groups': {'g1': TENANT_USER, 'g2': TENANT_MANAGER}
    },
    't4': {
        'users': {},
        'groups': {}
    },
    't5': {
        'users': {'u5': TENANT_MANAGER, 'u2': TENANT_USER, 'u3': TENANT_USER},
        'groups': {'g2': TENANT_USER}
    }
}


def _collect_roles(user, tenant):
    roles = [USERS[user]]
    if user in TENANTS[tenant]['users']:
        roles.append(TENANTS[tenant]['users'][user])
    for group in TENANTS[tenant]['groups']:
        if user in GROUPS[group]:
            roles.append(TENANTS[tenant]['groups'][group])
    return roles


def _is_authorized(user, tenant, allowed_roles):
    user_roles = _collect_roles(user, tenant)
    return any(role in allowed_roles for role in user_roles)


class AuthorizationTest(AgentlessTestCase):
    def setUp(self):
        super(AuthorizationTest, self).setUp()

        # create users
        for user in USERS:
            self.client.users.create(user, '12345', USERS[user])

        # create groups and add users to groups
        for group in GROUPS:
            self.client.user_groups.create(group, USER_ROLE)
            for user in GROUPS[group]:
                self.client.user_groups.add_user(user, group)

        # create tenants and add users and groups to tenants
        for tenant in TENANTS:
            self.client.tenants.create(tenant)
            for user in TENANTS[tenant]['users']:
                self.client.tenants.add_user(user,
                                             tenant,
                                             TENANTS[tenant]['users'][user])
            for group in TENANTS[tenant]['groups']:
                self.client.tenants.add_user_group(
                    group, tenant, TENANTS[tenant]['groups'][group])

    def test_authorization(self):
        for user in USERS:
            for tenant in TENANTS:
                self._test_user_in_tenant(user, tenant)

    def test_change_role(self):
        client = create_rest_client(username='u2',
                                    password='12345',
                                    tenant='t1')

        # can view ssl mode but can't change it
        client.manager.ssl_status()
        self.assertRaises(ForbiddenError, client.manager.set_ssl, False)

        # as an admin, can change ssl mode
        self.client.users.set_role('u2', ADMIN_ROLE)
        client.manager.ssl_status()
        client.manager.set_ssl(False)

        # back as a simple user, can't change ssl mode
        self.client.users.set_role('u2', USER_ROLE)
        client.manager.ssl_status()
        self.assertRaises(ForbiddenError, client.manager.set_ssl, False)

        # now adding the user to a new admins group, so it can change ssl mode
        self.client.user_groups.create('g5', ADMIN_ROLE)
        self.client.user_groups.add_user('u2', 'g5')
        client.manager.ssl_status()
        client.manager.set_ssl(False)

    def _test_user_in_tenant(self, user, tenant):
        client = create_rest_client(
            username=user,
            password='12345',
            tenant=tenant
        )
        self._test_action(
            user,
            tenant,
            [ADMIN_ROLE, USER_ROLE],
            client.manager.get_status
        )
        self._test_action(
            user,
            tenant,
            [ADMIN_ROLE],
            client.manager.set_ssl,
            False
        )
        self._test_action(
            user,
            tenant,
            [ADMIN_ROLE, TENANT_MANAGER, TENANT_USER, TENANT_VIEWER],
            client.blueprints.list
        )
        self._test_action(
            user,
            tenant,
            [ADMIN_ROLE, TENANT_MANAGER, TENANT_USER],
            client.blueprints.upload,
            join(dirname(__file__), 'resources', 'bp.yaml'),
            user
        )
        self._test_action(
            user,
            tenant,
            [ADMIN_ROLE, TENANT_MANAGER, TENANT_USER],
            client.tenants.get,
            tenant
        )

    def _test_action(self, user, tenant, allowed_roles, func, *args, **kwargs):
        if _is_authorized(user, tenant, allowed_roles):
            func(*args, **kwargs)
        else:
            self.assertRaises(ForbiddenError, func, *args, **kwargs)
