#########
# Copyright (c) 2020 Cloudify Platform Ltd. All rights reserved
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

        keys_list = viewer_client.deployments_labels.list_keys()
        self.assertEqual(set(keys_list.items), {'key1', 'key2'})

        values_list = viewer_client.deployments_labels.list_key_values('key1')
        self.assertEqual(set(values_list.items), {'val1', 'val2'})

    def test_list_keys_and_values_from_global_deployment(self):
        """
        We should be able to list the labels' keys and values of the
        deployments in the current tenant, and of the deployments with
        global visibility in other tenants.
        """
        self.client.tenants.create('new_tenant')
        new_tenant_client = utils.create_rest_client(
            host=self.env.container_ip, tenant='new_tenant')
        self._put_deployment_with_labels(self.client, self.LABELS)
        self._put_deployment_with_labels(new_tenant_client,
                                         self.LABELS_2,
                                         VisibilityState.GLOBAL)

        keys_list = self.client.deployments_labels.list_keys()
        self.assertEqual(set(keys_list.items), {'key1', 'key2', 'key3'})

        values_list = self.client.deployments_labels.list_key_values('key1')
        self.assertEqual(set(values_list.items), {'val1', 'val2', 'val3'})

    def _put_deployment_with_labels(self,
                                    client,
                                    labels,
                                    visibility=VisibilityState.TENANT):
        dsl_path = utils.get_resource('dsl/basic.yaml')
        blueprint_id = deployment_id = 'd{0}'.format(uuid.uuid4())
        client.blueprints.upload(dsl_path, blueprint_id, visibility=visibility)
        deployment = client.deployments.create(blueprint_id,
                                               deployment_id,
                                               visibility=visibility,
                                               labels=labels)
        utils.wait_for_deployment_creation_to_complete(self.env.container_id,
                                                       deployment_id,
                                                       self.client)
        return deployment
