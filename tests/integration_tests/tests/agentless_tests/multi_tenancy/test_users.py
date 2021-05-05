from cloudify_rest_client.exceptions import CloudifyClientError
from manager_rest.constants import DEFAULT_TENANT_NAME

from integration_tests import AgentlessTestCase
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
        self.assertEqual(len(users), 1)
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
        self._add_and_validate_test_user()
        old_password_client = self.create_rest_client(
            username=self.test_username,
            password=self.test_password,
        )
        old_password_client.manager.get_status()  # doesn't throw
        self.client.users.set_password(self.test_username, 'new_password')
        new_password_client = self.create_rest_client(
            username=self.test_username,
            password='new_password',
        )
        new_password_client.manager.get_status()  # doesn't throw
        with self.assertRaises(CloudifyClientError) as cm:
            old_password_client.manager.get_status()
        self.assertEqual(cm.exception.status_code, 401)

    def _test_list_users(self, get_data):
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
        # admin + 5 new users
        self.assertEqual(len(users), 6)
        for i in range(1, 6):
            user_dict = self._get_user_dict(
                username='{0}_{1}'.format(self.test_username, i),
                get_data=get_data
            )
            self.assertDictContainsSubset(user_dict, users[i])

    def test_list_users_get_data(self):
        self._test_list_users(get_data=True)

    def test_list_users_no_get_data(self):
        self._test_list_users(get_data=False)
