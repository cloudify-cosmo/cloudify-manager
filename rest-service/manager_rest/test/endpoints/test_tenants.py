#########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
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

from mock import patch

from manager_rest import constants, config
from manager_rest.storage import models

from cloudify.cryptography_utils import encrypt
from cloudify_rest_client.exceptions import CloudifyClientError

from manager_rest.test import base_test


CREDENTIALS_PERMISSION = 'tenant_rabbitmq_credentials'


@patch('manager_rest.security.secured_resource.premium_enabled', False)
class TenantsCommunityTestCase(base_test.BaseServerTestCase):
    def test_list_tenants(self):
        """Listing tenants is allowed on community."""
        result = self.client.tenants.list()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['name'], constants.DEFAULT_TENANT_NAME)

    def test_get_tenant_no_permission(self):
        """Getting a tenant without the credentials permission, gives
        the tenants details but without rabbitmq credentials.
        """
        with patch.dict(config.instance.authorization_permissions,
                        {CREDENTIALS_PERMISSION: []}):
            result = self.client.tenants.get(constants.DEFAULT_TENANT_NAME)
        self.assertEqual(result['name'], constants.DEFAULT_TENANT_NAME)
        for key in ['username', 'password', 'vhost']:
            self.assertIsNone(result['rabbitmq_' + key])

    def test_get_tenant_permission(self):
        """Getting a tenant with the credentials permission, the full
        tenant details, including the rabbitmq credentials.
        """
        password = 'password1234'
        self.tenant.rabbitmq_password = encrypt(password)

        with patch.dict(config.instance.authorization_permissions,
                        {CREDENTIALS_PERMISSION: ['user']}):
            result = self.client.tenants.get(constants.DEFAULT_TENANT_NAME)

        assert result['name'] == constants.DEFAULT_TENANT_NAME
        assert result['rabbitmq_username'] == self.tenant.rabbitmq_username
        assert result['rabbitmq_vhost'] == self.tenant.rabbitmq_vhost
        assert result['rabbitmq_password'] == password

    def test_get_nondefault_tenant(self):
        """Getting tenants other than default_tenant is disallowed on
        community.
        (there shouldn't be a way to create them anyway)
        """
        self.sm.put(models.Tenant(name='another_tenant'))
        with self.assertRaises(CloudifyClientError) as cm:
            self.client.tenants.get('another_tenant')
        self.assertEqual(
            cm.exception.error_code, 'missing_premium_package_error')

    def test_put_tenant(self):
        """Creating tenants is disallowed on community."""
        with self.assertRaises(CloudifyClientError) as cm:
            self.client.tenants.create('another_tenant')
        self.assertEqual(
            cm.exception.error_code, 'missing_premium_package_error')

    def test_delete_tenant(self):
        """Creating tenants is disallowed on community."""
        with self.assertRaises(CloudifyClientError) as cm:
            self.client.tenants.delete('another_tenant')
        self.assertEqual(
            cm.exception.error_code, 'missing_premium_package_error')
