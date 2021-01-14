import pytest

from cloudify.models_states import VisibilityState
from cloudify_rest_client.exceptions import CloudifyClientError, ForbiddenError

from integration_tests.tests import utils
from integration_tests import AgentlessTestCase

from .test_labels import LABELS, LABELS_2


@pytest.mark.usefixtures('cloudmock_plugin')
class FiltersTest(AgentlessTestCase):
    FILTER_ID = 'filter'
    SIMPLE_RULE = ['a=b']

    def test_viewer_can_create_filter(self):
        viewer_client = self.create_client_with_user_role('viewer')
        self._create_filter(viewer_client)

    def test_creator_can_update_filter(self):
        self._test_update_filter()

    def test_admin_can_update_filter(self):
        self._test_update_filter(updater_client=self.client)

    def test_update_filter_fails(self):
        new_client = self.create_client_with_user_role('user', 'user2')
        with self.assertRaisesRegex(
                ForbiddenError, 'User `user2` is not permitted to modify.*'):
            self._test_update_filter(updater_client=new_client)

    def test_list_filters_from_all_tenants(self):
        new_tenant_client = self._create_new_tenant()
        self._create_filter()
        self._create_filter(new_tenant_client, 'filter_2')
        filters_list = self.client.filters.list(_all_tenants=True)
        self.assertEqual(len(filters_list), 2)
        self.assertEqual(
            set(filter_elem.id for filter_elem in filters_list),
            {self.FILTER_ID, 'filter_2'})

    def test_conflict_with_global_filter(self):
        new_tenant_client = self._create_new_tenant()
        self._create_filter(visibility=VisibilityState.GLOBAL)
        with self.assertRaisesRegex(
                CloudifyClientError, '.*with global visibility'):
            self._create_filter(client=new_tenant_client)

    def test_list_deployments_with_filters_all_tenants(self):
        """
        Tests that deployments with the same ID on different tenants are
        being filtered successfully
        """
        dep_id = 'dep1'
        new_tenant_client = self._create_new_tenant()
        self.put_deployment_with_labels(self.client, LABELS, dep_id)
        self.put_deployment_with_labels(new_tenant_client, LABELS_2, dep_id)

        deployments_list_1 = self.client.deployments.list(
            filter_rules=['key1=val1'], _all_tenants=True)
        self.assertEqual(len(deployments_list_1), 2)

        deployments_list_2 = self.client.deployments.list(
            filter_rules=['key1=val1', 'key3 is not null'], _all_tenants=True)
        self.assertEqual(len(deployments_list_2), 1)
        self.assertEqual(deployments_list_2[0]['tenant_name'], 'new_tenant')

    def _create_filter(self, client=None, filter_name=None, filter_rules=None,
                       visibility=VisibilityState.TENANT):
        client = client or self.client
        filter_name = filter_name or self.FILTER_ID
        filter_rules = filter_rules or self.SIMPLE_RULE
        new_filter = client.filters.create(
            filter_name, filter_rules, visibility)
        self.assertEqual(new_filter.labels_filter, filter_rules)

    def _test_update_filter(self, updater_client=None):
        """Filter can be updated only by the filter creator or by sys-admin"""
        viewer_client = self.create_client_with_user_role('viewer')
        self._create_filter(viewer_client)
        updater_client = updater_client or viewer_client
        updated_filter = updater_client.filters.update(self.FILTER_ID, ['c=d'])
        self.assertEqual(updated_filter.id, self.FILTER_ID)
        self.assertEqual(updated_filter.labels_filter, ['c=d'])

    def _create_new_tenant(self):
        self.client.tenants.create('new_tenant')
        return utils.create_rest_client(
            host=self.env.container_ip, tenant='new_tenant')
