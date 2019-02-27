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
                      pollster_args=None,
                      expected_result=True):

    pollster_args = pollster_args or dict()
    # Check if timeout value is -1 that allows infinite timeout
    # If timeout value is not -1 then it is a finite timeout
    timeout = float('infinity') if timeout == -1 else timeout
    current_time = time.time()

    ctx.logger.debug('Timeout value is {}'.format(timeout))

    while time.time() <= current_time + timeout:
        if pollster(**pollster_args) != expected_result:
            ctx.logger.debug('Polling...')
            time.sleep(interval)
        else:
            ctx.logger.debug('Polling succeeded!')
            return True

    ctx.logger.error('Polling timed out!')
    return False


def dep_logs_redirect(_client, execution_id):
    COUNT_EVENTS = "received_events"

    if not ctx.instance.runtime_properties.get(COUNT_EVENTS):
        ctx.instance.runtime_properties[COUNT_EVENTS] = {}

    last_event = int(ctx.instance.runtime_properties[COUNT_EVENTS].get(
        execution_id, 0
    ))

    full_count = last_event + 100

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
            full_count = last_event + 100
        # returned nothing, let's do it next time
        if len(events) == 0:
            ctx.logger.log(20, "Returned nothing, let's get logs next time.")
            break

    ctx.instance.runtime_properties[COUNT_EVENTS][execution_id] = last_event


def dep_system_workflows_finished(_client, _check_all_in_deployment=False):

    _offset = int(getenv('_PAGINATION_OFFSET', 0))
    _size = int(getenv('_PAGINATION_SIZE', 1000))

    while True:

        try:
            _execs = _client.executions.list(
                include_system_workflows=True,
                _offset=_offset,
                _size=_size)
        except CloudifyClientError as ex:
            raise NonRecoverableError(
                'Executions list failed {0}.'.format(str(ex)))

        for _exec in _execs:

            if _exec.get('is_system_workflow'):
                if _exec.get('status') not in ('terminated', 'failed',
                                               'cancelled'):
                    return False

            if _check_all_in_deployment:
                if _check_all_in_deployment == _exec.get('deployment_id'):
                    if _exec.get('status') not in ('terminated', 'failed',
                                                   'cancelled'):
                        return False

        if _execs.metadata.pagination.total <= \
                _execs.metadata.pagination.offset:
            break

        _offset = _offset + _size

    return True


def dep_workflow_in_state_pollster(_client,
                                   _dep_id,
                                   _state,
                                   _workflow_id=None,
                                   _log_redirect=False,
                                   _execution_id=None):

    exec_get_fields = \
        ['status', 'workflow_id', 'created_at', 'id']

    try:
        _exec = \
            _client.executions.get(execution_id=_execution_id,
                                   _include=exec_get_fields)

        ctx.logger.debug(
            'The exec get response form {0} is {1}'.format(_dep_id, _exec))

    except CloudifyClientError as ex:
        raise NonRecoverableError(
            'Executions get failed {0}.'.format(str(ex)))

    if _log_redirect and _exec.get('id'):
        ctx.logger.debug(
            '_exec info for _log_redirect is {0}'.format(_exec))
        dep_logs_redirect(_client, _exec.get('id'))

    if _exec.get('status') == _state:
        ctx.logger.debug(
            'The status for _exec info id'
            ' {0} is {1}'.format(_execution_id, _state))

        return True
    elif _exec.get('status') == 'failed':
        raise NonRecoverableError(
            'Execution {0} failed.'.format(str(_exec)))

    return False


def poll_workflow_after_execute(_timeout,
                                _interval,
                                _client,
                                _dep_id,
                                _state,
                                _workflow_id,
                                _execution_id,
                                _log_redirect=False):

    pollster_args = {
        '_client': _client,
        '_dep_id': _dep_id,
        '_state': _state,
        '_workflow_id': _workflow_id,
        '_log_redirect': _log_redirect,
        '_execution_id': _execution_id,
    }

    ctx.logger.debug('Polling: {0}'.format(pollster_args))

    success = \
        poll_with_timeout(
            dep_workflow_in_state_pollster,
            timeout=_timeout,
            interval=_interval,
            pollster_args=pollster_args)

    if not success:
        raise NonRecoverableError(
            'Execution timeout: {0} seconds.'.format(_timeout))
    return True
