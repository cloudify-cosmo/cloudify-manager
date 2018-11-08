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

from flask import request

from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize

from .. import rest_utils
from ..rest_decorators import exceptions_handled
try:
    from cloudify_premium.ha import cluster_status, options
except ImportError:
    cluster_status, options = None, None


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
