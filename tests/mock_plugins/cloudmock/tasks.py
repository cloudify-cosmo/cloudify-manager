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


from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError
from testenv.utils import update_storage
from cloudify import ctx

DEFAULT_VM_IP = '10.0.0.1'

RUNNING = 'running'
NOT_RUNNING = 'not_running'


@operation
def provision(**kwargs):
    with update_storage(ctx) as data:
        machines = data.get('machines', {})
        if ctx.node_id in machines:
            raise NonRecoverableError('machine with id [{0}] already exists'
                                      .format(ctx.node_id))
        if ctx.properties.get('test_ip'):
            ctx.runtime_properties['ip'] = ctx.properties['test_ip']
        else:
            ctx.runtime_properties['ip'] = DEFAULT_VM_IP
        machines[ctx.node_id] = NOT_RUNNING
        data['machines'] = machines


@operation
def start(**kwargs):
    with update_storage(ctx) as data:
        machines = data.get('machines', {})
        ctx.send_event('starting machine event')
        ctx.logger.info('cloudmock start: [node_id={0}, machines={1}]'
                        .format(ctx.node_id, machines))
        if ctx.node_id not in machines:
            raise NonRecoverableError('machine with id [{0}] does not exist'
                                      .format(ctx.node_id))
        machines[ctx.node_id] = RUNNING
        ctx.runtime_properties['id'] = ctx.node_id


@operation
def start_error(**kwargs):
    raise RuntimeError('Exception raised from cloudmock.start()!')


@operation
def stop_error(**kwargs):
    raise RuntimeError('Exception raised from cloudmock.stop()!')


@operation
def get_state(**kwargs):
    with update_storage(ctx) as data:
        return data['machines'][ctx.node_id] == RUNNING


@operation
def stop(**kwargs):
    with update_storage(ctx) as data:
        ctx.logger.info('stopping machine: {0}'.format(ctx.node_id))
        if ctx.node_id not in data['machines']:
            raise RuntimeError('machine with id [{0}] does not exist'
                               .format(ctx.node_id))
        data['machines'][ctx.node_id] = NOT_RUNNING


@operation
def terminate(**kwargs):
    with update_storage(ctx) as data:
        ctx.logger.info('terminating machine: {0}'.format(ctx.node_id))
        if ctx.node_id not in data['machines']:
            raise RuntimeError('machine with id [{0}] does not exist'
                               .format(ctx.node_id))
        del data['machines'][ctx.node_id]
