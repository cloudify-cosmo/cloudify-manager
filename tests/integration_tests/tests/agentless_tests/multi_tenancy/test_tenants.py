import json
from collections import namedtuple

from cloudify.cryptography_utils import decrypt

from manager_rest.constants import (DEFAULT_TENANT_NAME,
                                    DEFAULT_TENANT_ROLE,
                                    SECURITY_FILE_LOCATION)
from integration_tests import AgentlessTestCase
from integration_tests.tests.constants import USER_ROLE, USER_IN_TENANT_ROLE
from integration_tests.tests.utils import get_resource as resource

user = namedtuple('user', 'username password')


class TenantsTest(AgentlessTestCase):
    def test_default_tenant(self):
        tenants = self.client.tenants.list()
        self.assertEqual(len(tenants), 1)
        self.assertDictContainsSubset(
            {
                'name': DEFAULT_TENANT_NAME,
                'groups': 0,
                'users': 1,
                'user_roles': None
            },
            tenants[0]
        )
        tenants = self.client.tenants.list(_get_data=True)
        self.assertEqual(len(tenants), 1)
        self.assertDictContainsSubset(
            {
                'name': DEFAULT_TENANT_NAME,
                'groups': {},
                'users': {
                    'admin': {
                        'tenant-role': USER_IN_TENANT_ROLE,
                        'roles': [USER_IN_TENANT_ROLE],
                    },
                },
                'user_roles': {
                    'direct': {
                        'admin': USER_IN_TENANT_ROLE,
                    },
                    'groups': {}
                }
            },
            tenants[0]
        )

    def test_create_and_list_tenants(self):
        for i in range(1, 6):
            self.client.tenants.create('tenant_{0}'.format(i))

        tenants = self.client.tenants.list()
        self.assertEqual(len(tenants), 6)  # default_tenant + 5 new ones
        tenants = sorted(tenants.items, key=lambda t: t['name'])
        for i in range(1, 6):
            self.assertEqual(tenants[i].name, 'tenant_{0}'.format(i))
            self.assertEqual(tenants[i].users, 0)
            self.assertEqual(tenants[i].groups, 0)

    def test_adding_groups_and_users(self):
        tenant_name = 'tenant_name'
        self.client.tenants.create(tenant_name)
        user_groups = []
        users = []
        for i in range(5):
            user_groups.append('group_{0}'.format(i))
            users.append('user_{0}'.format(i))

            self.client.user_groups.create(user_groups[i], USER_ROLE)
            self.client.users.create(users[i], 'dummy', USER_ROLE)
            self.client.tenants.add_user_group(
                user_groups[i],
                tenant_name,
                DEFAULT_TENANT_ROLE,
            )
            self.client.tenants.add_user(
                users[i],
                tenant_name,
                DEFAULT_TENANT_ROLE,
            )

        tenant = self.client.tenants.get(tenant_name)
        self.assertEqual(tenant.groups, len(user_groups))
        self.assertEqual(tenant.users, len(users))

        tenant = self.client.tenants.get(tenant_name, _get_data=True)
        self.assertDictEqual(
            tenant.groups,
            {
                user_group: DEFAULT_TENANT_ROLE
                for user_group in user_groups
            },
        )
        self.assertDictEqual(
            tenant.users,
            {
                user: {
                    'tenant-role': DEFAULT_TENANT_ROLE,
                    'roles': [DEFAULT_TENANT_ROLE],
                }
                for user in users
            },
        )

    def test_different_tenants_with_resources(self):
        user = namedtuple('user', 'username password')
        user_1 = user('user_1', 'user_1')
        user_2 = user('user_2', 'user_2')
        tenant_1 = 'tenant_1'
        tenant_2 = 'tenant_2'

        blueprint_id_1 = 'blueprint_id_1'
        blueprint_id_2 = 'blueprint_id_2'
        blueprint_path = resource('dsl/empty_blueprint.yaml')

        self.client.users.create(user_1.username, user_1.password, USER_ROLE)
        self.client.users.create(user_2.username, user_2.password, USER_ROLE)

        self.client.tenants.create(tenant_1)
        self.client.tenants.create(tenant_2)

        self.client.tenants.add_user(user_1.username,
                                     tenant_1,
                                     DEFAULT_TENANT_ROLE)
        self.client.tenants.add_user(user_2.username,
                                     tenant_2,
                                     DEFAULT_TENANT_ROLE)

        user_1_client = self.create_rest_client(
            username=user_1.username,
            password=user_1.password,
            tenant=tenant_1
        )
        user_2_client = self.create_rest_client(
            username=user_2.username,
            password=user_2.password,
            tenant=tenant_2
        )

        # Upload a blueprint with user 1
        user_1_client.blueprints.upload(blueprint_path, blueprint_id_1)

        # Upload a blueprint with user 2
        user_2_client.blueprints.upload(blueprint_path, blueprint_id_2)

        # User 1 shouldn't see the blueprint uploaded by user 2
        blueprints_list = user_1_client.blueprints.list()
        self.assertEqual(len(blueprints_list), 1)
        self.assertEqual(blueprints_list[0].id, blueprint_id_1)

        # User 2 shouldn't see the blueprint uploaded by user 1
        blueprints_list = user_2_client.blueprints.list()
        self.assertEqual(len(blueprints_list), 1)
        self.assertEqual(blueprints_list[0].id, blueprint_id_2)

        # The admin user (the one logged in with the default client) should
        # be able to see both blueprints
        blueprints_list = self.client.blueprints.list(_all_tenants=True)
        self.assertEqual(len(blueprints_list), 2)
        self.assertEqual(blueprints_list[0].id, blueprint_id_1)
        self.assertEqual(blueprints_list[1].id, blueprint_id_2)

    def test_list_tenants_non_admin(self):
        fred = user('fred', 'fred_password')
        self.client.users.create(fred.username, fred.password, USER_ROLE)
        self.client.tenants.create('test_tenant_1')
        self.client.tenants.create('test_tenant_2')
        self.client.tenants.add_user(fred.username,
                                     'test_tenant_1',
                                     DEFAULT_TENANT_ROLE)

        fred_client = self.create_rest_client(
            username=fred.username,
            password=fred.password,
            tenant='test_tenant_1'
        )
        tenants = fred_client.tenants.list()
        self.assertEqual(len(tenants.items), 1)

    def test_list_tenants_non_admin_with_group(self):
        fred = user('fred', 'fred_password')
        self.client.users.create(fred.username, fred.password, USER_ROLE)
        self.client.tenants.create('test_tenant_1')
        self.client.tenants.create('test_tenant_2')
        self.client.tenants.add_user(fred.username,
                                     'test_tenant_1',
                                     DEFAULT_TENANT_ROLE)
        self.client.user_groups.create('test_group', USER_ROLE)
        self.client.tenants.add_user_group(
            'test_group',
            'test_tenant_2',
            DEFAULT_TENANT_ROLE,
        )
        self.client.user_groups.add_user(fred.username, 'test_group')

        fred_client = self.create_rest_client(
            username=fred.username,
            password=fred.password,
            tenant='test_tenant_1'
        )
        tenants = fred_client.tenants.list()
        self.assertEqual(len(tenants), 2)
        tenant_names = [tenant.name for tenant in tenants]
        self.assertIn('test_tenant_1', tenant_names)
        self.assertIn('test_tenant_2', tenant_names)

    def test_create_tenant_rabbitmq_password_encrypted(self):
        self.client.tenants.create('tenant_1')
        password_encrypted = self._select(
            "SELECT rabbitmq_password FROM tenants WHERE name='tenant_1'"
        )[0][0]
        security_conf = self.read_manager_file(SECURITY_FILE_LOCATION)
        security_conf = json.loads(security_conf)

        # Validate the rabbitmq_password is being stored encrypted in the DB
        decrypt(password_encrypted, security_conf['encryption_key'])
        assert len(password_encrypted) > 32
