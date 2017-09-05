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

from subprocess import check_call, Popen

from flask_login import current_user

from manager_rest.app_logging import raise_unauthorized_user_error
from manager_rest.security import SecuredResource

from .. import rest_utils
from ..rest_decorators import exceptions_handled

DEFAULT_CONF_PATH = '/etc/nginx/conf.d/default.conf'
HTTP_PATH = '/etc/nginx/conf.d/http-external-rest-server.cloudify'
HTTPS_PATH = '/etc/nginx/conf.d/https-external-rest-server.cloudify'


class SSLConfig(SecuredResource):
    @exceptions_handled
    def post(self):
        """
        Enable/Disable SSL
        """
        if not current_user.is_admin:
            raise_unauthorized_user_error(
                '{0} does not have privileges to set SSL mode'.format(
                    current_user))
        request_dict = rest_utils.get_json_and_verify_params({'state'})
        state = rest_utils.verify_and_convert_bool('state',
                                                   request_dict.get('state'))
        status = 'enabled' if state else 'disabled'
        if state == SSLConfig._is_enabled():
            return 'SSL is already {0} on the manager'.format(status)
        source = HTTP_PATH if state else HTTPS_PATH
        target = HTTPS_PATH if state else HTTP_PATH
        cmd = 'sudo sed -i "s~{0}~{1}~g" {2}'.format(
            source, target, DEFAULT_CONF_PATH)
        check_call(cmd, shell=True)
        Popen('sleep 1; sudo systemctl restart nginx', shell=True)
        return 'SSL is now {0} on the manager'.format(status)

    @exceptions_handled
    def get(self):
        """
        Get ssl state (enabled/disabled)
        """
        return 'SSL {0}'.format(
            'enabled' if SSLConfig._is_enabled() else 'disabled')

    @staticmethod
    def _is_enabled():
        with open(DEFAULT_CONF_PATH) as f:
            content = f.read()
        return content.find(HTTPS_PATH) >= 0
