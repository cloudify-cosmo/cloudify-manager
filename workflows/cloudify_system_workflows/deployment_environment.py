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


from cloudify.decorators import workflow


WORKFLOWS_WORKER_PAYLOAD = {
    'cloudify_agent': {
        'workflows_worker': True
    }
}


@workflow
def create(ctx, **kwargs):

    graph = ctx.graph_mode()
    sequence = graph.sequence()

    deployment_plugins = kwargs['deployment_plugins_to_install']

    deployment_plugins = filter(lambda plugin: plugin['install'],
                                deployment_plugins)

    workflow_plugins = kwargs['workflow_plugins_to_install']

    workflow_plugins = filter(lambda plugin: plugin['install'],
                              workflow_plugins)

    # installing the operations worker
    sequence.add(
        ctx.send_event('Creating deployment operations worker'),
        ctx.execute_task(
            task_name='cloudify_agent.installer.operations.create'),
        ctx.send_event('Configuring deployment operations worker'),
        ctx.execute_task(
            task_name='cloudify_agent.installer.operations.configure'),
        ctx.send_event('Starting deployment operations worker'),
        ctx.execute_task(
            task_name='cloudify_agent.installer.operations.start')
    )

    if deployment_plugins:
        sequence.add(
            ctx.send_event('Installing deployment operations plugins'),
            ctx.execute_task(
                task_queue=ctx.deployment.id,
                task_target=ctx.deployment.id,
                task_name='cloudify_agent.operations'
                          '.install_plugins',
                kwargs={'plugins': deployment_plugins},
                local=False),
            ctx.execute_task(
                task_name='cloudify_agent.installer.operations.restart',
                send_task_events=False))

    # installing the workflows worker
    sequence.add(
        ctx.send_event('Creating deployment workflows worker'),
        ctx.execute_task(
            task_name='cloudify_agent.installer.operations.create',
            kwargs=WORKFLOWS_WORKER_PAYLOAD),
        ctx.send_event('Configuring deployment workflows worker'),
        ctx.execute_task(
            task_name='cloudify_agent.installer.operations.configure',
            kwargs=WORKFLOWS_WORKER_PAYLOAD),
        ctx.send_event('Starting deployment workflows worker'),
        ctx.execute_task(
            task_name='cloudify_agent.installer.operations.start',
            kwargs=WORKFLOWS_WORKER_PAYLOAD))

    if workflow_plugins:
        sequence.add(
            ctx.send_event('Installing deployment workflows plugins'),
            ctx.execute_task(
                task_queue='{0}_workflows'.format(ctx.deployment.id),
                task_target='{0}_workflows'.format(ctx.deployment.id),
                task_name='cloudify_agent.operations'
                          '.install_plugins',
                kwargs={'plugins': workflow_plugins},
                local=False),
            ctx.execute_task(
                task_name='cloudify_agent.installer.operations.restart',
                send_task_events=False,
                kwargs=WORKFLOWS_WORKER_PAYLOAD))

    # Start deployment policy engine core
    sequence.add(
        ctx.send_event('Starting deployment policy engine core'),
        ctx.execute_task('riemann_controller.tasks.create',
                         kwargs=kwargs.get('policy_configuration', {})))

    return graph.execute()


@workflow
def delete(ctx, **kwargs):

    graph = ctx.graph_mode()
    sequence = graph.sequence()

    sequence.add(
        # uninstalling the operations worker
        ctx.send_event('Stopping deployment operations worker'),
        ctx.execute_task(
            task_name='cloudify_agent.installer.operations.stop'),
        ctx.send_event('Deleting deployment operations worker'),
        ctx.execute_task(
            task_name='cloudify_agent.installer.operations.delete'),

        # uninstalling the workflows worker
        ctx.send_event('Stopping deployment workflows worker'),
        ctx.execute_task(
            task_name='cloudify_agent.installer.operations.stop',
            kwargs=WORKFLOWS_WORKER_PAYLOAD),
        ctx.send_event('Deleting deployment workflows worker'),
        ctx.execute_task(
            task_name='cloudify_agent.installer.operations.delete',
            kwargs=WORKFLOWS_WORKER_PAYLOAD))

    # Stop deployment policy engine core
    sequence.add(
        ctx.send_event('Stopping deployment policy engine core'),
        ctx.execute_task('riemann_controller.tasks.delete'))

    return graph.execute()
