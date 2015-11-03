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


from cloudify import celery
from cloudify.decorators import workflow
from cloudify.manager import get_rest_client
from cloudify.workflows.workflow_context import task_config


WORKFLOWS_WORKER_PAYLOAD = {
    'cloudify_agent': {
        'workflows_worker': True
    }
}


def generate_create_dep_tasks_graph(ctx, deployment_plugins_to_install,
                                    workflow_plugins_to_install,
                                    policy_configuration=None):
    graph = ctx.graph_mode()
    sequence = graph.sequence()

    is_transient_workers = _is_transient_deployment_workers_mode()

    deployment_plugins = filter(lambda plugin: plugin['install'],
                                deployment_plugins_to_install)

    workflow_plugins = filter(lambda plugin: plugin['install'],
                              workflow_plugins_to_install)

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

    if is_transient_workers:
        sequence.add(
            ctx.send_event('Stopping deployment operations worker'),
            ctx.execute_task(
                task_name='cloudify_agent.installer.operations.stop'))

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

    if is_transient_workers:
        sequence.add(
            ctx.send_event('Stopping deployment workflows worker'),
            ctx.execute_task(
                task_name='cloudify_agent.installer.operations.stop',
                kwargs=WORKFLOWS_WORKER_PAYLOAD))

    # Start deployment policy engine core
    sequence.add(
        ctx.send_event('Starting deployment policy engine core'),
        ctx.execute_task('riemann_controller.tasks.create',
                         kwargs=policy_configuration or {}))

    return graph


@workflow
def create(ctx, deployment_plugins_to_install, workflow_plugins_to_install,
           policy_configuration, **_):
    graph = generate_create_dep_tasks_graph(
        ctx,
        deployment_plugins_to_install,
        workflow_plugins_to_install,
        policy_configuration)
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


@workflow
def start(ctx, **kwargs):
    graph = ctx.graph_mode()
    sequence = graph.sequence()

    sequence.add(
        ctx.send_event('Starting deployment operations worker'),
        ctx.execute_task(
            task_name='cloudify_agent.installer.operations.start'),

        ctx.send_event('Starting deployment workflows worker'),
        ctx.execute_task(
            task_name='cloudify_agent.installer.operations.start',
            kwargs=WORKFLOWS_WORKER_PAYLOAD))

    return graph.execute()


@workflow
def stop(ctx, prerequisite_task_id, prerequisite_task_timeout=60, **kwargs):
    graph = ctx.graph_mode()
    sequence = graph.sequence()

    @task_config(total_retries=1)
    def wait_for_prerequisite_task_to_finish():
        async_result = celery.celery.AsyncResult(prerequisite_task_id)
        async_result.get(timeout=prerequisite_task_timeout, propagate=False)
        if async_result.status not in (
                celery.TASK_STATE_SUCCESS, celery.TASK_STATE_FAILURE):
            raise RuntimeError(
                'Failed to stop deployment environment: User workflow '
                'execution updated to final state yet the task (id {0}) has '
                'failed to complete in {1} seconds'.format(
                    prerequisite_task_id, prerequisite_task_timeout))

    sequence.add(
        ctx.local_task(wait_for_prerequisite_task_to_finish),
        ctx.send_event('Stopping deployment operations worker'),
        ctx.execute_task(
            task_name='cloudify_agent.installer.operations.stop'),

        ctx.send_event('Stopping deployment workflows worker'),
        ctx.execute_task(
            task_name='cloudify_agent.installer.operations.stop',
            kwargs=WORKFLOWS_WORKER_PAYLOAD))

    return graph.execute()


def _is_transient_deployment_workers_mode():
    client = get_rest_client()
    bootstrap_context = client.manager.get_context()['context']['cloudify']
    return bootstrap_context.get(
        'transient_deployment_workers_mode', {}).get('enabled', True)
