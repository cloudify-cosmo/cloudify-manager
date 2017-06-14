########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

from uuid import uuid4
from functools import wraps

from pyrabbit.api import Client
from pyrabbit.http import HTTPError


def ignore_not_found(func):
    """ Helper decorator to ignore not found errors """

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except HTTPError, e:
            if e.status == 404:
                pass
            else:
                raise
    return wrapper


class AMQPManager(object):
    RABBITMQ_MANAGEMENT_PORT = 15672
    VHOST_NAME_PATTERN = 'rabbitmq_vhost_{0}'
    USERNAME_PATTERN = 'rabbitmq_user_{0}'

    def __init__(self, host, username, password):
        host_str = '{0}:{1}'.format(host, self.RABBITMQ_MANAGEMENT_PORT)
        self._client = Client(host_str, username, password)

    def create_tenant_vhost_and_user(self, tenant):
        """
        Create a new RabbitMQ vhost and user, and grant the user permissions
        on the vhost
        :param tenant: An SQLAlchemy Tenant object
        :return: The updated tenant object
        """
        vhost = tenant.rabbitmq_vhost or \
            self.VHOST_NAME_PATTERN.format(tenant.name)
        username = tenant.rabbitmq_username or \
            self.USERNAME_PATTERN.format(tenant.name)
        password = tenant.rabbitmq_password or str(uuid4())

        self._client.create_vhost(vhost)
        self._client.create_user(username, password)
        self._client.set_vhost_permissions(vhost, username, '.*', '.*', '.*')

        # TODO: Maybe won't be necessary in the future
        self._client.set_vhost_permissions('/', username, '.*', '.*', '.*')

        tenant.rabbitmq_vhost = vhost
        tenant.rabbitmq_username = username
        tenant.rabbitmq_password = password

        return tenant

    def sync_metadata(self, tenants):
        """Synchronize database tenants with rabbitmq metadata.

        :param tenants: Tenants currently available in the database
        :type tentans: list(manager_rest.storage.management_models.Tenant)

        """
        # Remove vhosts in rabbitmq not present in the database
        expected_vhosts = set(tenant.rabbitmq_vhost for tenant in tenants)
        current_vhosts = set(
            vhost
            for vhost in self._client.get_vhost_names()
            if vhost.startswith(self.VHOST_NAME_PATTERN[:-3])
        )
        extra_vhosts = current_vhosts - expected_vhosts
        for vhost in extra_vhosts:
            self._client.delete_vhost(vhost)

        # Remove users in rabbitmq not present in the database
        expected_usernames = set(
            tenant.rabbitmq_username for tenant in tenants)
        current_usernames = set(
            user['name']
            for user in self._client.get_users()
            if user['name'].startswith(self.USERNAME_PATTERN[:-3])
        )
        extra_usernames = current_usernames - expected_usernames
        for username in extra_usernames:
            self._client.delete_user(username)

        # Create vhosts and users present in the database
        for tenant in tenants:
            self.create_tenant_vhost_and_user(tenant)

    @ignore_not_found
    def _delete_vhost(self, vhost):
        self._client.delete_vhost(vhost)

    @ignore_not_found
    def _delete_user(self, username):
        self._client.delete_user(username)

    def remove_tenant_vhost_and_user(self, tenant_name):
        """ Delete the vhost and user associated with a tenant name """

        vhost = self.VHOST_NAME_PATTERN.format(tenant_name)
        username = self.USERNAME_PATTERN.format(tenant_name)

        self._delete_vhost(vhost)
        self._delete_user(username)
