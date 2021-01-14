import pytest

from cloudify.models_states import VisibilityState

from integration_tests.tests import utils
from integration_tests import AgentlessTestCase

LABELS = [{'key1': 'val1'}, {'key1': 'val2'}, {'key2': 'val3'}]
LABELS_2 = [{'key1': 'val1'}, {'key1': 'val3'}, {'key3': 'val3'}]


@pytest.mark.usefixtures('cloudmock_plugin')
class DeploymentsLabelsTest(AgentlessTestCase):
    def test_viewer_labels_permissions(self):
        """A "viewer" is allowed to list the labels' keys and values."""
        self.put_deployment_with_labels(self.client, LABELS)
        self.client.users.create('user', 'password', role='default')
        self.client.tenants.add_user('user', 'default_tenant', role='viewer')
        viewer_client = utils.create_rest_client(host=self.env.container_ip,
                                                 username='user',
                                                 password='password',
                                                 tenant='default_tenant')

        self._assert_keys_and_values(viewer_client,
                                     {'key1': {'val1', 'val2'},
                                      'key2': {'val3'}})

    def test_list_keys_and_values_from_global_deployment(self):
        """
        Listing the labels' keys and values of the deployments in the current
        tenant, and of global visibility deployments in other tenants.
        """
        self.client.tenants.create('new_tenant')
        new_tenant_client = utils.create_rest_client(
            host=self.env.container_ip, tenant='new_tenant')
        self.put_deployment_with_labels(self.client, LABELS)
        self.put_deployment_with_labels(new_tenant_client,
                                        LABELS_2,
                                        visibility=VisibilityState.GLOBAL)

        self._assert_keys_and_values(self.client,
                                     {'key1': {'val1', 'val2', 'val3'},
                                      'key2': {'val3'},
                                      'key3': {'val3'}})

    def _assert_keys_and_values(self, client, keys_values_dict):
        keys_list = client.deployments_labels.list_keys()
        self.assertEqual(set(keys_list.items), set(keys_values_dict.keys()))

        for key, values in keys_values_dict.items():
            values_list = self.client.deployments_labels.list_key_values(key)
            self.assertEqual(set(values_list.items), values)
