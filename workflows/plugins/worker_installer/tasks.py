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
from cloudify.celery import celery as app

INSTALLED = "installed"
STARTED = "started"
STOPPED = "stopped"
UNINSTALLED = "uninstalled"
RESTARTED = "restarted"

workers_state = {}

current_worker_name = None


def fix_worker(ctx, worker_config):
    if ctx.node_id is None:
        worker_config['name'] = ctx.deployment_id
    else:
        worker_config['name'] = ctx.node_id


@operation
def install(ctx, **kwargs):
    worker_config = ctx.properties['worker_config']
    fix_worker(ctx, worker_config)

    global current_worker_name
    global workers_state

    ctx.logger.info("Installing worker {0}".format(worker_config["name"]))
    current_worker_name = worker_config["name"]
    workers_state[worker_config["name"]] = [INSTALLED]


@operation
def start(ctx, worker_config, local=False, **kwargs):

    fix_worker(ctx, worker_config)

    global workers_state

    ctx.logger.info("Starting worker {0}".format(worker_config["name"]))
    # adding a consumer that handles tasks from a
    # queue called worker_config["name"]
    app.control.add_consumer(worker_config["name"], reply=True)
    ctx.logger.info("Workers state before change is {0}".format(workers_state))
    workers_state[worker_config["name"]].append(STARTED)


@operation
def restart(ctx, worker_config, local=False, **kwargs):

    fix_worker(ctx, worker_config)

    global workers_state

    ctx.logger.info("Restarting worker {0}".format(worker_config["name"]))
    workers_state[worker_config["name"]].append(RESTARTED)


@operation
def stop(ctx, worker_config, local=False, **kwargs):

    fix_worker(ctx, worker_config)

    global workers_state

    ctx.logger.info("Stopping worker {0}".format(worker_config["name"]))
    if worker_config["name"] not in workers_state:
        ctx.logger.debug("No worker. nothing to do.")
        return
    app.control.cancel_consumer(worker_config["name"], reply=True)
    workers_state[worker_config["name"]].append(STOPPED)


@operation
def uninstall(ctx, worker_config, local=False, **kwargs):

    fix_worker(ctx, worker_config)

    global workers_state

    ctx.logger.info("Uninstalling worker {0}".format(worker_config["name"]))
    if worker_config["name"] not in workers_state:
        ctx.logger.debug("No worker. nothing to do.")
        return
    workers_state[worker_config["name"]].append(UNINSTALLED)


@operation
def get_current_worker_state(**kwargs):
    return workers_state[current_worker_name]
