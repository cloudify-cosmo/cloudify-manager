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
        cluster_status,
        options,
        add_manager,
        remove_manager
    )

except ImportError:
    cluster_status, options, add_manager, remove_manager = \
        None, None, None, None


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
        if rest_utils.is_clustered():
            self._cluster_set_ssl_state(state)
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

    @staticmethod
    def _cluster_set_ssl_state(state):
        # mutation isn't enough, need to set it for it to be saved
        cluster_opts = cluster_status.cluster_options
        cluster_opts[options.CLUSTER_SSL_ENABLED] = state
        cluster_status.cluster_options = cluster_opts


class Managers(SecuredResource):
    @exceptions_handled
    @marshal_with(models.Manager)
    @paginate
    @authorize('manager_get')
    def get(self, pagination=None, _include=None):
        """
        Get the list of managers in the database
        :param hostname: optional hostname to return only a specific manager
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
            'fs_sync_node_id': {'type': unicode, 'optional': True},
            'networks': {'type': dict, 'optional': True}
        })
        new_manager = models.Manager(
            hostname=_manager['hostname'],
            private_ip=_manager['private_ip'],
            public_ip=_manager['public_ip'],
            version=_manager['version'],
            edition=_manager['edition'],
            distribution=_manager['distribution'],
            distro_release=_manager['distro_release'],
            fs_sync_node_id=_manager.get('fs_sync_node_id', ''),
            networks=_manager.get('networks')
        )
        result = get_storage_manager().put(new_manager)
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


class RabbitMQBrokers(SecuredResource):
    @exceptions_handled
    @marshal_with(models.RabbitMQBroker)
    @paginate
    @authorize('broker_get')
    def get(self, pagination=None):
        return get_storage_manager().list(
            models.RabbitMQBroker,
        )
