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
from cloudify.workflows import tasks as workflow_tasks


def generate_create_dep_tasks_graph(ctx,
                                    deployment_plugins_to_install,
                                    workflow_plugins_to_install,
                                    policy_configuration=None):
    graph = ctx.graph_mode()
    sequence = graph.sequence()

    dep_plugins = [p for p in deployment_plugins_to_install if p['install']]
    wf_plugins = [p for p in workflow_plugins_to_install if p['install']]
    plugins_to_install = dep_plugins + wf_plugins
    if plugins_to_install:
        sequence.add(
            ctx.send_event('Installing deployment plugins'),
            ctx.execute_task('cloudify_agent.operations.install_plugins',
                             kwargs={'plugins': plugins_to_install}))

    sequence.add(
        ctx.send_event('Starting deployment policy engine core'),
        ctx.execute_task('riemann_controller.tasks.create',
                         kwargs=policy_configuration or {}))

    return graph


@workflow
def create(ctx,
           deployment_plugins_to_install,
           workflow_plugins_to_install,
           policy_configuration, **_):
    graph = generate_create_dep_tasks_graph(
        ctx,
        deployment_plugins_to_install,
        workflow_plugins_to_install,
        policy_configuration)
    return graph.execute()


@workflow
def delete(ctx,
           deployment_plugins_to_uninstall,
           workflow_plugins_to_uninstall,
           **kwargs):
    graph = ctx.graph_mode()
    sequence = graph.sequence()

    dep_plugins = [p for p in deployment_plugins_to_uninstall if p['install']]
    wf_plugins = [p for p in workflow_plugins_to_uninstall if p['install']]
    plugins_to_uninstall = dep_plugins + wf_plugins
    if plugins_to_uninstall:
        sequence.add(
            ctx.send_event('Uninstalling deployment plugins'),
            ctx.execute_task(
                task_name='cloudify_agent.operations.uninstall_plugins',
                kwargs={'plugins': plugins_to_uninstall}),
            ctx.send_event('Stopping deployment policy engine core'),
            ctx.execute_task('riemann_controller.tasks.delete'))

    for task in graph.tasks_iter():
        _ignore_task_on_fail_and_send_event(task, ctx)

    return graph.execute()


def _ignore_task_on_fail_and_send_event(task, ctx):
    def failure_handler(tsk):
        ctx.send_event('Ignoring task {0} failure'.format(tsk.name))
        return workflow_tasks.HandlerResult.ignore()
    task.on_failure = failure_handler
