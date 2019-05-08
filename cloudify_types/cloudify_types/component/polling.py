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

import time

from cloudify import ctx
from cloudify.exceptions import NonRecoverableError

from cloudify_types.utils import handle_client_exception, get_deployment_by_id

from .constants import POLLING_INTERVAL, PAGINATION_SIZE

PREDEFINED_LOG_LEVELS = {
    'critical': 50,
    'error': 40,
    'warning': 30,
    'info': 20,
    'debug': 10
}


@handle_client_exception('Blueprint search failed')
def blueprint_id_exists(client, blueprint_id):
    """
    Searching for blueprint_id in all blueprints in order to differentiate
    not finding the blueprint then other kinds of errors, like server
    failure.
    """
    blueprint_id_filter = {'id': blueprint_id}
    blueprint = client.blueprints.list(_include=['id'],
                                       **blueprint_id_filter)
    return True if blueprint else False


def deployment_id_exists(client, deployment_id):
    deployment = get_deployment_by_id(client, deployment_id)
    return True if deployment else False


def poll_with_timeout(pollster,
                      timeout,
                      interval=POLLING_INTERVAL,
                      expected_result=True):
    # Check if timeout value is -1 that allows infinite timeout
    # If timeout value is not -1 then it is a finite timeout
    timeout = float('infinity') if timeout == -1 else timeout
    current_time = time.time()

    ctx.logger.debug('Pooling with timeout {0} seconds'.format(timeout))

    while time.time() <= current_time + timeout:
        if pollster() != expected_result:
            ctx.logger.debug('Polling...')
            time.sleep(interval)
        else:
            ctx.logger.debug('Polling succeeded!')
            return True

    ctx.logger.error('Polling timed out!')
    return False


def _fetch_events(client, execution_id, last_event):
    response = client.events.list(execution_id=execution_id,
                                  _offset=last_event,
                                  _size=PAGINATION_SIZE,
                                  _sort='timestamp',
                                  include_logs=True)
    events = response.items
    full_count = response.metadata.pagination.total

    return events, full_count


@handle_client_exception('Redirecting logs from the component failed')
def redirect_logs(client, execution_id):
    count_events = "received_events"

    if not ctx.instance.runtime_properties.get(count_events):
        ctx.instance.runtime_properties[count_events] = {}

    last_event = int(ctx.instance.runtime_properties[count_events].get(
        execution_id, 0))
    full_count = -1

    while full_count != last_event:
        events, full_count = _fetch_events(client, execution_id, last_event)

        for event in events:
            ctx.logger.debug(
                'Event {0} for execution_id {1}'.format(event, execution_id))
            instance_prompt = event.get('node_instance_id', "")
            if instance_prompt:
                event_operation = event.get('operation')
                if event_operation:
                    instance_prompt += (
                        "." + event_operation.split('.')[-1]
                    )

            if instance_prompt:
                instance_prompt = "[" + instance_prompt + "] "

            message = "%s %s%s" % (
                event.get('reported_timestamp', ""),
                instance_prompt if instance_prompt else "",
                event.get('message', "")
            )
            message = message.encode('utf-8')

            ctx.logger.info(
                'Message {0} for Event {1} for execution_id {1}'.format(
                    message, event))

            level = event.get('level')
            if level in PREDEFINED_LOG_LEVELS:
                ctx.logger.log(PREDEFINED_LOG_LEVELS[level], message)
            else:
                ctx.logger.log(20, message)

        last_event += len(events)

        if len(events) == 0:
            ctx.logger.log(20, "Returned nothing, let's get logs next time.")
            break

    ctx.instance.runtime_properties[count_events][execution_id] = last_event


def _is_execution_not_ended(execution_status):
    return execution_status not in ('terminated', 'failed', 'cancelled')


@handle_client_exception('Checking all executions had failed')
def is_all_executions_finished(client, deployment_id=None):
    """
    Checks if all system workflows or given deployment id are finished
    running (successful not).

    :param client: cloudify http client.
    :param deployment_id: Optional, will check all it's executions
    :return: True if all executions had ended
    """
    offset = 0

    while True:
        executions = client.executions.list(
            include_system_workflows=True,
            _offset=offset,
            _size=PAGINATION_SIZE)

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


@handle_client_exception('Checking component\'s latest execution had failed')
def is_component_execution_at_state(client,
                                    dep_id,
                                    state,
                                    log_redirect=False,
                                    execution_id=None):

    execution_get_args = ['status', 'workflow_id',
                          'created_at', 'ended_at', 'id']

    execution = client.executions.get(execution_id=execution_id,
                                      _include=execution_get_args)
    ctx.logger.info(
        'The execution of "{0}" component is {1}'.format(dep_id,
                                                         execution))

    execution_id = execution.get('id')
    if log_redirect and execution_id:
        ctx.logger.debug(
            'Execution info with log_redirect is {0}'.format(execution))
        redirect_logs(client, execution_id)

    execution_status = execution.get('status')
    if execution_status == state:
        ctx.logger.debug(
            'The status for execution info of'
            ' {0} is {1}'.format(execution_id, state))

        return True
    elif execution_status == 'failed':
        raise NonRecoverableError(
            'Execution {0} failed.'.format(str(execution)))

    return False
