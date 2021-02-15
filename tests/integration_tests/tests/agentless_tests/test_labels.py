import uuid
import pytest

from cloudify.models_states import VisibilityState

from integration_tests.tests import utils
from integration_tests import AgentlessTestCase


@pytest.mark.usefixtures('cloudmock_plugin')
class DeploymentsLabelsTest(AgentlessTestCase):
    LABELS = [{'key1': 'val1'}, {'key1': 'val2'}, {'key2': 'val3'}]
    LABELS_2 = [{'key1': 'val1'}, {'key1': 'val3'}, {'key3': 'val3'}]

    def test_viewer_labels_permissions(self):
        """A "viewer" is allowed to list the labels' keys and values."""
        self._put_deployment_with_labels(self.client, self.LABELS)
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
        self._put_deployment_with_labels(self.client, self.LABELS)
        self._put_deployment_with_labels(new_tenant_client,
                                         self.LABELS_2,
                                         VisibilityState.GLOBAL)

        self._assert_keys_and_values(self.client,
                                     {'key1': {'val1', 'val2', 'val3'},
                                      'key2': {'val3'},
                                      'key3': {'val3'}})

    def test_upload_blueprint_with_labels(self):
        new_labels = [{'key1': 'key1_val1'}, {'key3': 'val3'}]
        dsl_path = utils.get_resource('dsl/blueprint_with_labels.yaml')
        blueprint_id = deployment_id = 'd{0}'.format(uuid.uuid4())
        self.client.blueprints.upload(dsl_path, blueprint_id)
        deployment = self.client.deployments.create(blueprint_id,
                                                    deployment_id,
                                                    labels=new_labels)
        utils.wait_for_deployment_creation_to_complete(self.env.container_id,
                                                       deployment_id,
                                                       self.client)
        labels_list = [{'key1': 'key1_val1'}, {'key2': 'key2_val1'},
                       {'key2': 'key2_val2'}, {'key3': 'val3'}]
        self._assert_deployment_labels(deployment.labels, labels_list)

    def _assert_keys_and_values(self, client, keys_values_dict):
        keys_list = client.deployments_labels.list_keys()
        self.assertEqual(set(keys_list.items), set(keys_values_dict.keys()))

        for key, values in keys_values_dict.items():
            values_list = self.client.deployments_labels.list_key_values(key)
            self.assertEqual(set(values_list.items), values)

    def _put_deployment_with_labels(self,
                                    client,
                                    labels,
                                    visibility=VisibilityState.TENANT):
        dsl_path = utils.get_resource('dsl/basic.yaml')
        blueprint_id = deployment_id = 'd{0}'.format(uuid.uuid4())
        client.blueprints.upload(dsl_path, blueprint_id, visibility=visibility)
        utils.wait_for_blueprint_upload(blueprint_id, client)
        deployment = client.deployments.create(blueprint_id,
                                               deployment_id,
                                               visibility=visibility,
                                               labels=labels)
        utils.wait_for_deployment_creation_to_complete(self.env.container_id,
                                                       deployment_id,
                                                       self.client)
        return deployment

    def _assert_deployment_labels(self, deployment_labels, compared_labels):
        simplified_labels = set()
        compared_labels_set = set()

        for label in deployment_labels:
            simplified_labels.add((label['key'], label['value']))

        for compared_label in compared_labels:
            [(key, value)] = compared_label.items()
            compared_labels_set.add((key, value))

        self.assertEqual(simplified_labels, compared_labels_set)
