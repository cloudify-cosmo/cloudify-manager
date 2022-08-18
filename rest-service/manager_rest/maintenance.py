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
#

import traceback
from datetime import datetime
from flask import jsonify, request
from io import StringIO

from cloudify.models_states import ExecutionState

from manager_rest import utils
from manager_rest.storage import get_storage_manager, models
from manager_rest.storage.models_base import db
from manager_rest.constants import (FORBIDDEN_METHODS,
                                    MAINTENANCE_MODE_ACTIVATED,
                                    MAINTENANCE_MODE_ACTIVATING,
                                    MAINTENANCE_MODE_DEACTIVATED,
                                    MAINTENANCE_MODE_ACTIVE_ERROR_CODE,
                                    MAINTENANCE_MODE_ACTIVATING_ERROR_CODE,
                                    ALLOWED_MAINTENANCE_ENDPOINTS)
from manager_rest.security.authorization import is_user_action_allowed


def prepare_maintenance_dict(status,
                             activated_at='',
                             remaining_executions=None,
                             requested_by='',
                             activation_requested_at=''):
    remaining_executions = remaining_executions or []
    state = {'status': status,
             'activated_at': activated_at,
             'remaining_executions': remaining_executions,
             'requested_by': requested_by,
             'activation_requested_at': activation_requested_at}
    return state


def maintenance_mode_handler():

    # failed to route the request - this is a 404. Abort early.
    if not request.endpoint:
        return

    state = get_maintenance_state()
    if not state:
        return

    if is_bypass_maintenance_mode() and \
            is_user_action_allowed('maintenance_mode_set'):
        return

    if state['status'] == MAINTENANCE_MODE_ACTIVATING:
        if not get_running_executions():
            state = store_maintenance_state(
                status=MAINTENANCE_MODE_ACTIVATED,
                activated_at=datetime.utcnow()
            )
        else:
            # Removing v*/ from the endpoint
            index = request.endpoint.find('/')
            request_endpoint = request.endpoint[index + 1:]
            return _handle_activating_mode(
                state=state,
                request_endpoint=request_endpoint)

    if utils.check_allowed_endpoint(ALLOWED_MAINTENANCE_ENDPOINTS):
        return

    if state['status'] == MAINTENANCE_MODE_ACTIVATED:
        return _maintenance_mode_error()


def _handle_activating_mode(state, request_endpoint):
    status = state['status']

    if request_endpoint == 'snapshots/<string:snapshot_id>':
        if request.method in FORBIDDEN_METHODS:
            return _return_maintenance_error(status)
    if request_endpoint == 'snapshots/' \
                           '<string:snapshot_id>/restore':
        return _return_maintenance_error(status)

    if request_endpoint == 'executions':
        if request.method in FORBIDDEN_METHODS:
            return _return_maintenance_error(status)

    if request_endpoint == 'deployments/<string:deployment_id>':
        if request.method in FORBIDDEN_METHODS:
            return _return_maintenance_error(status)

    if request_endpoint == 'deployment-modifications':
        if request.method in FORBIDDEN_METHODS:
            return _return_maintenance_error(status)


def _return_maintenance_error(status):
    if status == MAINTENANCE_MODE_ACTIVATED:
        return _maintenance_mode_error()
    return _activating_maintenance_mode_error()


def get_running_executions():
    executions = get_storage_manager().full_access_list(models.Execution)
    running_executions = []
    for execution in executions:
        if execution.status not in ExecutionState.END_STATES:
            running_executions.append({
                'id': execution.id,
                'status': execution.status,
                'deployment_id': execution.deployment_id,
                'workflow_id': execution.workflow_id
            })

    return running_executions


def is_bypass_maintenance_mode():
    return utils.is_bypass_maintenance_mode(request)


def _create_maintenance_error(error_code):
    # app.logger.exception(e)  # gets logged automatically
    s_traceback = StringIO()
    traceback.print_exc(file=s_traceback)
    error_message = 'Your request was rejected since Cloudify ' \
                    'manager is currently in maintenance mode'

    response = jsonify({
        "message": error_message,
        "error_code": error_code,
        "server_traceback": s_traceback.getvalue()
    })
    response.status_code = 503
    return response


def _maintenance_mode_error():
    return _create_maintenance_error(MAINTENANCE_MODE_ACTIVE_ERROR_CODE)


def _activating_maintenance_mode_error():
    return _create_maintenance_error(MAINTENANCE_MODE_ACTIVATING_ERROR_CODE)


def get_maintenance_state():
    inst = db.session.query(models.MaintenanceMode).first()
    if not inst:
        return None
    return inst.to_dict()


def store_maintenance_state(**state):
    inst = db.session.query(models.MaintenanceMode).first()
    if inst:
        for k, v in state.items():
            setattr(inst, k, v)
    else:
        inst = models.MaintenanceMode(**state)
    db.session.add(inst)
    db.session.commit()
    return inst.to_dict()


def remove_maintenance_state():
    inst = db.session.query(models.MaintenanceMode).first()
    if inst:
        state = inst.to_dict()
        db.session.delete(inst)
        db.session.commit()
    else:
        state = {}
    state['status'] = MAINTENANCE_MODE_DEACTIVATED
    return state
