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
from cloudify import context
from cloudify import ctx

from mock_plugins.cloudify_agent.installer import process
from mock_plugins.cloudify_agent.installer import consumer

from testenv.utils import update_storage


@operation
def create(cloudify_agent=None, **_):
    installer = get_backend(cloudify_agent)
    installer.create()
    worker_name = installer.agent_name
    with update_storage(ctx) as data:
        data[worker_name] = data.get(worker_name, {})
        data[worker_name]['states'] = data[worker_name].get('states', [])
        data[worker_name]['states'].append('created')


@operation
def configure(cloudify_agent=None, **_):
    installer = get_backend(cloudify_agent)
    installer.create()
    worker_name = installer.agent_name
    with update_storage(ctx) as data:
        data[worker_name] = data.get(worker_name, {})
        data[worker_name]['states'] = data[worker_name].get('states', [])
        data[worker_name]['states'].append('configured')


@operation
def start(cloudify_agent=None, **_):
    installer = get_backend(cloudify_agent)
    installer.start()
    worker_name = installer.agent_name
    with update_storage(ctx) as data:
        data[worker_name] = data.get(worker_name, {})
        data[worker_name]['states'] = data[worker_name].get('states', [])
        data[worker_name]['states'].append('started')


@operation
def stop(cloudify_agent=None, **_):
    installer = get_backend(cloudify_agent)
    installer.stop()
    worker_name = installer.agent_name
    with update_storage(ctx) as data:
        data[worker_name] = data.get(worker_name, {})
        data[worker_name]['states'] = data[worker_name].get('states', [])
        data[worker_name]['states'].append('stopped')


@operation
def delete(cloudify_agent=None, **_):

    installer = get_backend(cloudify_agent)
    installer.delete()
    worker_name = installer.agent_name
    with update_storage(ctx) as data:
        if 'raise_exception_on_delete' in data:
            raise Exception("Exception raised intentionally")
        data[worker_name] = data.get(worker_name, {})
        data[worker_name]['states'] = data[worker_name].get('states', [])
        data[worker_name]['states'].append('deleted')

    if ctx.type == context.NODE_INSTANCE:
        del ctx.instance.runtime_properties['cloudify_agent']


@operation
def restart(cloudify_agent=None, **_):
    installer = get_backend(cloudify_agent)
    worker_name = installer.agent_name
    installer.restart()
    with update_storage(ctx) as data:
        data[worker_name] = data.get(worker_name, {})
        data[worker_name]['states'] = data[worker_name].get('states', [])
        data[worker_name]['states'].append('restarted')


def get_backend(cloudify_agent=None):
    if not cloudify_agent:
        cloudify_agent = {}
    if _is_workflows_worker(cloudify_agent):
        cloudify_agent['name'] = '{0}_workflows'.format(ctx.deployment.id)
    elif ctx.type == context.DEPLOYMENT:
        cloudify_agent['name'] = ctx.deployment.id
    else:
        cloudify_agent['name'] = ctx.instance.id
    cloudify_agent['queue'] = cloudify_agent['name']
    if ctx.type == context.NODE_INSTANCE:
        ctx.instance.runtime_properties['cloudify_agent'] = cloudify_agent
    if os.environ.get('PROCESS_MODE'):
        return process.ProcessBackedAgentInstaller(cloudify_agent)
    return consumer.ConsumerBackedAgentInstaller(cloudify_agent)


def _is_workflows_worker(cloudify_agent):
    if 'workflows_worker' in cloudify_agent:
        workflows_worker = cloudify_agent['workflows_worker']
        return workflows_worker
    return False
