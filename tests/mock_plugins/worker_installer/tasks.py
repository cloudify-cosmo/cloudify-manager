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

from cloudify.decorators import operation
from testenv.processes.celery import CeleryWorkerProcess
from testenv.utils import update_storage


@operation
def install(ctx, **kwargs):
    worker = get_instance(ctx, **kwargs)
    ctx.logger.info('Installing worker {0}'.format(worker.name))
    worker.create_dirs()
    with update_storage(ctx) as data:
        data[worker.name] = data.get(worker.name, {})
        data[worker.name]['states'] = data[worker.name].get('states', [])
        data[worker.name]['states'].append('installed')
        data[worker.name]['pids'] = []



@operation
def start(ctx, **kwargs):
    worker = get_instance(ctx, **kwargs)
    ctx.logger.info('Starting worker {0}'.format(worker.name))
    worker.start()

    with update_storage(ctx) as data:
        data[worker.name] = data.get(worker.name, {})
        data[worker.name]['states'] = data[worker.name].get('states', [])
        data[worker.name]['states'].append('started')
        data[worker.name]['pids'] = worker.pids


@operation
def restart(ctx, **kwargs):
    stop(ctx, **kwargs)
    start(ctx, **kwargs)


@operation
def stop(ctx, **kwargs):
    worker = get_instance(ctx, **kwargs)
    ctx.logger.info('Stopping worker {0}'.format(worker.name))
    worker.stop()
    with update_storage(ctx) as data:
        data[worker.name] = data.get(worker.name, {})
        data[worker.name]['states'] = data[worker.name].get('states', [])
        data[worker.name]['states'].append('stopped')
        data[worker.name]['pids'] = []


@operation
def uninstall(ctx, **kwargs):
    worker = get_instance(ctx, **kwargs)
    ctx.logger.info('Uninstalling worker {0}'.format(worker.name))
    worker.delete_dirs()
    with update_storage(ctx) as data:
        data[worker.name] = data.get(worker.name, {})
        data[worker.name]['states'] = data[worker.name].get('states', [])
        data[worker.name]['states'].append('uninstalled')
        data[worker.name]['pids'] = []


def _fix_worker(ctx, **kwargs):
    agent_config = {}
    if _is_workflows_worker(kwargs):
        agent_config['name'] = '{0}_workflows'.format(ctx.deployment_id)
        agent_config['includes'] = ['cloudify.plugins.workflows']
    elif ctx.node_id is None:
        agent_config['name'] = ctx.deployment_id
        agent_config['includes'] = None
    else:
        agent_config['name'] = ctx.node_id
        agent_config['includes'] = None
    return agent_config


def _is_workflows_worker(config_container):
    if 'cloudify_agent' in config_container:
        cloudify_agent = config_container['cloudify_agent']
        if 'workflows_worker' in cloudify_agent:
            workflows_worker = cloudify_agent['workflows_worker']
            return workflows_worker
    return False


def get_instance(ctx, **kwargs):
    agent_config = _fix_worker(ctx, **kwargs)
    worker_name = agent_config['name']
    test_working_dir = os.environ['TEST_WORKING_DIR']
    return CeleryWorkerProcess(
        queues=[worker_name],
        test_working_dir=test_working_dir,
        includes=agent_config['includes']
    )
