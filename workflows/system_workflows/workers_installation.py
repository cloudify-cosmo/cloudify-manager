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


WORKFLOWS_WORKER_PAYLOAD = {
    'cloudify_agent': {
        'workflows_worker': True
    }
}


@workflow
def install(ctx, **kwargs):

    graph = ctx.graph_mode()
    sequence = graph.sequence()

    management_plugins = kwargs['management_plugins_to_install']
    workflow_plugins = kwargs['workflow_plugins_to_install']

    # installing the operations worker
    sequence.add(
        ctx.send_event('Installing deployment operations worker'),
        ctx.execute_task(
            task_name='worker_installer.tasks.install'),
        ctx.send_event('Starting deployment operations worker'),
        ctx.execute_task(
            task_name='worker_installer.tasks.start'))

    if management_plugins:
        sequence.add(
            ctx.send_event('Installing deployment operations plugins'),
            ctx.execute_task(
                task_queue=ctx.deployment_id,
                task_name='plugin_installer.tasks.install',
                kwargs={'plugins': management_plugins}),
            ctx.execute_task(
                task_name='worker_installer.tasks.restart'))

    # installing the workflows worker
    sequence.add(
        ctx.send_event('Installing deployment workflows worker'),
        ctx.execute_task(
            task_name='worker_installer.tasks.install',
            kwargs=WORKFLOWS_WORKER_PAYLOAD),
        ctx.send_event('Starting deployment workflows worker'),
        ctx.execute_task(
            task_name='worker_installer.tasks.start',
            kwargs=WORKFLOWS_WORKER_PAYLOAD))

    if workflow_plugins:
        sequence.add(
            ctx.send_event('Installing deployment workflows plugins'),
            ctx.execute_task(
                task_queue='{0}_workflows'.format(ctx.deployment_id),
                task_name='plugin_installer.tasks.install',
                kwargs={'plugins': workflow_plugins}),
            ctx.execute_task(
                task_name='worker_installer.tasks.restart',
                kwargs=WORKFLOWS_WORKER_PAYLOAD))

    # Start deployment policy engine core
    # sequence.add(
    #     ctx.send_event('Starting deployment policy engine core'),
    #     ctx.execute_task('riemann_controller.tasks.create',
    #                      kwargs=kwargs.get('policy_configuration', {})))

    return graph.execute()


@workflow
def uninstall(ctx, **kwargs):

    graph = ctx.graph_mode()
    sequence = graph.sequence()

    sequence.add(
        # uninstalling the operations worker
        ctx.send_event('Stopping deployment operations worker'),
        ctx.execute_task(
            task_name='worker_installer.tasks.stop'),
        ctx.send_event('Uninstalling deployment operations worker'),
        ctx.execute_task(
            task_name='worker_installer.tasks.uninstall'),

        # uninstalling the workflows worker
        ctx.send_event('Stopping deployment workflows worker'),
        ctx.execute_task(
            task_name='worker_installer.tasks.stop',
            kwargs=WORKFLOWS_WORKER_PAYLOAD),
        ctx.send_event('Uninstall deployment workflows worker'),
        ctx.execute_task(
            task_name='worker_installer.tasks.uninstall',
            kwargs=WORKFLOWS_WORKER_PAYLOAD))

    # Stop deployment policy engine core
    # sequence.add(
    #     ctx.send_event('Stopping deployment policy engine core'),
    #     ctx.execute_task('riemann_controller.tasks.delete'))

    return graph.execute()
