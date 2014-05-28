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

INSTALLED = "installed"
STARTED = "started"
STOPPED = "stopped"
UNINSTALLED = "uninstalled"
RESTARTED = "restarted"

workers_state = {}

current_worker_name = None


def fix_worker(ctx, **kwargs):
    worker_config = {}
    if ctx.properties and 'worker_config' in ctx.properties:
        worker_config = ctx.properties['worker_config']
    if _is_workflows_worker(kwargs):
        worker_config['name'] = 'cloudify.workflows'
    elif ctx.node_id is None:
        worker_config['name'] = ctx.deployment_id
    else:
        worker_config['name'] = ctx.node_id
    return worker_config


@operation
def install(ctx, **kwargs):
    worker_config = fix_worker(ctx, **kwargs)

    global current_worker_name
    global workers_state

    ctx.logger.info("Installing worker {0}".format(worker_config["name"]))
    if not _is_workflows_worker(kwargs):
        current_worker_name = worker_config["name"]
    workers_state[worker_config["name"]] = [INSTALLED]


@operation
def start(ctx, **kwargs):
    worker_config = fix_worker(ctx, **kwargs)

    global workers_state

    ctx.logger.info("Starting worker {0}".format(worker_config["name"]))
    # adding a consumer that handles tasks from a
    # queue called worker_config["name"]
    ctx.logger.info("Workers state before change is {0}".format(workers_state))
    workers_state[worker_config["name"]].append(STARTED)


@operation
def restart(ctx, **kwargs):
    worker_config = fix_worker(ctx, **kwargs)

    global workers_state

    ctx.logger.info("Restarting worker {0}".format(worker_config["name"]))
    workers_state[worker_config["name"]].append(RESTARTED)


@operation
def stop(ctx, **kwargs):
    worker_config = fix_worker(ctx, **kwargs)

    global workers_state

    ctx.logger.info("Stopping worker {0}".format(worker_config["name"]))
    if worker_config["name"] not in workers_state:
        ctx.logger.debug("No worker. nothing to do.")
        return
    workers_state[worker_config["name"]].append(STOPPED)


@operation
def uninstall(ctx, **kwargs):
    worker_config = fix_worker(ctx, **kwargs)

    global workers_state

    ctx.logger.info("Uninstalling worker {0}".format(worker_config["name"]))
    if worker_config["name"] not in workers_state:
        ctx.logger.debug("No worker. nothing to do.")
        return
    workers_state[worker_config["name"]].append(UNINSTALLED)


@operation
def get_current_worker_state(workflows_worker=False, **kwargs):
    name = 'cloudify.workflows' if workflows_worker else current_worker_name
    return workers_state[name]


def _is_workflows_worker(config_container):
    return 'worker_config' in config_container and 'workflows_worker' in \
           config_container['worker_config'] and config_container[
           'worker_config']['workflows_worker']
