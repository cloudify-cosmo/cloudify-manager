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

import os
import StringIO
import traceback

from flask import jsonify, request

from manager_rest import config
from manager_rest import utils
from manager_rest.storage.models_states import ExecutionState
from manager_rest.resource_manager import get_resource_manager
from manager_rest.constants import (MAINTENANCE_MODE_ACTIVATED,
                                    MAINTENANCE_MODE_STATUS_FILE,
                                    MAINTENANCE_MODE_ACTIVATING,
                                    MAINTENANCE_MODE_ACTIVE_ERROR_CODE,
                                    MAINTENANCE_MODE_ACTIVATING_ERROR_CODE)


FORBIDDEN_METHODS = ['POST', 'PATCH', 'PUT']
ALLOWED_ENDPOINTS = ['maintenance',
                     'status',
                     'version']
LOCAL_ADDRESS = '127.0.0.1'


def get_maintenance_file_path():
    return os.path.join(
            config.instance.maintenance_folder,
            MAINTENANCE_MODE_STATUS_FILE)


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

    # enabling internal requests
    if _is_internal_request() and is_bypass_maintenance_mode():
        return

    # Removing v*/ from the endpoint
    index = request.endpoint.find('/')
    request_endpoint = request.endpoint[index+1:]
    maintenance_file = os.path.join(
            config.instance.maintenance_folder,
            MAINTENANCE_MODE_STATUS_FILE)

    if os.path.isfile(maintenance_file):
        state = utils.read_json_file(maintenance_file)
        if state['status'] == MAINTENANCE_MODE_ACTIVATING:
            running_executions = get_running_executions()
            if not running_executions:
                now = utils.get_formatted_timestamp()
                state = prepare_maintenance_dict(
                        MAINTENANCE_MODE_ACTIVATED,
                        activated_at=now,
                        remaining_executions=[],
                        requested_by=state['requested_by'],
                        activation_requested_at=state[
                            'activation_requested_at'])
                utils.write_dict_to_json_file(maintenance_file, state)
            else:
                return _handle_activating_mode(
                       state=state,
                       request_endpoint=request_endpoint)

        if _check_allowed_endpoint(request_endpoint):
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


def _check_allowed_endpoint(request_endpoint):
    for endpoint in ALLOWED_ENDPOINTS:
        if request_endpoint.startswith(endpoint):
            return True
    return False


def get_running_executions():
    executions = get_resource_manager().list_executions(
            is_include_system_workflows=True).items
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


def _is_internal_request():
    remote_addr = _get_remote_addr()
    http_hosts = [_get_host(), LOCAL_ADDRESS]
    return all([remote_addr, http_hosts, remote_addr in http_hosts])


def is_bypass_maintenance_mode():
    return utils.is_bypass_maintenance_mode(request)


def _get_remote_addr():
    return request.remote_addr


def _get_host():
    return request.host


def _create_maintenance_error(error_code):
    # app.logger.exception(e)  # gets logged automatically
    s_traceback = StringIO.StringIO()
    traceback.print_exc(file=s_traceback)
    error_message = 'Your request was rejected since Cloudify ' \
                    'manager is currently in maintenance mode'

    response = jsonify(
            {"message": error_message,
             "error_code": error_code,
             "server_traceback": s_traceback.getvalue()})
    response.status_code = 503
    return response


def _maintenance_mode_error():
    return _create_maintenance_error(MAINTENANCE_MODE_ACTIVE_ERROR_CODE)


def _activating_maintenance_mode_error():
    return _create_maintenance_error(MAINTENANCE_MODE_ACTIVATING_ERROR_CODE)
