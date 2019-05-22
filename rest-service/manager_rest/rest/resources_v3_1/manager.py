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

from subprocess import check_call

from flask import request, current_app
from flask_restful.reqparse import Argument

from manager_rest import manager_exceptions
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.storage import (
    get_storage_manager,
    models
)

from .. import rest_utils
from ..rest_decorators import (
    exceptions_handled,
    marshal_with,
    paginate
)


try:
    from cloudify_premium.ha import (
        add_manager,
        remove_manager
    )
except ImportError:
    add_manager, remove_manager = None, None


DEFAULT_CONF_PATH = '/etc/nginx/conf.d/cloudify.conf'
HTTP_PATH = '/etc/nginx/conf.d/http-external-rest-server.cloudify'
HTTPS_PATH = '/etc/nginx/conf.d/https-external-rest-server.cloudify'


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
    @authorize('manager_add')
    @marshal_with(models.Manager)
    def post(self):
        """
        Create a new manager
        """
        _manager = rest_utils.get_json_and_verify_params({
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
        sm = get_storage_manager()
        ca_cert_id = self._get_ca_cert_id(sm, _manager)
        new_manager = models.Manager(
            hostname=_manager['hostname'],
            private_ip=_manager['private_ip'],
            public_ip=_manager['public_ip'],
            version=_manager['version'],
            edition=_manager['edition'],
            distribution=_manager['distribution'],
            distro_release=_manager['distro_release'],
            fs_sync_node_id=_manager.get('fs_sync_node_id', ''),
            networks=_manager.get('networks'),
            _ca_cert_id=ca_cert_id
        )
        result = sm.put(new_manager)
        current_app.logger.info('Manager added successfully')
        if _manager.get('fs_sync_node_id'):
            managers_list = get_storage_manager().list(models.Manager)
            add_manager(managers_list)
        return result

    @exceptions_handled
    @authorize('manager_update_fs_sync_node_id')
    @marshal_with(models.Manager)
    def put(self):
        """
        Update a manager's FS sync node ID required by syncthing
        """
        _manager = rest_utils.get_json_and_verify_params({
            'hostname': {'type': unicode},
            'fs_sync_node_id': {'type': unicode},
            'bootstrap_cluster': {'type': bool}
        })
        sm = get_storage_manager()
        manager_to_update = sm.get(
            models.Manager,
            None,
            filters={'hostname': _manager['hostname']}
        )
        manager_to_update.fs_sync_node_id = _manager['fs_sync_node_id']
        result = sm.update(manager_to_update)

        current_app.logger.info('Manager updated successfully, sending message'
                                ' on service-queue')
        if not _manager['bootstrap_cluster']:
            managers_list = get_storage_manager().list(models.Manager)
            add_manager(managers_list)
        return result

    @exceptions_handled
    @authorize('manager_delete')
    @marshal_with(models.Manager)
    def delete(self):
        """
        Delete a manager from the database
        """
        _manager = rest_utils.get_json_and_verify_params({
            'hostname': {'type': unicode}
        })
        sm = get_storage_manager()
        manager_to_delete = sm.get(
            models.Manager,
            None,
            filters={'hostname': _manager['hostname']}
        )

        result = sm.delete(manager_to_delete)
        if _manager['hostname'] == result.hostname:
            current_app.logger.info('Manager deleted successfully')
            managers_list = get_storage_manager().list(models.Manager)
            remove_manager(managers_list)  # Removing manager from cluster
        return result

    def _get_ca_cert_id(self, sm, _manager):
        ca_cert_content = _manager.get('ca_cert_content')
        if ca_cert_content:
            ca_cert = sm.put(models.Certificate(
                name='{0}-ca'.format(_manager['hostname']),
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


class RabbitMQBrokers(SecuredResource):
    @exceptions_handled
    @marshal_with(models.RabbitMQBroker)
    @paginate
    @authorize('broker_get')
    def get(self, pagination=None):
        """List brokers from the database."""
        return get_storage_manager().list(
            models.RabbitMQBroker,
        )

    @exceptions_handled
    @authorize('broker_add')
    @marshal_with(models.RabbitMQBroker)
    def post(self):
        """Add a broker to the database."""
        _broker = rest_utils.get_json_and_verify_params({
            'name': {'type': unicode},
            'address': {'type': unicode},
            'port': {'type': int, 'optional': True},
            'networks': {'type': dict, 'optional': True},
        })
        sm = get_storage_manager()

        # Get the first broker in the list to get the ca_cert and credentials
        first_broker = sm.list(models.RabbitMQBroker, None, None).items[0]

        if not _broker.get('networks'):
            _broker['networks'] = {'default': _broker['address']}

        new_broker = models.RabbitMQBroker(
            name=_broker['name'],
            host=_broker['address'],
            management_host=_broker['address'],
            port=_broker.get('port'),
            networks=_broker['networks'],
            username=first_broker.username,
            password=first_broker.password,
            ca_cert=first_broker.ca_cert,
        )
        result = sm.put(new_broker)
        current_app.logger.info('Broker added successfully')
        return result

    @exceptions_handled
    @authorize('broker_delete')
    @marshal_with(models.RabbitMQBroker)
    def delete(self):
        """Delete a broker from the database."""
        _broker = rest_utils.get_json_and_verify_params({
            'name': {'type': unicode}
        })
        sm = get_storage_manager()
        broker_to_delete = sm.get(
            models.RabbitMQBroker,
            None,
            filters={'name': _broker['name']}
        )

        result = sm.delete(broker_to_delete)
        if _broker['name'] == result.name:
            current_app.logger.info('Broker deleted successfully')
        return result
