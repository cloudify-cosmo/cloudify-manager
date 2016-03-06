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
#

import os
from flask_securest.rest_security import SecuredResource

from manager_rest import utils
from manager_rest.resources import (marshal_with,
                                    exceptions_handled)

from manager_rest import models
from manager_rest import responses_v2_1
from manager_rest import config
from manager_rest.blueprints_manager import get_blueprints_manager
from manager_rest.constants import (MAINTENANCE_MODE_ACTIVE,
                                    MAINTENANCE_MODE_STATUS_FILE,
                                    ACTIVATING_MAINTENANCE_MODE,
                                    NOT_IN_MAINTENANCE_MODE)


class MaintenanceMode(SecuredResource):
    @exceptions_handled
    @marshal_with(responses_v2_1.MaintenanceMode)
    def get(self, **kwargs):
        maintenance_file_path = get_maintenance_file_path()
        if os.path.isfile(maintenance_file_path):
            with open(maintenance_file_path, 'r') as f:
                status = f.read()

            if status == MAINTENANCE_MODE_ACTIVE:
                return {'status': MAINTENANCE_MODE_ACTIVE}
            if status == ACTIVATING_MAINTENANCE_MODE:
                executions = get_blueprints_manager().executions_list(
                        is_include_system_workflows=True).items
                for execution in executions:
                    if execution.status not in models.Execution.END_STATES:
                        return {'status': ACTIVATING_MAINTENANCE_MODE}

                write_maintenance_state(MAINTENANCE_MODE_ACTIVE)
                return {'status': MAINTENANCE_MODE_ACTIVE}
        else:
            return {'status': NOT_IN_MAINTENANCE_MODE}


class MaintenanceModeAction(SecuredResource):
    @exceptions_handled
    @marshal_with(responses_v2_1.MaintenanceMode)
    def post(self, maintenance_action, **kwargs):
        maintenance_file_path = get_maintenance_file_path()

        if maintenance_action == 'activate':
            if os.path.isfile(maintenance_file_path):
                return {'status': MAINTENANCE_MODE_ACTIVE}, 304

            utils.mkdirs(config.instance().maintenance_folder)
            write_maintenance_state(ACTIVATING_MAINTENANCE_MODE)

            return {'status': ACTIVATING_MAINTENANCE_MODE}

        if maintenance_action == 'deactivate':
            if not os.path.isfile(maintenance_file_path):
                return {'status': NOT_IN_MAINTENANCE_MODE}, 304
            os.remove(maintenance_file_path)
            return {'status': NOT_IN_MAINTENANCE_MODE}


def get_maintenance_file_path():
    return os.path.join(
        config.instance().maintenance_folder,
        MAINTENANCE_MODE_STATUS_FILE)


def write_maintenance_state(state):
    maintenance_file_path = get_maintenance_file_path()
    with open(maintenance_file_path, 'w') as f:
        f.write(state)
