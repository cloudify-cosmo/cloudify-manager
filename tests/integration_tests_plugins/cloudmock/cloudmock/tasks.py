########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import os
import time
from cloudify.decorators import operation, workflow
from cloudify.exceptions import NonRecoverableError
from cloudify.manager import get_rest_client
from cloudify import ctx


RUNNING = 'running'
NOT_RUNNING = 'not_running'


def _merge_handler(prev_props, next_props):
    """On conflict in updating runtime-props, take the newer ones, but
    make sure that 'resumed' is true of either was true"""
    if 'resumed' in prev_props or 'resumed' in next_props:
        next_props['resumed'] = (prev_props.get('resumed', False) or
                                 next_props.get('resumed', False))
    return next_props


def _is_unlocked():
    """IS the current operation allowed to continue?

    The operations are unlocked from within the test code (see test_resume.py),
    to simulate long-running operations and be able to control when are
    cancel/resume commands executed. (otherwise we'd have to rely on sleeps)
    """
    return ctx.operation.name in \
        ctx.instance.runtime_properties.get('unlock', [])


def _resumable_task_base(ctx):
    ctx.instance.runtime_properties['resumed'] = False
    ctx.instance.update(_merge_handler)
    while not _is_unlocked():
        ctx.instance.refresh()
        ctx.logger.info('{0} WAITING'.format(ctx.operation.name))
        time.sleep(1)
    ctx.instance.runtime_properties['resumed'] = True

    # fetch some file, any file, to see if downloading works aftter a resume
    downloaded_data = ctx.download_resource('resumable_mgmtworker.yaml')
    ctx.logger.info('Downloaded data: %s bytes', len(downloaded_data))

    ctx.instance.update(_merge_handler)


@operation
def task_agent(ctx, **kwargs):
    ctx.instance.runtime_properties['resumed'] = False
    ctx.instance.update()
    ctx.logger.info('BEFORE SLEEP')
    time.sleep(20)
    ctx.logger.info('AFTER SLEEP')
    ctx.instance.runtime_properties['resumed'] = True


@operation
def retrying_task(ctx, **kwargs):
    count = ctx.instance.runtime_properties.get('count', 0)

    ctx.instance.runtime_properties['count'] = count + 1
    ctx.instance.update()

    count = ctx.instance.runtime_properties['count']
    if count == 1:
        return ctx.operation.retry()
    elif count == 2:
        raise NonRecoverableError('Error')


@operation(resumable=True)
def resumable(**kwargs):
    _resumable_task_base(**kwargs)


@operation(resumable=False)
def nonresumable(**kwargs):
    _resumable_task_base(**kwargs)


@operation
def failing(ctx, **kwargs):
    if not _is_unlocked():
        raise NonRecoverableError('Error')
    ctx.instance.runtime_properties['resumed'] = True


@operation
def mark_instance(ctx, **kwargs):
    ctx.instance.runtime_properties['marked'] = True


@operation
def provision(ctx, **kwargs):
    machines = ctx.instance.runtime_properties.get('machines', {})
    if ctx.instance.id in machines:
        raise NonRecoverableError('machine with id [{0}] already exists'
                                  .format(ctx.instance.id))
    if ctx.node.properties.get('test_ip'):
        ctx.instance.runtime_properties['ip'] = \
            ctx.node.properties['test_ip']
    machines[ctx.instance.id] = NOT_RUNNING
    ctx.instance.runtime_properties['machines'] = machines


@operation
def start(**kwargs):
    machines = ctx.instance.runtime_properties.get('machines', {})
    ctx.send_event('starting machine event')
    ctx.logger.info('cloudmock start: [node_id={0}, machines={1}]'
                    .format(ctx.instance.id, machines))
    if ctx.instance.id not in machines:
        raise NonRecoverableError('machine with id [{0}] does not exist'
                                  .format(ctx.instance.id))
    machines[ctx.instance.id] = RUNNING
    ctx.instance.runtime_properties['id'] = ctx.instance.id
    ctx.instance.runtime_properties['machines'] = machines


@operation
def start_error(**kwargs):
    raise RuntimeError('Exception raised from cloudmock.start()!')


@operation
def stop_error(**kwargs):
    raise RuntimeError('Exception raised from cloudmock.stop()!')


@operation
def get_state(ctx, **kwargs):
    machines = ctx.instance.runtime_properties['machines']
    return machines[ctx.instance.id] == RUNNING


@operation
def stop(**kwargs):
    machines = ctx.instance.runtime_properties.get('machines', {})
    ctx.logger.info('stopping machine: {0}'.format(ctx.instance.id))
    if ctx.instance.id not in machines:
        raise RuntimeError('machine with id [{0}] does not exist'
                           .format(ctx.instance.id))
    machines[ctx.instance.id] = NOT_RUNNING
    ctx.instance.runtime_properties['machines'] = machines


@operation
def terminate(**kwargs):
    machines = ctx.instance.runtime_properties.get('machines', {})
    ctx.logger.info('terminating machine: {0}'.format(ctx.instance.id))
    if ctx.instance.id not in machines:
        raise RuntimeError('machine with id [{0}] does not exist'
                           .format(ctx.instance.id))
    del machines[ctx.instance.id]
    ctx.instance.runtime_properties['machines'] = machines


@operation
def hook_task(context, **kwargs):
    with open('/tmp/hook_task.txt', 'a') as f:
        f.write("In hook_task, context: {0} kwargs: {1}"
                .format(context, kwargs))


@workflow
def workflow1(ctx):
    client = get_rest_client()
    for ni in client.node_instances.list():
        client.node_instances.update(
            ni.id,
            version=ni.version,
            runtime_properties={'custom_workflow': True}
        )


def wait(ctx, delay=5, **kwargs):
    time.sleep(delay)
    ctx.logger.info('wait done; slept %s', delay)


@operation
def store_pid(ctx, delay=180, **kwargs):
    """Store our PID and sleep.

    Useful for tests that involve kill-cancel.
    """
    ctx.instance.runtime_properties['pid'] = os.getpid()
    ctx.instance.update()
    time.sleep(delay)
