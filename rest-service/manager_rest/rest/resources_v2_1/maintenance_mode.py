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


from datetime import datetime
from flask_security import current_user

from manager_rest.resource_manager import get_resource_manager
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.constants import (MAINTENANCE_MODE_ACTIVATED,
                                    MAINTENANCE_MODE_ACTIVATING,
                                    MAINTENANCE_MODE_DEACTIVATED)
from manager_rest.maintenance import (get_running_executions,
                                      get_maintenance_state,
                                      store_maintenance_state,
                                      remove_maintenance_state)
from manager_rest.manager_exceptions import BadParametersError

from .. import rest_decorators
from ..responses_v2_1 import MaintenanceMode as MaintenanceModeResponse


class MaintenanceMode(SecuredResource):
    @authorize('maintenance_mode_get')
    @rest_decorators.marshal_with(MaintenanceModeResponse)
    def get(self, **_):
        state = get_maintenance_state()
        if not state:
            return {
                'status': MAINTENANCE_MODE_DEACTIVATED,
                'activated_at': '',
                'remaining_executions': None,
                'requested_by': '',
                'activation_requested_at': ''
            }

        if state['status'] == MAINTENANCE_MODE_ACTIVATED:
            return state
        elif state['status'] == MAINTENANCE_MODE_ACTIVATING:
            running_executions = get_running_executions()

            # If there are no running executions,
            # maintenance mode would have been activated at the
            # maintenance handler hook (server.py)
            state['remaining_executions'] = running_executions
            return state
        else:
            raise RuntimeError('Unknown maintenance mode state: {0}'
                               .format(state['status']))


class MaintenanceModeAction(SecuredResource):
    @authorize('maintenance_mode_set')
    @rest_decorators.marshal_with(MaintenanceModeResponse)
    def post(self, maintenance_action, **_):

        state = get_maintenance_state()
        if maintenance_action == 'activate':
            if state:
                return state, 304
            remaining_executions = get_running_executions()
            status = MAINTENANCE_MODE_ACTIVATING \
                if remaining_executions else MAINTENANCE_MODE_ACTIVATED

            now = datetime.utcnow()
            state = store_maintenance_state(
                status=status,
                activation_requested_at=now,
                activated_at=None if remaining_executions else now,
                requested_by=current_user
            )
            state['remaining_executions'] = remaining_executions,
            return state

        elif maintenance_action == 'deactivate':
            if not state:
                return {'status': MAINTENANCE_MODE_DEACTIVATED}, 304
            rv = remove_maintenance_state()
            get_resource_manager().start_queued_executions()
            return rv

        else:
            valid_actions = ['activate', 'deactivate']
            raise BadParametersError(
                'Invalid action: {0}, Valid action '
                'values are: {1}'.format(maintenance_action, valid_actions))
