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
from cloudify.exceptions import CommandExecutionException
from flask import request, current_app

from manager_rest import config
from manager_rest.rest import rest_decorators
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize


class ManagerConfig(SecuredResource):
    @rest_decorators.exceptions_handled
    @authorize('manager_config_get')
    def get(self):
        """
        Get the Manager config
        """
        request_args = request.args.to_dict(flat=False)
        current_app.logger.info('Retrieving roles config. filter: {0}'.
                                format(request_args))
        result = dict()
        filter_by = request_args.get('filter', [])
        for key in filter_by:
            if key == 'authorization':
                result['authorization'] = self._authorization_config()
        if not filter_by:
            current_app.logger.debug('Retrieving roles without a filter')
            result['authorization'] = self._authorization_config()
        return result

    @staticmethod
    def _authorization_config():
        cfy_config = config.instance
        authorization = {
            'roles': cfy_config.authorization_roles,
            'permissions': cfy_config.authorization_permissions
        }
        return authorization


class ManagerRestConfig(SecuredResource):
    @rest_decorators.exceptions_handled
    @authorize('manager_rest_config_get')
    def get(self):
        """
        Get the Manager's REST configuration
        :return: Manager's REST configuration data
        """
        request_args = request.args.to_dict(flat=False)
        current_app.logger.info('Retrieving Manager REST config. filter: {0}'.
                                format(request_args))
        result = dict()
        filter_by = request_args.get('filter', [])
        for key in filter_by:
            try:
                result[key] = config.instance.to_dict()[key]
            except KeyError as ke:
                current_app.logger.error(
                    'KeyError thrown: {0}'.format(str(ke)))
                raise CommandExecutionException(command='manager.config.get',
                                                error=str(ke),
                                                code=400,
                                                output=None)
        if not filter_by:
            current_app.logger.debug('Retrieving Manager REST config without a'
                                     ' filter')
            result = config.instance.to_dict()
        return result
