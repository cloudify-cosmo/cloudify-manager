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

from cosmo.events import set_reachable
from cosmo.events import set_unreachable
from cloudify.decorators import operation
from cloudify.decorators import context


RUNNING = "running"
NOT_RUNNING = "not_running"

reachable = set_reachable
unreachable = set_unreachable
machines = {}


@operation
@context
def provision(__cloudify_id, ctx, **kwargs):
    global machines
    ctx.logger.info("provisioning machine: " + __cloudify_id)
    if __cloudify_id in machines:
        raise RuntimeError("machine with id [{0}] already exists"
                           .format(__cloudify_id))
    machines[__cloudify_id] = NOT_RUNNING


@operation
@context
def start(ctx, __cloudify_id, **kwargs):
    global machines
    ctx.logger.info("starting machine: " + __cloudify_id)
    if __cloudify_id not in machines:
        raise RuntimeError("machine with id [{0}] does not exist"
                           .format(__cloudify_id))
    machines[__cloudify_id] = RUNNING
    ctx['id'] = __cloudify_id

    reachable(__cloudify_id)


@operation
@context
def stop(__cloudify_id, ctx, **kwargs):
    global machines
    ctx.logger.info("stopping machine: " + __cloudify_id)
    if __cloudify_id not in machines:
        raise RuntimeError("machine with id [{0}] does not exist"
                           .format(__cloudify_id))
    machines[__cloudify_id] = NOT_RUNNING


@operation
@context
def terminate(__cloudify_id, ctx, **kwargs):
    global machines
    ctx.logger.info("terminating machine: " + __cloudify_id)
    if __cloudify_id not in machines:
        raise RuntimeError("machine with id [{0}] does not exist"
                           .format(__cloudify_id))
    del machines[__cloudify_id]
    unreachable(__cloudify_id)


@operation
def get_machines(**kwargs):
    return machines
