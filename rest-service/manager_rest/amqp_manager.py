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

import random
import string
import requests
from urllib import quote
from requests.exceptions import HTTPError

from functools import wraps

from manager_rest.storage.models import Tenant
from manager_rest.storage import get_storage_manager
from manager_rest.cryptography_utils import encrypt, decrypt


def ignore_not_found(func):
    """ Helper decorator to ignore not found errors """

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except HTTPError as e:
            if e.response.status_code == 404:
                pass
            else:
                raise
    return wrapper


RABBITMQ_MANAGEMENT_PORT = 15671


class RabbitMQClient(object):
    def __init__(self, host, username, password, port=RABBITMQ_MANAGEMENT_PORT,
                 scheme='https', **request_kwargs):
        self._host = host
        self._port = port
        self._scheme = scheme
        request_kwargs.setdefault('auth', (username, password))
        self._request_kwargs = request_kwargs

    @property
    def base_url(self):
        return '{0}://{1}:{2}'.format(self._scheme, self._host, self._port)

    def _do_request(self, request_method, url, **kwargs):
        request_kwargs = self._request_kwargs.copy()
        request_kwargs.update(kwargs)
        request_kwargs.setdefault('headers', {})\
            .setdefault('Content-Type', 'application/json',)

        url = '{0}/api/{1}'.format(self.base_url, url)
        response = request_method(url, **request_kwargs)
        response.raise_for_status()
        return response

    def get_vhost_names(self):
        vhosts = self._do_request(requests.get, 'vhosts').json()
        return [vhost['name'] for vhost in vhosts]

    def create_vhost(self, vhost):
        vhost = quote(vhost, '')
        self._do_request(requests.put, 'vhosts/{0}'.format(vhost))

    def delete_vhost(self, vhost):
        vhost = quote(vhost, '')
        self._do_request(requests.delete, 'vhosts/{0}'.format(vhost))

    def get_users(self):
        return self._do_request(requests.get, 'users').json()

    def create_user(self, username, password, tags=''):
        self._do_request(requests.put, 'users/{0}'.format(username),
                         json={'password': password, 'tags': tags})

    def delete_user(self, username):
        self._do_request(requests.delete, 'users/{0}'.format(username))

    def set_vhost_permissions(self, vhost, username, configure='', write='',
                              read=''):
        vhost = quote(vhost, '')
        self._do_request(requests.put,
                         'permissions/{0}/{1}'.format(vhost, username),
                         json={
                             'configure': configure,
                             'write': write,
                             'read': read
                         })


class AMQPManager(object):

    VHOST_NAME_PATTERN = 'rabbitmq_vhost_{0}'
    USERNAME_PATTERN = 'rabbitmq_user_{0}'

    def __init__(self, host, username, password, **request_kwargs):
        self._client = RabbitMQClient(host, username, password,
                                      **request_kwargs)
        self._storage_manager = get_storage_manager()

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

        # The password is being stored encrypted in the DB
        new_password = AMQPManager._generate_user_password()
        password = decrypt(tenant.rabbitmq_password) \
            if tenant.rabbitmq_password else new_password
        encrypted_password = tenant.rabbitmq_password or encrypt(new_password)

        self._client.create_vhost(vhost)
        self._client.create_user(username, password)
        self._client.set_vhost_permissions(vhost, username, '.*', '.*', '.*')

        # Gives configure and write permissions to the specific exchanges of
        # events, logs and monitoring
        allowed_resources = '^cloudify-(events|logs|monitoring)$'
        self._client.set_vhost_permissions('/',
                                           username,
                                           configure=allowed_resources,
                                           write=allowed_resources)
        tenant.rabbitmq_vhost = vhost
        tenant.rabbitmq_username = username
        tenant.rabbitmq_password = encrypted_password

        return tenant

    def sync_metadata(self):
        """Synchronize database tenants with rabbitmq metadata"""

        tenants = self._storage_manager.list(Tenant, get_all_results=True)
        self._clear_extra_vhosts(tenants)
        self._clear_extra_users(tenants)
        self._add_missing_vhosts_and_users(tenants)

    def _add_missing_vhosts_and_users(self, tenants):
        """Create vhosts and users present in the database"""

        for tenant in tenants:
            t = self.create_tenant_vhost_and_user(tenant)
            self._storage_manager.update(t)

    def _clear_extra_vhosts(self, tenants):
        """Remove vhosts in rabbitmq not present in the database"""

        expected_vhosts = set(
            tenant.rabbitmq_vhost
            for tenant in tenants
            if tenant.rabbitmq_vhost  # Ignore None values
        )
        current_vhosts = set(
            vhost
            for vhost in self._client.get_vhost_names()
            if vhost.startswith(self.VHOST_NAME_PATTERN[:-3])
        )
        extra_vhosts = current_vhosts - expected_vhosts
        for vhost in extra_vhosts:
            self._client.delete_vhost(vhost)

    def _clear_extra_users(self, tenants):
        """Remove users in rabbitmq not present in the database"""

        expected_usernames = set(
            tenant.rabbitmq_username
            for tenant in tenants
            if tenant.rabbitmq_username  # Ignore None values
        )
        current_usernames = set(
            user['name']
            for user in self._client.get_users()
            if user['name'].startswith(self.USERNAME_PATTERN[:-3])
        )
        extra_usernames = current_usernames - expected_usernames
        for username in extra_usernames:
            self._client.delete_user(username)

    @staticmethod
    def _generate_user_password(password_length=32):
        """Generate random string to use as user password."""
        system_random = random.SystemRandom()
        allowed_characters = (
            string.letters +
            string.digits +
            '-_'
        )

        password = ''.join(
            system_random.choice(allowed_characters)
            for _ in xrange(password_length)
        )
        return password

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
