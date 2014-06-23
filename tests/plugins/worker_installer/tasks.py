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
import os
import json

DATA_FILE_PATH = '/tmp/agent-installer-data.json'

INSTALLED = "installed"
STARTED = "started"
STOPPED = "stopped"
UNINSTALLED = "uninstalled"
RESTARTED = "restarted"


@operation
def install(ctx, **kwargs):
    worker_config = _fix_worker(ctx, **kwargs)
    data = _get_data()

    ctx.logger.info("Installing worker {0}".format(worker_config["name"]))
    data['workers_state'][worker_config["name"]] = [INSTALLED]
    _store_data(data)


@operation
def start(ctx, **kwargs):
    worker_config = _fix_worker(ctx, **kwargs)
    data = _get_data()

    ctx.logger.info("Starting worker {0}".format(worker_config["name"]))
    # adding a consumer that handles tasks from a
    # queue called worker_config["name"]
    ctx.logger.info("Workers state before change is {0}".format(
        data['workers_state']))
    data['workers_state'][worker_config["name"]].append(STARTED)
    _store_data(data)


@operation
def restart(ctx, **kwargs):
    worker_config = _fix_worker(ctx, **kwargs)
    data = _get_data()

    ctx.logger.info("Restarting worker {0}".format(worker_config["name"]))
    data['workers_state'][worker_config["name"]].append(RESTARTED)
    _store_data(data)


@operation
def stop(ctx, **kwargs):
    worker_config = _fix_worker(ctx, **kwargs)
    data = _get_data()

    ctx.logger.info("Stopping worker {0}".format(worker_config["name"]))
    if worker_config["name"] not in data['workers_state']:
        ctx.logger.debug("No worker. nothing to do.")
        return
    data['workers_state'][worker_config["name"]].append(STOPPED)
    _store_data(data)


@operation
def uninstall(ctx, **kwargs):
    worker_config = _fix_worker(ctx, **kwargs)
    data = _get_data()

    ctx.logger.info("Uninstalling worker {0}".format(worker_config["name"]))
    if worker_config["name"] not in data['workers_state']:
        ctx.logger.debug("No worker. nothing to do.")
        return
    data['workers_state'][worker_config["name"]].append(UNINSTALLED)
    _store_data(data)


@operation
def get_worker_state(worker_name, **kwargs):
    data = _get_data()
    return data['workers_state'][worker_name]


def _fix_worker(ctx, **kwargs):
    worker_config = {}
    if _is_workflows_worker(kwargs):
        worker_config['name'] = '{0}_workflows'.format(ctx.deployment_id)
    elif ctx.node_id is None:
        worker_config['name'] = ctx.deployment_id
    else:
        worker_config['name'] = ctx.node_id
    return worker_config


def _is_workflows_worker(config_container):
    return 'worker_config' in config_container and \
           'workflows_worker' in config_container['worker_config'] and \
           config_container['worker_config']['workflows_worker']


def _get_data():
    with open(DATA_FILE_PATH, 'r') as f:
        data = json.load(f)
        return data


def _store_data(data):
    with open(DATA_FILE_PATH, 'w') as f:
        json.dump(data, f)


def setup_plugin():
    data = {
        'workers_state': {}
    }
    _store_data(data)


def teardown_plugin():
    os.remove(DATA_FILE_PATH)
