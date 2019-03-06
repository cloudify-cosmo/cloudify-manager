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


def any_bp_by_id(_client, _bp_id):
    resource_type = 'blueprints'
    return any_resource_by_id(_client, _bp_id, resource_type)


def any_dep_by_id(_client, _dep_id):
    resource_type = 'deployments'
    return any_resource_by_id(_client, _dep_id, resource_type)


def any_resource_by_id(_client, _resource_id, _resource_type):
    return any(resource_by_id(_client, _resource_id, _resource_type))


def all_deps_by_id(_client, _dep_id):
    resource_type = 'deployments'
    return all_resource_by_id(_client, _dep_id, resource_type)


def all_resource_by_id(_client, _resource_id, _resource_type):
    output = resource_by_id(_client, _resource_id, _resource_type)
    if not output:
        return False
    return all(output)


def resource_by_id(_client, _id, _type):
    _resources_client = getattr(_client, _type)
    try:
        _resources = _resources_client.list(_include=['id'])
    except CloudifyClientError as ex:
        raise NonRecoverableError(
            '{0} list failed {1}.'.format(_type, str(ex)))
    else:
        return [str(_r['id']) == _id for _r in _resources]


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
    event_pagination_step = 100

    if not ctx.instance.runtime_properties.get(count_events):
        ctx.instance.runtime_properties[count_events] = {}

    last_event = int(ctx.instance.runtime_properties[count_events].get(
        execution_id, 0))

    full_count = last_event + event_pagination_step

    while full_count > last_event:
        events, full_count = _client.events.get(execution_id, last_event,
                                                250, True)
        for event in events:
            ctx.logger.debug(
                'Event {0} for execution_id {1}'.format(event, execution_id))
            instance_prompt = event.get('node_instance_id', "")
            if instance_prompt:
                if event.get('operation'):
                    instance_prompt += (
                        "." + event.get('operation').split('.')[-1]
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
        # returned infinite count
        if full_count < 0:
            full_count = last_event + event_pagination_step
        # returned nothing, let's do it next time
        if len(events) == 0:
            ctx.logger.log(20, "Returned nothing, let's get logs next time.")
            break

    ctx.instance.runtime_properties[count_events][execution_id] = last_event


def is_system_workflows_finished(client, check_all_in_deployment=False):
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
                'Executions list failed {0}.'.format(str(ex)))

        for execution in executions:
            if execution.get('is_system_workflow'):
                if execution.get('status') not in ('terminated', 'failed',
                                                   'cancelled'):
                    return False

            if check_all_in_deployment:
                if check_all_in_deployment == execution.get('deployment_id'):
                    if execution.get('status') not in ('terminated', 'failed',
                                                       'cancelled'):
                        return False

        if executions.metadata.pagination.total <= \
                executions.metadata.pagination.offset:
            break

        offset = offset + size

    return True


def dep_workflow_in_state_pollster(client,
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
            'The exec get response form {0} is {1}'.format(dep_id,
                                                           execution))

    except CloudifyClientError as ex:
        raise NonRecoverableError(
            'Executions get failed {0}.'.format(str(ex)))

    execution_id = execution.get('id')
    if log_redirect and execution_id:
        ctx.logger.debug(
            '_exec info for _log_redirect is {0}'.format(execution))
        redirect_logs(client, execution_id)

    execution_status = execution.get('status')
    if execution_status == state:
        ctx.logger.debug(
            'The status for _exec info id'
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
        lambda: dep_workflow_in_state_pollster(**pollster_args),
        timeout=timeout,
        interval=interval)

    if not result:
        raise NonRecoverableError(
            'Execution timeout: {0} seconds.'.format(timeout))
    return True
