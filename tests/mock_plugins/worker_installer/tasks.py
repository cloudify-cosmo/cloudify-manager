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
from mock_plugins.worker_installer.consumer import \
    ConsumerBackedWorkerInstaller
from mock_plugins.worker_installer.process import \
    ProcessBackedWorkerInstaller

from testenv.utils import update_storage
from testenv.utils import task_exists

from cloudify.decorators import operation
from cloudify import context
from cloudify.workflows import tasks


# This is needed because in this
# environment, all tasks are sent to
# the management worker, and handled by
# different consumers. The original method
# asserts that tasks are being sent to
# different workers,
tasks.verify_task_registered = task_exists


from cloudify import ctx


@operation
def install(cloudify_agent=None, **kwargs):
    installer = get_backend(cloudify_agent)
    installer.install()
    worker_name = installer.agent_name
    with update_storage(ctx) as data:
        data[worker_name] = data.get(worker_name, {})
        data[worker_name]['states'] = data[worker_name].get('states', [])
        data[worker_name]['states'].append('installed')
        data[worker_name]['pids'] = []


@operation
def start(cloudify_agent=None, **kwargs):
    installer = get_backend(cloudify_agent)
    installer.start()
    worker_name = installer.agent_name
    with update_storage(ctx) as data:
        data[worker_name] = data.get(worker_name, {})
        data[worker_name]['states'] = data[worker_name].get('states', [])
        data[worker_name]['states'].append('started')
        data[worker_name]['pids'] = []


@operation
def restart(cloudify_agent=None, **kwargs):
    installer = get_backend(cloudify_agent)
    worker_name = installer.agent_name
    installer.restart()
    with update_storage(ctx) as data:
        data[worker_name] = data.get(worker_name, {})
        data[worker_name]['states'] = data[worker_name].get('states', [])
        data[worker_name]['states'].append('restarted')


@operation
def stop(cloudify_agent=None, **kwargs):
    installer = get_backend(cloudify_agent)
    installer.stop()
    worker_name = installer.agent_name
    with update_storage(ctx) as data:
        data[worker_name] = data.get(worker_name, {})
        data[worker_name]['states'] = data[worker_name].get('states', [])
        data[worker_name]['states'].append('stopped')
        data[worker_name]['pids'] = []


@operation
def uninstall(cloudify_agent=None, **kwargs):
    installer = get_backend(cloudify_agent)
    installer.uninstall()
    worker_name = installer.agent_name
    with update_storage(ctx) as data:
        data[worker_name] = data.get(worker_name, {})
        data[worker_name]['states'] = data[worker_name].get('states', [])
        data[worker_name]['states'].append('uninstalled')
        data[worker_name]['pids'] = []


def get_backend(cloudify_agent):
    if not cloudify_agent:
        cloudify_agent = {}
    if _is_workflows_worker(cloudify_agent):
        cloudify_agent['name'] = '{0}_workflows'.format(ctx.deployment.id)
    elif ctx.type == context.DEPLOYMENT:
        cloudify_agent['name'] = ctx.deployment.id
    else:
        cloudify_agent['name'] = ctx.instance.id
    if os.environ.get('PROCESS_MODE'):
        return ProcessBackedWorkerInstaller(cloudify_agent)
    return ConsumerBackedWorkerInstaller(cloudify_agent)


def _is_workflows_worker(cloudify_agent):
    if 'workflows_worker' in cloudify_agent:
        workflows_worker = cloudify_agent['workflows_worker']
        return workflows_worker
    return False
