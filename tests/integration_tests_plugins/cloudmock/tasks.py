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
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError
from cloudify import ctx

from integration_tests_plugins.utils import update_storage


RUNNING = 'running'
NOT_RUNNING = 'not_running'


def _resumable_task_base(ctx, wait_message, target_file):
    ctx.instance.runtime_properties['resumed'] = False
    ctx.instance.update()
    while not os.path.exists(target_file):
        ctx.logger.info(wait_message)
        time.sleep(1)
    ctx.instance.runtime_properties['resumed'] = True


@operation
def task_agent(ctx, wait_message, **kwargs):
    ctx.instance.runtime_properties['resumed'] = False
    ctx.instance.update()
    ctx.logger.info(wait_message)
    time.sleep(20)
    ctx.logger.info(wait_message[::-1])
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
def failing(ctx, target_file, **kwargs):
    if not os.path.exists(target_file):
        raise ValueError('Error')
    ctx.instance.runtime_properties['resumed'] = True


@operation
def mark_instance(ctx, **kwargs):
    ctx.instance.runtime_properties['marked'] = True


@operation
def provision(**kwargs):
    with update_storage(ctx) as data:
        machines = data.get('machines', {})
        if ctx.instance.id in machines:
            raise NonRecoverableError('machine with id [{0}] already exists'
                                      .format(ctx.instance.id))
        if ctx.node.properties.get('test_ip'):
            ctx.instance.runtime_properties['ip'] = \
                ctx.node.properties['test_ip']
        machines[ctx.instance.id] = NOT_RUNNING
        data['machines'] = machines


@operation
def start(**kwargs):
    with update_storage(ctx) as data:
        machines = data.get('machines', {})
        ctx.send_event('starting machine event')
        ctx.logger.info('cloudmock start: [node_id={0}, machines={1}]'
                        .format(ctx.instance.id, machines))
        if ctx.instance.id not in machines:
            raise NonRecoverableError('machine with id [{0}] does not exist'
                                      .format(ctx.instance.id))
        machines[ctx.instance.id] = RUNNING
        ctx.instance.runtime_properties['id'] = ctx.instance.id


@operation
def start_error(**kwargs):
    raise RuntimeError('Exception raised from cloudmock.start()!')


@operation
def stop_error(**kwargs):
    raise RuntimeError('Exception raised from cloudmock.stop()!')


@operation
def get_state(**kwargs):
    with update_storage(ctx) as data:
        return data['machines'][ctx.instance.id] == RUNNING


@operation
def stop(**kwargs):
    with update_storage(ctx) as data:
        ctx.logger.info('stopping machine: {0}'.format(ctx.instance.id))
        if ctx.instance.id not in data['machines']:
            raise RuntimeError('machine with id [{0}] does not exist'
                               .format(ctx.instance.id))
        data['machines'][ctx.instance.id] = NOT_RUNNING


@operation
def terminate(**kwargs):
    with update_storage(ctx) as data:
        ctx.logger.info('terminating machine: {0}'.format(ctx.instance.id))
        if ctx.instance.id not in data['machines']:
            raise RuntimeError('machine with id [{0}] does not exist'
                               .format(ctx.instance.id))
        del data['machines'][ctx.instance.id]


@operation
def hook_task(context, **kwargs):
    with open('/tmp/hook_task.txt', 'a') as f:
        f.write("In hook_task, context: {0} kwargs: {1}"
                .format(context, kwargs))
