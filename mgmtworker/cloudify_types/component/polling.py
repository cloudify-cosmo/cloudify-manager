# Copyright (c) 2017-2019 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging

from cloudify import ctx
from cloudify.exceptions import NonRecoverableError
from cloudify.models_states import ExecutionState
from cloudify_types.polling import poll_with_timeout

from .constants import POLLING_INTERVAL, PAGINATION_SIZE, EXECUTIONS_TIMEOUT


def _fetch_events(client, execution_id, last_event):
    response = client.events.list(execution_id=execution_id,
                                  _offset=last_event,
                                  _size=PAGINATION_SIZE,
                                  _sort='timestamp',
                                  include_logs=True)
    events = response.items
    full_count = response.metadata.pagination.total

    return events, full_count


def _get_ctx(instance_ctx):
    return instance_ctx if instance_ctx else ctx.instance


def redirect_logs(client, execution_id, instance_ctx=None):
    instance_ctx = _get_ctx(instance_ctx)
    count_events = "received_events"

    if not instance_ctx.runtime_properties.get(count_events):
        instance_ctx.runtime_properties[count_events] = {}

    last_event = int(instance_ctx.runtime_properties[count_events].get(
        execution_id, 0))
    full_count = -1

    while full_count != last_event:
        events, full_count = _fetch_events(client, execution_id, last_event)

        for event in events:
            instance_prompt = event.get('node_instance_id', "")
            if instance_prompt:
                event_operation = event.get('operation')
                if event_operation:
                    instance_prompt += (
                        "." + event_operation.split('.')[-1]
                    )

            if instance_prompt:
                instance_prompt = "[" + instance_prompt + "] "

            level = event.get('level')

            # If the event dict had a 'level' key, then the value is
            # a string. In that case, convert it to uppercase and get
            # the matching Python logging constant.
            if level:
                level = logging.getLevelName(level.upper())

            # In the (very) odd case that the level is still not an int
            # (can happen if the original level value wasn't recognized
            # by Python's logging library), then use 'INFO'.
            if not isinstance(level, int):
                level = logging.INFO

            ctx.logger.log(level, "%s %s%s",
                           event.get('reported_timestamp', ""),
                           instance_prompt if instance_prompt else "",
                           event.get('message', ""))

        last_event += len(events)

        if len(events) == 0:
            ctx.logger.info(
                "Waiting for log messages (execution: %s)...", execution_id)
            break

    instance_ctx.runtime_properties[count_events][execution_id] = last_event


def _is_execution_not_ended(execution_status):
    return execution_status not in ('terminated', 'failed', 'cancelled')


def is_all_executions_finished(client, deployment_id=None):
    """
    Checks if all system workflows or given deployment id are finished
    running (successful not).

    :param client: cloudify http client.
    :param deployment_id: Optional, will check all it's executions
    :return: True if all executions had ended
    """
    offset = 0

    execution_list_args = {'include_system_workflows': True,
                           '_size': PAGINATION_SIZE}
    if deployment_id:
        execution_list_args['deployment_id'] = deployment_id
    while True:
        execution_list_args['_offset'] = offset
        executions = client.executions.list(**execution_list_args)

        for execution in executions:
            execution_status = execution.get('status')
            if (execution.get('is_system_workflow') or
                    (deployment_id and
                     deployment_id == execution.get('deployment_id'))):
                if _is_execution_not_ended(execution_status):
                    return False

        if (executions.metadata.pagination.total <=
                executions.metadata.pagination.offset):
            break

        offset = offset + len(executions)

    return True


def is_deployment_execution_at_state(client,
                                     dep_id,
                                     state,
                                     execution_id,
                                     log_redirect=False,
                                     instance_ctx=None):
    instance_ctx = _get_ctx(instance_ctx)

    if not execution_id:
        raise NonRecoverableError(
            'Execution id was not found for deployment "{0}"'.format(
                dep_id))

    execution_get_args = ['status', 'workflow_id', 'status_display',
                          'created_at', 'ended_at', 'id']

    execution = client.executions.get(execution_id=execution_id,
                                      _include=execution_get_args)
    ctx.logger.debug(
        'Execution "%s" of component "%s" state is %s',
        execution_id, dep_id, execution.get('status_display', '<unknown>'))

    if log_redirect:
        redirect_logs(client, execution_id, instance_ctx)

    execution_status = execution.get('status')
    if execution_status == state:
        ctx.logger.debug(
            'The status for execution "%s" is %s', execution_id, state)
        return True
    elif execution_status == ExecutionState.FAILED:
        raise NonRecoverableError(f'Execution {execution} {execution_status}.')
    elif execution_status == ExecutionState.CANCELLED:
        main_execution = ctx.get_execution()
        if main_execution.status in [
            ExecutionState.CANCELLED,
            # maybe we weren't cancelled _yet_ but are still cancelling?
            ExecutionState.CANCELLING,
            ExecutionState.FORCE_CANCELLING,
            ExecutionState.KILL_CANCELLING,
        ]:
            ctx.logger.debug(
                'Both the main execution "%s" and the component execution "%s"'
                ' are cancelled (main execution status: %s)',
                main_execution.id, execution_id, main_execution.status)
            return True
        raise NonRecoverableError(f'Execution {execution} {execution_status}.')

    return False


def verify_execution_state(client,
                           execution_id,
                           deployment_id,
                           redirect_log,
                           workflow_state,
                           timeout=EXECUTIONS_TIMEOUT,
                           interval=POLLING_INTERVAL,
                           instance_ctx=None):
    instance_ctx = _get_ctx(instance_ctx)

    pollster_args = {
        'client': client,
        'dep_id': deployment_id,
        'state': workflow_state,
        'log_redirect': redirect_log,
        'execution_id': execution_id,
        'instance_ctx': instance_ctx
    }

    ctx.logger.debug('Polling execution state with: %s', pollster_args)
    result = poll_with_timeout(
        lambda: is_deployment_execution_at_state(**pollster_args),
        timeout=timeout,
        interval=interval)

    if not result:
        raise NonRecoverableError(
            f'Execution timed out after: {timeout} seconds.')
    return True
