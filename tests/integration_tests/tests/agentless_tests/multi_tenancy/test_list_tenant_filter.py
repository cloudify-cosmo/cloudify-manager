from integration_tests import AgentlessTestCase
from integration_tests.tests.constants import USER_ROLE
from integration_tests.tests.utils import get_resource as resource

from manager_rest.constants import DEFAULT_TENANT_NAME, DEFAULT_TENANT_ROLE

from cloudify_rest_client.exceptions import CloudifyClientError


class ListResourcesTest(AgentlessTestCase):
    def setUp(self):
        super(ListResourcesTest, self).setUp()
        self.client.tenants.create('TEST_TENANT')
        self.client.users.create('alice', 'alice_password', USER_ROLE)
        self.client.users.create('fred', 'fred_password', USER_ROLE)

        # Alice belongs to both tenants
        self.client.tenants.add_user('alice',
                                     DEFAULT_TENANT_NAME,
                                     DEFAULT_TENANT_ROLE)
        self.client.tenants.add_user('alice',
                                     'TEST_TENANT',
                                     DEFAULT_TENANT_ROLE)
        # Fred only belongs to 'TEST_TENANT'
        self.client.tenants.add_user('fred',
                                     'TEST_TENANT',
                                     DEFAULT_TENANT_ROLE)

        # Create clients for each user
        self.alice_client = self.create_rest_client(
            username='alice',
            password='alice_password',
            tenant=DEFAULT_TENANT_NAME,
        )
        self.fred_client = self.create_rest_client(
            username='fred',
            password='fred_password',
            tenant='TEST_TENANT',
        )

    def test_list_blueprints_with_tenants_filter(self):

        self._upload_blueprints_to_different_tenants()

        result = self.alice_client.blueprints.list(_all_tenants=True)
        self.assertEquals(len(result), 2)

        blueprint_ids = [result[0].id, result[1].id]
        self.assertIn('alice_bp', blueprint_ids)
        self.assertIn('fred_bp', blueprint_ids)

        result = self.alice_client.blueprints.list()
        self.assertEquals(len(result), 1)

        with self.client_using_tenant(self.alice_client,
                                      tenant_name=DEFAULT_TENANT_NAME):
            result = self.alice_client.blueprints.list()
        self.assertEquals(len(result), 1)
        self.assertEqual(result[0].id, 'alice_bp')

        with self.client_using_tenant(self.alice_client,
                                      tenant_name='TEST_TENANT'):
            result = self.alice_client.blueprints.list()
        self.assertEquals(len(result), 1)
        self.assertEqual(result[0].id, 'fred_bp')

    def test_list_blueprints_not_authorized(self):
        error_msg = '403: User `fred` is not permitted to perform the ' \
                    'action blueprint_list in the tenant `default_tenant`'
        with self.client_using_tenant(self.fred_client, DEFAULT_TENANT_NAME):
            self.assertRaisesRegexp(CloudifyClientError,
                                    error_msg,
                                    self.fred_client.blueprints.list)

    def test_admin_list_blueprints_non_existing_tenant(self):
        error_msg = '403: Authorization failed: Tried to authenticate with ' \
                    'invalid tenant name: non_existing_tenant'
        with self.client_using_tenant(self.client, 'non_existing_tenant'):
            self.assertRaisesRegexp(CloudifyClientError,
                                    error_msg,
                                    self.client.blueprints.list)

    def test_list_blueprints_non_existing_tenant(self):
        error_msg = '403: Authorization failed: Tried to authenticate with ' \
                    'invalid tenant name: non_existing_tenant'
        with self.client_using_tenant(self.alice_client,
                                      tenant_name='non_existing_tenant'):
            self.assertRaisesRegexp(CloudifyClientError,
                                    error_msg,
                                    self.alice_client.blueprints.list)

    # Assert that if no tenants were passed, response will contain only the
    # blueprints associated with the current tenant.
    def test_list_blueprints_no_filters(self):
        self._upload_blueprints_to_different_tenants()
        result = self.alice_client.blueprints.list()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, 'alice_bp')

    def test_list_blueprints_all_tenants_flag(self):
        self._upload_blueprints_to_different_tenants()
        result = self.alice_client.blueprints.list(_all_tenants=True)
        self.assertEqual(len(result), 2)

    def _upload_blueprints_to_different_tenants(self,
                                                alice_bp_id='alice_bp',
                                                fred_bp_id='fred_bp'):
        blueprint_path = resource('dsl/empty_blueprint.yaml')
        self.alice_client.blueprints.upload(path=blueprint_path,
                                            entity_id=alice_bp_id)
        self.fred_client.blueprints.upload(path=blueprint_path,
                                           entity_id=fred_bp_id)
