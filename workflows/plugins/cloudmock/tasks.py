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

__author__ = 'idanmo'

from cloudify.decorators import operation


RUNNING = "running"
NOT_RUNNING = "not_running"
machines = {}
raise_exception_on_start = False


@operation
def provision(ctx, **kwargs):
    global machines
    ctx.logger.info("cloudmock provision: [node_id=%s, machines=%s]",
                    ctx.node_id, machines)
    if ctx.node_id in machines:
        raise RuntimeError("machine with id [{0}] already exists"
                           .format(ctx.node_id))
    machines[ctx.node_id] = NOT_RUNNING


@operation
def start(ctx, **kwargs):
    global machines
    ctx.logger.info("cloudmock start: [node_id={0}, machines={1}]".format(
        ctx.node_id, machines))
    if ctx.node_id not in machines:
        raise RuntimeError("machine with id [{0}] does not exist"
                           .format(ctx.node_id))
    machines[ctx.node_id] = RUNNING
    ctx['id'] = ctx.node_id
    global raise_exception_on_start
    if raise_exception_on_start:
        raise RuntimeError('Exception raised from CloudMock.start()!')
    ctx.set_started()


@operation
def stop(ctx, **kwargs):
    global machines
    ctx.logger.info("stopping machine: " + ctx.node_id)
    if ctx.node_id not in machines:
        raise RuntimeError("machine with id [{0}] does not exist"
                           .format(ctx.node_id))
    machines[ctx.node_id] = NOT_RUNNING
    ctx.set_stopped()


@operation
def terminate(ctx, **kwargs):
    global machines
    ctx.logger.info("terminating machine: " + ctx.node_id)
    if ctx.node_id not in machines:
        raise RuntimeError("machine with id [{0}] does not exist"
                           .format(ctx.node_id))
    del machines[ctx.node_id]


@operation
def get_machines(**kwargs):
    return machines


@operation
def set_raise_exception_on_start(**kwargs):
    global raise_exception_on_start
    raise_exception_on_start = True
