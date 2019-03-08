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
from os import getenv

from cloudify import ctx
from cloudify.exceptions import NonRecoverableError
from cloudify_rest_client.exceptions import CloudifyClientError

from .constants import POLLING_INTERVAL
from .utils import handle_client_exception


def _is_find_by_key(key, value, items):
    return any([item for item in items if item[key] == value])


@handle_client_exception('Blueprint was not found')
def blueprint_id_exists(client, blueprint_id):
    blueprints_ids = client.blueprints.list(_include=['id'])
    return _is_find_by_key('id', blueprint_id, blueprints_ids)


@handle_client_exception('Deployment was not found')
def deployment_id_exists(client, deployment_id):
    deployments_ids = client.deployments.list(_include=['id'])
    return _is_find_by_key('id', deployment_id, deployments_ids)


def poll_with_timeout(pollster,
                      timeout,
                      interval=POLLING_INTERVAL,
                      expected_result=True):
    # Check if timeout value is -1 that allows infinite timeout
    # If timeout value is not -1 then it is a finite timeout
    timeout = float('infinity') if timeout == -1 else timeout
    current_time = time.time()

    ctx.logger.debug('Timeout value is {}'.format(timeout))

    while time.time() <= current_time + timeout:
        if pollster() != expected_result:
            ctx.logger.debug('Polling...')
            time.sleep(interval)
        else:
            ctx.logger.debug('Polling succeeded!')
            return True

    ctx.logger.error('Polling timed out!')
    return False


def redirect_logs(_client, execution_id):
    count_events = "received_events"

    if not ctx.instance.runtime_properties.get(count_events):
        ctx.instance.runtime_properties[count_events] = {}

    last_event = int(ctx.instance.runtime_properties[count_events].get(
        execution_id, 0))
    full_count = -1

    while full_count != last_event:
        events, full_count = _client.events.get(execution_id,
                                                last_event,
                                                include_logs=True)
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

            ctx.logger.debug(
                'Message {0} for Event {1} for execution_id {1}'.format(
                    message, event))

            level = event.get('level')
            predefined_levels = {
                'critical': 50,
                'error': 40,
                'warning': 30,
                'info': 20,
                'debug': 10
            }
            if level in predefined_levels:
                ctx.logger.log(predefined_levels[level], message)
            else:
                ctx.logger.log(20, message)

        last_event += len(events)

        if len(events) == 0:
            ctx.logger.log(20, "Returned nothing, let's get logs next time.")
            break

    ctx.instance.runtime_properties[count_events][execution_id] = last_event


def _is_execution_ended(execution_status):
    return execution_status not in ('terminated', 'failed', 'cancelled')


def is_system_workflows_finished(client, target_deployment_id=None):
    offset = int(getenv('_PAGINATION_OFFSET', 0))
    size = int(getenv('_PAGINATION_SIZE', 1000))

    while True:
        try:
            executions = client.executions.list(
                include_system_workflows=True,
                _offset=offset,
                _size=size)
        except CloudifyClientError as ex:
            raise NonRecoverableError(
                'Executions list failed {0}.'.format(ex))

        for execution in executions:
            execution_status = execution.get('status')
            if (execution.get('is_system_workflow') or
                    (target_deployment_id and
                     target_deployment_id == execution.get('deployment_id'))):
                if _is_execution_ended(execution_status):
                    return False

        if (executions.metadata.pagination.total <=
                executions.metadata.pagination.offset):
            break

        offset = offset + size

    return True


def is_component_workflow_at_state(client,
                                   dep_id,
                                   state,
                                   log_redirect=False,
                                   execution_id=None):

    exec_get_fields = \
        ['status', 'workflow_id', 'created_at', 'ended_at', 'id']

    try:
        execution = client.executions.get(execution_id=execution_id,
                                          _include=exec_get_fields)
        ctx.logger.debug(
            'The execution get response form {0} is {1}'.format(dep_id,
                                                                execution))

    except CloudifyClientError as ex:
        raise NonRecoverableError(
            'Executions get failed {0}.'.format(ex))

    execution_id = execution.get('id')
    if log_redirect and execution_id:
        ctx.logger.debug(
            'execution info for _log_redirect is {0}'.format(execution))
        redirect_logs(client, execution_id)

    execution_status = execution.get('status')
    if execution_status == state:
        ctx.logger.debug(
            'The status for execution info id'
            ' {0} is {1}'.format(execution_id, state))

        return True
    elif execution_status == 'failed':
        raise NonRecoverableError(
            'Execution {0} failed.'.format(str(execution)))

    return False


def poll_workflow_after_execute(timeout,
                                interval,
                                client,
                                dep_id,
                                state,
                                execution_id,
                                log_redirect=False):
    pollster_args = {
        'client': client,
        'dep_id': dep_id,
        'state': state,
        'log_redirect': log_redirect,
        'execution_id': execution_id,
    }

    ctx.logger.debug('Polling: {0}'.format(pollster_args))
    result = poll_with_timeout(
        lambda: is_component_workflow_at_state(**pollster_args),
        timeout=timeout,
        interval=interval)

    if not result:
        raise NonRecoverableError(
            'Execution timeout: {0} seconds.'.format(timeout))
    return True
