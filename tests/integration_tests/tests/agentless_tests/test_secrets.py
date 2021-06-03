########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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

import pytest

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource
from cloudify_rest_client.exceptions import CloudifyClientError, ForbiddenError

pytestmark = pytest.mark.group_general


class SecretsTest(AgentlessTestCase):

    def test_create_encrypted_secret(self):
        new_secret = self.client.secrets.create('test_key', 'test_value')
        self.assertNotEqual('test_value', new_secret.value)

    def test_get_decrypted_secret(self):
        new_secret = self.client.secrets.create('test_key', 'test_value')
        received_secret = self.client.secrets.get(new_secret.key)
        self.assertEqual(received_secret.key, new_secret.key)
        self.assertEqual(received_secret.value, 'test_value')

    def test_update_encrypted_secret(self):
        key = 'test_key'
        self.client.secrets.create(key, 'test_value')
        updated_secret = self.client.secrets.update(key, 'test_value2')
        self.assertNotEqual('test_value2', updated_secret.value)
        updated_secret = self.client.secrets.get(key)
        self.assertEqual('test_value2', updated_secret.value)

    def test_get_secret_not_found(self):
        self.assertRaisesRegexp(
            CloudifyClientError,
            '404: Requested `Secret` with ID `test_key` was not found',
            self.client.secrets.get,
            'test_key'
        )

    def test_get_secret_intrinsic_function(self):
        dsl_path = resource("dsl/basic_get_secret.yaml")
        error_msg = "Required secrets: .* don't exist in this tenant"
        self.assertRaisesRegexp(
            CloudifyClientError,
            error_msg,
            self.deploy_application,
            dsl_path
        )

        # Manage to create deployment after creating the secret
        self.client.secrets.create('port', '8080')
        deployment, _ = self.deploy_application(dsl_path)

    def test_secret_export_not_authorized(self):
        self.client.secrets.create('key', 'value')
        self.client.users.create('user', 'password', 'default')
        self.client.tenants.add_user('user', 'default_tenant', 'viewer')
        viewer_client = self.create_rest_client(
            username='user', password='password', tenant='default_tenant',
        )
        self.assertRaisesRegexp(ForbiddenError,
                                '403: User `user` is not permitted to perform'
                                ' the action secret_export in the tenant '
                                '`default_tenant`',
                                viewer_client.secrets.export)
