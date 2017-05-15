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

    def create_vhost_user_from_tenant(self, tenant):
        """
        Create a new RabbitMQ vhost and user, and grant the user permissions
        on the vhost
        :param tenant: An SQLAlchemy Tenant object
        :return: The updated tenant object
        """
        vhost = self.VHOST_NAME_PATTERN.format(tenant.name)
        username = self.USERNAME_PATTERN.format(tenant.name)
        password = str(uuid4())

        self._client.create_vhost(vhost)
        self._client.create_user(username, password)
        self._client.set_vhost_permissions(vhost, username, '.*', '.*', '.*')

        # Give the user permissions on the default vhost - /
        self._client.set_vhost_permissions('/', username, '.*', '.*', '.*')

        tenant.rabbitmq_vhost = vhost
        tenant.rabbitmq_username = username
        tenant.rabbitmq_password = password

        return tenant

    @ignore_not_found
    def _delete_vhost(self, vhost):
        self._client.delete_vhost(vhost)

    @ignore_not_found
    def _delete_user(self, username):
        self._client.delete_user(username)

    def remove_vhost_user_from_tenant(self, tenant_name):
        """ Delete the vhost and user associated with a tenant name """

        vhost = self.VHOST_NAME_PATTERN.format(tenant_name)
        username = self.USERNAME_PATTERN.format(tenant_name)

        self._delete_vhost(vhost)
        self._delete_user(username)
