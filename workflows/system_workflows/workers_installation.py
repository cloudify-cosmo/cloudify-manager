########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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

__author__ = 'ran'


from cloudify.decorators import workflow
from cloudify.workflows.tasks_graph import TaskDependencyGraph


WORKFLOWS_WORKER_PAYLOAD = {
    'worker_config': {
        'workflows_worker': True
    }
}


@workflow
def install(ctx, **kwargs):
    graph = TaskDependencyGraph(ctx)

    sequence = graph.sequence()

    management_plugins = kwargs['management_plugins_to_install']
    workflow_plugins = kwargs['workflow_plugins_to_install']

    # installing the operations worker
    sequence.add(
        ctx.send_event('Installing deployment operations worker'),
        ctx.execute_task(
            task_queue='cloudify.management',
            task_name='worker_installer.tasks.install'),
        ctx.send_event('Starting deployment operations worker'),
        ctx.execute_task(
            task_queue='cloudify.management',
            task_name='worker_installer.tasks.start'))

    if management_plugins:
        sequence.add(
            ctx.send_event('Installing deployment operations plugins'),
            ctx.execute_task(
                task_queue=ctx.deployment_id,
                task_name='plugin_installer.tasks.install',
                kwargs={'plugins': management_plugins}))

    sequence.add(
        ctx.execute_task(
            task_queue='cloudify.management',
            task_name='worker_installer.tasks.restart'))

    # installing the workflows worker
    sequence.add(
        ctx.send_event('Installing deployment workflows worker'),
        ctx.execute_task(
            task_queue='cloudify.management',
            task_name='worker_installer.tasks.install',
            kwargs=WORKFLOWS_WORKER_PAYLOAD),
        ctx.send_event('Starting deployment workflows worker'),
        ctx.execute_task(
            task_queue='cloudify.management',
            task_name='worker_installer.tasks.start',
            kwargs=WORKFLOWS_WORKER_PAYLOAD))

    if workflow_plugins:
        sequence.add(
            ctx.send_event('Installing deployment workflows plugins'),
            ctx.execute_task(
                task_queue='{0}_workflows'.format(ctx.deployment_id),
                task_name='plugin_installer.tasks.install',
                kwargs={'plugins': workflow_plugins}))

    sequence.add(
        ctx.execute_task(
            task_queue='cloudify.management',
            task_name='worker_installer.tasks.restart',
            kwargs=WORKFLOWS_WORKER_PAYLOAD))

    return graph.execute()


@workflow
def uninstall(ctx, **kwargs):

    graph = TaskDependencyGraph(ctx)

    sequence = graph.sequence()

    # uninstalling the operations worker
    sequence.add(
        ctx.send_event('Stopping deployment operations worker'),
        ctx.execute_task(
            task_queue='cloudify.management',
            task_name='worker_installer.tasks.stop'),
        ctx.send_event('Uninstalling deployment operations worker'),
        ctx.execute_task(
            task_queue='cloudify.management',
            task_name='worker_installer.tasks.uninstall'))

    # uninstalling the workflows worker
    sequence.add(
        ctx.send_event('Stopping deployment workflows worker'),
        ctx.execute_task(
            task_queue='cloudify.management',
            task_name='worker_installer.tasks.stop',
            kwargs=WORKFLOWS_WORKER_PAYLOAD),
        ctx.send_event('Uninstall deployment workflows worker'),
        ctx.execute_task(
            task_queue='cloudify.management',
            task_name='worker_installer.tasks.uninstall',
            kwargs=WORKFLOWS_WORKER_PAYLOAD))

    return graph.execute()
