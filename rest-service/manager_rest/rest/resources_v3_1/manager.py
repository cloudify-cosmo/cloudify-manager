#########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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

import json
from subprocess import check_call

from flask import request, current_app
from flask_restful.reqparse import Argument

from manager_rest import manager_exceptions
from manager_rest.security import (
    SecuredResource,
    premium_only
)
from manager_rest.security.authorization import (
    authorize,
    is_user_action_allowed
)
from manager_rest.storage import (
    get_storage_manager,
    models
)

from .. import rest_utils
from ..rest_decorators import (
    exceptions_handled,
    marshal_with,
    paginate,
)


try:
    from cloudify_premium.ha import (
        add_manager,
        remove_manager,
    )
    from cloudify_premium.ha.agents import update_agents
except ImportError:
    add_manager, remove_manager, update_agents = None, None, None


DEFAULT_CONF_PATH = '/etc/nginx/conf.d/cloudify.conf'
HTTP_PATH = '/etc/nginx/conf.d/http-external-rest-server.cloudify'
HTTPS_PATH = '/etc/nginx/conf.d/https-external-rest-server.cloudify'


def check_private_address_is_in_networks(address, networks):
    if address not in networks.values():
        raise manager_exceptions.BadParametersError(
            'Supplied address {address} was not found in networks: '
            '{networks}'.format(
                address=address,
                networks=json.dumps(networks),
            )
        )


class SSLConfig(SecuredResource):
    @exceptions_handled
    @authorize('ssl_set')
    def post(self):
        """
        Enable/Disable SSL
        """
        request_dict = rest_utils.get_json_and_verify_params({'state'})
        state = rest_utils.verify_and_convert_bool('state',
                                                   request_dict.get('state'))
        status = 'enabled' if state else 'disabled'
        if state == SSLConfig._is_enabled():
            return 'SSL is already {0} on the manager'.format(status)
        else:
            self._set_ssl_state(state)
        return 'SSL is now {0} on the manager'.format(status)

    @exceptions_handled
    @authorize('ssl_get')
    def get(self):
        """
        Get ssl state (enabled/disabled)
        """
        return 'SSL {0}'.format(
            'enabled' if SSLConfig._is_enabled() else 'disabled')

    @staticmethod
    def _is_enabled():
        return request.scheme == 'https'

    @staticmethod
    def _set_ssl_state(state):
        flag = '--ssl-enabled' if state else '--ssl-disabled'
        check_call(['sudo', '/opt/manager/scripts/set-manager-ssl.py',
                    flag])


class Managers(SecuredResource):
    @exceptions_handled
    @marshal_with(models.Manager)
    @paginate
    @authorize('manager_get')
    def get(self, pagination=None, _include=None):
        """
        Get the list of managers in the database
        :param hostname: optional hostname to return only a specific manager
        :param _include: optional, what columns to include in the response
        """
        args = rest_utils.get_args_and_verify_arguments([
            Argument('hostname', type=unicode, required=False)
        ])
        hostname = args.get('hostname')
        if hostname:
            return get_storage_manager().list(
                models.Manager,
                None,
                filters={'hostname': hostname}
            )
        return get_storage_manager().list(
            models.Manager,
            include=_include
        )

    @exceptions_handled
    @authorize('manager_manage')
    @marshal_with(models.Manager)
    @premium_only
    def post(self):
        """
        Create a new manager
        """
        manager = rest_utils.get_json_and_verify_params({
            'hostname': {'type': unicode},
            'private_ip': {'type': unicode},
            'public_ip': {'type': unicode},
            'version': {'type': unicode},
            'edition': {'type': unicode},
            'distribution': {'type': unicode},
            'distro_release': {'type': unicode},
            'ca_cert_content': {'type': unicode, 'optional': True},
            'fs_sync_node_id': {'type': unicode, 'optional': True},
            'networks': {'type': dict, 'optional': True}
        })

        check_private_address_is_in_networks(
            manager['private_ip'],
            manager['networks'],
        )

        sm = get_storage_manager()
        ca_cert_id = self._get_ca_cert_id(sm, manager)
        new_manager = models.Manager(
            hostname=manager['hostname'],
            private_ip=manager['private_ip'],
            public_ip=manager['public_ip'],
            version=manager['version'],
            edition=manager['edition'],
            distribution=manager['distribution'],
            distro_release=manager['distro_release'],
            fs_sync_node_id=manager.get('fs_sync_node_id', ''),
            networks=manager.get('networks'),
            _ca_cert_id=ca_cert_id,
        )
        result = sm.put(new_manager)
        current_app.logger.info('Manager added successfully')
        if add_manager and manager.get('fs_sync_node_id'):
            managers_list = get_storage_manager().list(models.Manager)
            add_manager(managers_list)
        if update_agents:
            update_agents(sm)
        return result

    def _get_ca_cert_id(self, sm, manager):
        ca_cert_content = manager.get('ca_cert_content')
        if ca_cert_content:
            ca_cert = sm.put(models.Certificate(
                name='{0}-ca'.format(manager['hostname']),
                value=ca_cert_content
            ))
            return ca_cert.id
        else:
            # if CA content is not given, use the one used by other managers
            # (this means exactly one CA must be used by other managers)
            existing_managers_certs = {m._ca_cert_id
                                       for m in sm.list(models.Manager)}
            if len(existing_managers_certs) != 1:
                raise manager_exceptions.ConflictError(
                    'ca_cert_content not given, but {0} existing CA '
                    'certs found'.format(len(existing_managers_certs)))
            return existing_managers_certs.pop()


class ManagersId(SecuredResource):
    @exceptions_handled
    @authorize('manager_manage')
    @marshal_with(models.Manager)
    @premium_only
    def put(self, name):
        """
        Update a manager's FS sync node ID required by syncthing
        """
        manager = rest_utils.get_json_and_verify_params({
            'fs_sync_node_id': {'type': unicode},
            'bootstrap_cluster': {'type': bool}
        })
        sm = get_storage_manager()
        manager_to_update = sm.get(
            models.Manager,
            None,
            filters={'hostname': name}
        )
        manager_to_update.fs_sync_node_id = manager['fs_sync_node_id']
        result = sm.update(manager_to_update)

        current_app.logger.info('Manager updated successfully, sending message'
                                ' on service-queue')
        if add_manager and not manager['bootstrap_cluster']:
            managers_list = get_storage_manager().list(models.Manager)
            add_manager(managers_list)
        return result

    @exceptions_handled
    @authorize('manager_manage')
    @marshal_with(models.Manager)
    @premium_only
    def delete(self, name):
        """
        Delete a manager from the database
        """
        sm = get_storage_manager()
        manager_to_delete = sm.get(
            models.Manager,
            None,
            filters={'hostname': name}
        )

        result = sm.delete(manager_to_delete)
        current_app.logger.info('Manager deleted successfully')
        managers_list = get_storage_manager().list(models.Manager)
        if remove_manager and update_agents:
            remove_manager(managers_list)  # Removing manager from cluster
            update_agents(sm)
        return result


class RabbitMQBrokers(SecuredResource):
    @exceptions_handled
    @marshal_with(models.RabbitMQBroker)
    @paginate
    @authorize('broker_get')
    def get(self, pagination=None):
        """List brokers from the database."""
        brokers = get_storage_manager().list(models.RabbitMQBroker)
        if not is_user_action_allowed('broker_credentials'):
            for broker in brokers:
                broker.username = None
                broker.password = None
        return brokers

    @exceptions_handled
    @authorize('broker_manage')
    @marshal_with(models.RabbitMQBroker)
    @premium_only
    def post(self):
        """Add a broker to the database."""
        broker = rest_utils.get_json_and_verify_params({
            'name': {'type': unicode},
            'address': {'type': unicode},
            'port': {'type': int, 'optional': True},
            'networks': {'type': dict, 'optional': True},
        })
        sm = get_storage_manager()

        # Get the first broker in the list to get the ca_cert and credentials
        first_broker = sm.list(models.RabbitMQBroker).items[0]

        if broker.get('networks'):
            check_private_address_is_in_networks(
                broker['address'],
                broker['networks'],
            )
        else:
            broker['networks'] = {'default': broker['address']}

        new_broker = models.RabbitMQBroker(
            name=broker['name'],
            host=broker['address'],
            management_host=broker['address'],
            port=broker.get('port'),
            networks=broker['networks'],
            username=first_broker.username,
            password=first_broker.password,
            _ca_cert_id=first_broker._ca_cert_id,
        )
        result = sm.put(new_broker)
        current_app.logger.info('Broker added successfully')
        if update_agents:
            update_agents(sm)
        return result


class RabbitMQBrokersId(SecuredResource):
    @exceptions_handled
    @authorize('broker_manage')
    @marshal_with(models.Manager)
    @premium_only
    def put(self, name):
        """Update a broker's networks.

        :param name: Name of broker to update.
        :return: Updated broker details.
        """
        broker_update = rest_utils.get_json_and_verify_params({
            'networks': {'type': dict},
        })
        sm = get_storage_manager()
        broker_to_update = sm.get(
            models.RabbitMQBroker,
            None,
            filters={'name': name}
        )
        broker_networks = broker_to_update.networks
        broker_networks.update(broker_update['networks'])
        broker_to_update.networks = broker_networks
        result = sm.update(broker_to_update, modified_attrs=('networks',))

        current_app.logger.info('Broker {name} updated successfully'.format(
                                name=name))
        if update_agents:
            update_agents(sm)
        return result

    @exceptions_handled
    @authorize('broker_manage')
    @marshal_with(models.RabbitMQBroker)
    @premium_only
    def delete(self, name):
        """Delete a broker from the database."""
        sm = get_storage_manager()
        broker_to_delete = sm.get(
            models.RabbitMQBroker,
            None,
            filters={'name': name}
        )

        result = sm.delete(broker_to_delete)
        current_app.logger.info('Broker deleted successfully')
        if update_agents:
            update_agents(sm)
        return result
