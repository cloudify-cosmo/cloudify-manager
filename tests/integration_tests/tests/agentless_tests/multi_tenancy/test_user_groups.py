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

from integration_tests import AgentlessTestCase
from integration_tests.tests.constants import USER_ROLE

from cloudify_premium.constants import DEFAULT_TENANT_ROLE
from cloudify_rest_client.exceptions import CloudifyClientError


class UserGroupsTest(AgentlessTestCase):
    def test_default_groups(self):
        self.assertEqual(self.client.user_groups.list().items, [])

    def test_create_and_list_groups(self):
        for i in range(5):
            self.client.user_groups.create('group_{0}'.format(i), USER_ROLE)
        groups = self.client.user_groups.list()
        self.assertEqual(len(groups), 5)
        for i in range(5):
            self.assertEqual(groups[i].name, 'group_{0}'.format(i))
            self.assertEqual(groups[i].tenants, 0)

    def test_create_group_with_dn(self):
        self.client.user_groups.create('test_group',
                                       USER_ROLE,
                                       ldap_group_dn='test_dn')
        group = self.client.user_groups.get('test_group')
        self.assertEqual(group.name, 'test_group')
        self.assertEqual(group.ldap_dn, 'test_dn')

    def test_add_tenants_and_users_to_group(self):
        group_name = 'group_name'
        self.client.user_groups.create(group_name, USER_ROLE)
        tenants = []
        users = []
        for i in range(5):
            tenants.append('tenant_{0}'.format(i))
            users.append('user_{0}'.format(i))

            self.client.tenants.create(tenants[i])
            self.client.users.create(users[i], 'dummy', USER_ROLE)
            self.client.tenants.add_user_group(
                group_name,
                tenants[i],
                DEFAULT_TENANT_ROLE,
            )
            self.client.user_groups.add_user(users[i], group_name)

        group = self.client.user_groups.get(group_name)
        self.assertEqual(group.tenants, len(tenants))
        self.assertEqual(group.users, len(users))

        group = self.client.user_groups.get(group_name, _get_data=True)
        self.assertDictEqual(
            group.tenants,
            {tenant: DEFAULT_TENANT_ROLE for tenant in tenants},
        )
        self.assertEqual(group.users, users)

    def test_case_insensitive_group(self):
        group_name = 'test_group'
        group_ldap_dn = 'CN=test_group,DC=cloudifyi,DC=com'
        self.client.user_groups.create(group_name=group_name,
                                       role=USER_ROLE,
                                       ldap_group_dn=group_ldap_dn)

        def _assert_list_result(**kwargs):
            groups = self.client.user_groups.list(**kwargs)
            self.assertEqual(len(groups), 1)
            self.assertEqual(groups[0].name, group_name)
            self.assertEqual(groups[0].ldap_dn, group_ldap_dn)

        def _assert_get_result(group_name_to_check):
            group = self.client.user_groups.get(group_name_to_check)
            self.assertEqual(group.name, group_name)
            self.assertEqual(group.ldap_dn, group_ldap_dn)

        _assert_list_result()
        _assert_list_result(name='test_group')
        _assert_list_result(name='TeSt_gRouP')
        _assert_list_result(name='TEST_GROUP')
        _assert_list_result(ldap_dn='CN=test_group,DC=cloudifyi,DC=com')
        _assert_list_result(ldap_dn='cn=test_group,dc=cloudifyi,dc=com')
        _assert_list_result(ldap_dn='CN=TEST_GROUP,DC=CLOUDIFYI,DC=COM')

        _assert_get_result('test_group')
        _assert_get_result('TeSt_gRouP')
        _assert_get_result('TEST_GROUP')

    def test_case_insensitive_group_creation(self):
        self.client.user_groups.create(group_name='test_group',
                                       role=USER_ROLE,
                                       ldap_group_dn='cd=test_group')

        self.assertRaisesRegexp(
            CloudifyClientError,
            '409: A group with the same name already exists: '
            '<Group name=`test_group` ldap_dn=`cd=test_group`>',
            self.client.user_groups.create,
            group_name='TEST_group',
            role=USER_ROLE,
            ldap_group_dn='cd=test_group'
        )

        self.assertRaisesRegexp(
            CloudifyClientError,
            '409: A group with the same LDAP DN already exists: '
            '<Group name=`test_group` ldap_dn=`cd=test_group`>',
            self.client.user_groups.create,
            group_name='test_group_2',
            role=USER_ROLE,
            ldap_group_dn='cd=TEST_group'
        )
