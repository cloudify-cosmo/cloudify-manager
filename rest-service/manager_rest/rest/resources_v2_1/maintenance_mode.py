#########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

import os

from flask_security import current_user

from manager_rest import config
from manager_rest import utils
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.constants import (MAINTENANCE_MODE_ACTIVATED,
                                    MAINTENANCE_MODE_ACTIVATING,
                                    MAINTENANCE_MODE_DEACTIVATED)
from manager_rest.maintenance import (get_maintenance_file_path,
                                      prepare_maintenance_dict,
                                      get_running_executions)
from manager_rest.manager_exceptions import BadParametersError

from .. import rest_decorators
from ..responses_v2_1 import MaintenanceMode as MaintenanceModeResponse


class MaintenanceMode(SecuredResource):
    @authorize('maintenance_mode_get')
    @rest_decorators.marshal_with(MaintenanceModeResponse)
    def get(self, **_):
        maintenance_file_path = get_maintenance_file_path()
        if os.path.isfile(maintenance_file_path):
            state = utils.read_json_file(maintenance_file_path)

            if state['status'] == MAINTENANCE_MODE_ACTIVATED:
                return state
            if state['status'] == MAINTENANCE_MODE_ACTIVATING:
                running_executions = get_running_executions()

                # If there are no running executions,
                # maintenance mode would have been activated at the
                # maintenance handler hook (server.py)
                state['remaining_executions'] = running_executions
                return state
        else:
            return prepare_maintenance_dict(MAINTENANCE_MODE_DEACTIVATED)


class MaintenanceModeAction(SecuredResource):
    @authorize('maintenance_mode_set')
    @rest_decorators.marshal_with(MaintenanceModeResponse)
    def post(self, maintenance_action, **_):
        maintenance_file_path = get_maintenance_file_path()
        if maintenance_action == 'activate':
            if os.path.isfile(maintenance_file_path):
                state = utils.read_json_file(maintenance_file_path)
                return state, 304
            now = utils.get_formatted_timestamp()
            try:
                user = current_user.username
            except AttributeError:
                user = ''
            remaining_executions = get_running_executions()
            status = MAINTENANCE_MODE_ACTIVATING \
                if remaining_executions else MAINTENANCE_MODE_ACTIVATED
            activated_at = '' if remaining_executions else now
            utils.mkdirs(config.instance.maintenance_folder)
            new_state = prepare_maintenance_dict(
                status=status,
                activation_requested_at=now,
                activated_at=activated_at,
                remaining_executions=remaining_executions,
                requested_by=user)
            utils.write_dict_to_json_file(maintenance_file_path, new_state)
            return new_state
        if maintenance_action == 'deactivate':
            if not os.path.isfile(maintenance_file_path):
                return prepare_maintenance_dict(
                        MAINTENANCE_MODE_DEACTIVATED), 304
            os.remove(maintenance_file_path)
            return prepare_maintenance_dict(MAINTENANCE_MODE_DEACTIVATED)
        valid_actions = ['activate', 'deactivate']
        raise BadParametersError(
                'Invalid action: {0}, Valid action '
                'values are: {1}'.format(maintenance_action, valid_actions))
