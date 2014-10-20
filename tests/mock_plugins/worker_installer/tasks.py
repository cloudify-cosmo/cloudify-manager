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
from testenv.utils import update_storage
from cloudify import context
from cloudify.workflows import tasks
from cloudify.celery import celery
from testenv.utils import task_exists


# This is needed because in this
# environment, all tasks are sent to
# the management worker, and handled by
# different consumers. The original method
# asserts that tasks are being sent to
# different workers,
tasks.verify_task_registered = task_exists


@operation
def install(ctx, **kwargs):
    agent_config = _fix_worker(ctx, **kwargs)
    worker_name = agent_config['name']
    ctx.logger.info('Installing worker {0}'.format(worker_name))
    with update_storage(ctx) as data:
        data[worker_name] = data.get(worker_name, {})
        data[worker_name]['states'] = data[worker_name].get('states', [])
        data[worker_name]['states'].append('installed')
        data[worker_name]['pids'] = []


@operation
def start(ctx, **kwargs):
    agent_config = _fix_worker(ctx, **kwargs)
    worker_name = agent_config['name']
    ctx.logger.info('Starting worker {0}'.format(worker_name))
    celery.control.add_consumer(
        queue=worker_name,
        destination=['celery.cloudify.management']
    )
    with update_storage(ctx) as data:
        data[worker_name] = data.get(worker_name, {})
        data[worker_name]['states'] = data[worker_name].get('states', [])
        data[worker_name]['states'].append('started')
        data[worker_name]['pids'] = []


@operation
def restart(ctx, **kwargs):
    stop(ctx, **kwargs)
    start(ctx, **kwargs)


@operation
def stop(ctx, **kwargs):
    agent_config = _fix_worker(ctx, **kwargs)
    worker_name = agent_config['name']
    ctx.logger.info('Stopping worker {0}'.format(worker_name))
    celery.control.cancel_consumer(
        queue=worker_name,
        destination=['celery.cloudify.management']
    )
    with update_storage(ctx) as data:
        data[worker_name] = data.get(worker_name, {})
        data[worker_name]['states'] = data[worker_name].get('states', [])
        data[worker_name]['states'].append('stopped')
        data[worker_name]['pids'] = []


@operation
def uninstall(ctx, **kwargs):
    agent_config = _fix_worker(ctx, **kwargs)
    worker_name = agent_config['name']
    ctx.logger.info('Uninstalling worker {0}'.format(worker_name))
    with update_storage(ctx) as data:
        data[worker_name] = data.get(worker_name, {})
        data[worker_name]['states'] = data[worker_name].get('states', [])
        data[worker_name]['states'].append('uninstalled')
        data[worker_name]['pids'] = []


def _fix_worker(ctx, **kwargs):
    agent_config = {}
    if _is_workflows_worker(kwargs):
        agent_config['name'] = '{0}_workflows'.format(ctx.deployment.id)
    elif ctx.type == context.DEPLOYMENT:
        agent_config['name'] = ctx.deployment.id
    else:
        agent_config['name'] = ctx.instance.id
    return agent_config


def _is_workflows_worker(config_container):
    if 'cloudify_agent' in config_container:
        cloudify_agent = config_container['cloudify_agent']
        if 'workflows_worker' in cloudify_agent:
            workflows_worker = cloudify_agent['workflows_worker']
            return workflows_worker
    return False
