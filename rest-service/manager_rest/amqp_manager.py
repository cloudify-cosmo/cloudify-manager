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

from requests.exceptions import HTTPError

from functools import wraps

from cloudify.models_states import AgentState
from cloudify.utils import generate_user_password
from cloudify.cryptography_utils import encrypt, decrypt
from cloudify.rabbitmq_client import RabbitMQClient, USERNAME_PATTERN

from manager_rest.storage import get_storage_manager
from manager_rest.storage.models import Tenant, Agent


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


class AMQPManager(object):

    VHOST_NAME_PATTERN = 'rabbitmq_vhost_{0}'

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
        username, encrypted_password = self._create_rabbitmq_user(tenant)
        vhost = tenant.rabbitmq_vhost or \
            self.VHOST_NAME_PATTERN.format(tenant.name)
        self._client.create_vhost(vhost)
        self._client.set_vhost_permissions(vhost, username, '.*', '.*', '.*')

        # Gives configure and write permissions to the specific exchanges of
        # events, logs and monitoring. The exchange cloudify-events-topic
        # is the new events exchange and cloudify-events permissions are being
        # kept for old agents upgrades.
        allowed_resources = '^cloudify-(events-topic|events|logs|monitoring)$'
        self._client.set_vhost_permissions('/',
                                           username,
                                           configure=allowed_resources,
                                           write=allowed_resources)
        tenant.rabbitmq_vhost = vhost
        tenant.rabbitmq_username = username
        tenant.rabbitmq_password = encrypted_password

        return tenant

    def create_agent_user(self, agent):
        """
        Create a new RabbitMQ user, and grant the user permissions
        :param agent: An SQLAlchemy Agent object
        :return: The updated agent object
        """
        username, encrypted_password = self._create_rabbitmq_user(agent)
        self._set_agent_rabbitmq_user_permissions(username,
                                                  agent.rabbitmq_exchange,
                                                  agent.tenant.rabbitmq_vhost)
        agent.rabbitmq_username = username
        agent.rabbitmq_password = encrypted_password
        return agent

    def sync_metadata(self):
        """Synchronize database tenants with rabbitmq metadata"""

        tenants = self._storage_manager.list(Tenant, get_all_results=True)
        agents = self._storage_manager.list(Agent, get_all_results=True)
        self._clear_extra_vhosts(tenants)
        self._clear_extra_users(tenants, agents)
        self._add_missing_vhosts_and_users(tenants, agents)

    def _create_rabbitmq_user(self, resource):
        username = resource.rabbitmq_username or \
                   USERNAME_PATTERN.format(resource.name)

        # The password is being stored encrypted in the DB
        new_password = generate_user_password()
        password = decrypt(resource.rabbitmq_password) \
            if resource.rabbitmq_password else new_password
        encrypted_password = resource.rabbitmq_password or \
            encrypt(new_password)

        self._client.create_user(username, password)
        return username, encrypted_password

    def _add_missing_vhosts_and_users(self, tenants, agents):
        """Create vhosts and users present in the database"""

        for tenant in tenants:
            updated_tenant = self.create_tenant_vhost_and_user(tenant)
            self._storage_manager.update(updated_tenant)

        for agent in agents:
            if agent.state != AgentState.RESTORED:
                updated_agent = self.create_agent_user(agent)
                self._storage_manager.update(updated_agent)

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

    def _clear_extra_users(self, tenants, agents):
        """Remove users in rabbitmq not present in the database"""
        expected_usernames = self._get_rabbitmq_users(tenants).union(
            self._get_rabbitmq_users(agents))
        current_usernames = set(
            user['name']
            for user in self._client.get_users()
            if user['name'].startswith(USERNAME_PATTERN[:-3])
        )
        extra_usernames = current_usernames - expected_usernames
        for username in extra_usernames:
            self._client.delete_user(username)

    def _get_rabbitmq_users(self, resources):
        return set(
            resource.rabbitmq_username
            for resource in resources
            if resource.rabbitmq_username  # Ignore None values
        )

    @ignore_not_found
    def _delete_vhost(self, vhost):
        self._client.delete_vhost(vhost)

    @ignore_not_found
    def _delete_user(self, username):
        self._client.delete_user(username)

    def remove_tenant_vhost_and_user(self, tenant_name):
        """ Delete the vhost and user associated with a tenant name """

        vhost = self.VHOST_NAME_PATTERN.format(tenant_name)
        username = USERNAME_PATTERN.format(tenant_name)

        self._delete_vhost(vhost)
        self._delete_user(username)

    def _set_agent_rabbitmq_user_permissions(self,
                                             username,
                                             exchange,
                                             tenant_vhost):
        # Gives the user permissions only to these resources in the tenant
        # vhost:
        # 1. The agent's exchange
        # 2. The agent's queues (for receiving tasks and sending responses)
        # 3. The exchanges of events, logs and monitoring
        allowed_resources = '^(cloudify-(events-topic|logs|monitoring)|' \
                            '{exchange}($|_(operation|workflow|service|' \
                            'response_.*))$)'.format(exchange=exchange)
        self._client.set_vhost_permissions(tenant_vhost,
                                           username,
                                           configure=allowed_resources,
                                           write=allowed_resources,
                                           read=allowed_resources)

        # Gives configure and write permissions to the specific exchanges of
        # events, logs and monitoring in the root vhost
        allowed_resources = '^cloudify-(events-topic|logs|monitoring)$'
        self._client.set_vhost_permissions('/',
                                           username,
                                           configure=allowed_resources,
                                           write=allowed_resources)
