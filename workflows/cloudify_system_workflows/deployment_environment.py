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

import glob
import os
import shutil
import errno

from cloudify.decorators import workflow
from cloudify.workflows import tasks as workflow_tasks
from cloudify.workflows import workflow_context


def _should_create_policy_engine_core(policy_configuration):
    """Examine the policy_configuration and decide to start a riemann core
    """
    return any(group.get('policies')
               for group in policy_configuration['groups'].values())


def _merge_deployment_and_workflow_plugins(deployment_plugins,
                                           workflow_plugins):
    added_plugins = set()
    result = []

    def add_plugins(plugins):
        for plugin in plugins:
            if plugin['name'] in added_plugins:
                continue
            added_plugins.add(plugin['name'])
            result.append(plugin)

    for plugins in (deployment_plugins, workflow_plugins):
        add_plugins(plugins)
    return result


def generate_create_dep_tasks_graph(ctx,
                                    deployment_plugins_to_install,
                                    workflow_plugins_to_install,
                                    policy_configuration=None):
    graph = ctx.graph_mode()
    sequence = graph.sequence()

    dep_plugins = [p for p in deployment_plugins_to_install if p['install']]
    wf_plugins = [p for p in workflow_plugins_to_install if p['install']]
    plugins_to_install = _merge_deployment_and_workflow_plugins(dep_plugins,
                                                                wf_plugins)
    if plugins_to_install:
        sequence.add(
            ctx.send_event('Installing deployment plugins'),
            ctx.execute_task('cloudify_agent.operations.install_plugins',
                             kwargs={'plugins': plugins_to_install}))

    if _should_create_policy_engine_core(policy_configuration):
        sequence.add(
            ctx.send_event('Starting deployment policy engine core'),
            ctx.execute_task('riemann_controller.tasks.create',
                             kwargs=policy_configuration))
    else:
        sequence.add(
            ctx.send_event('Skipping starting deployment policy engine '
                           'core - no policies defined'))

    sequence.add(
        ctx.send_event('Creating deployment work directory'),
        ctx.local_task(_create_deployment_workdir,
                       kwargs={'deployment_id': ctx.deployment.id,
                               'tenant': ctx.tenant_name,
                               'logger': ctx.logger}))

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

    sequence.add(
        ctx.send_event(
                'Deleting deployment [{}] environment'.format(
                    ctx.deployment.id)))

    dep_plugins = [p for p in deployment_plugins_to_uninstall if p['install']]
    wf_plugins = [p for p in workflow_plugins_to_uninstall if p['install']]
    plugins_to_uninstall = dep_plugins + wf_plugins
    if plugins_to_uninstall:
        sequence.add(
            ctx.send_event('Uninstalling deployment plugins'),
            ctx.execute_task(
                task_name='cloudify_agent.operations.uninstall_plugins',
                kwargs={'plugins': plugins_to_uninstall}))

    sequence.add(
        ctx.send_event('Stopping deployment policy engine core '
                       '(if applicable)'),
        ctx.execute_task('riemann_controller.tasks.delete'))

    for task in graph.tasks_iter():
        _ignore_task_on_fail_and_send_event(task, ctx)

    try:
        return graph.execute()
    finally:
        _delete_deployment_workdir(ctx)
        _delete_logs(ctx)


def _delete_logs(ctx):
    log_dir = os.environ.get('CELERY_LOG_DIR')
    if log_dir:
        log_file_path = os.path.join(log_dir, 'logs',
                                     '{0}.log'.format(ctx.deployment.id))
        if os.path.exists(log_file_path):
            try:
                with open(log_file_path, 'w') as f:
                    # Truncating instead of deleting because the logging
                    # server currently holds a file descriptor open to this
                    # file. If we delete the file, the logs for new
                    # deployments that get created with the same deployment
                    # id, will get written to a stale file descriptor and
                    # will essentially be lost.
                    f.truncate()
            except IOError:
                ctx.logger.warn(
                    'Failed truncating {0}.'.format(log_file_path,
                                                    exc_info=True))
        for rotated_log_file_path in glob.glob('{0}.*'.format(
                log_file_path)):
            try:
                os.remove(rotated_log_file_path)
            except IOError:
                ctx.logger.exception(
                    'Failed removing rotated log file {0}.'.format(
                        rotated_log_file_path, exc_info=True))


def _ignore_task_on_fail_and_send_event(task, ctx):
    def failure_handler(tsk):
        ctx.send_event('Ignoring task {0} failure'.format(tsk.name))
        return workflow_tasks.HandlerResult.ignore()

    task.on_failure = failure_handler


@workflow_context.task_config(send_task_events=False)
def _create_deployment_workdir(deployment_id, logger, tenant):
    deployment_workdir = _workdir(deployment_id, tenant)
    try:
        os.makedirs(deployment_workdir)
    except os.error as e:
        if e.errno == errno.EEXIST:
            logger.error('Failed creating directory {0}. '
                         'Current directory content: {1}'.format(
                            deployment_workdir,
                            os.listdir(deployment_workdir)))
        raise


def _delete_deployment_workdir(ctx):
    deployment_workdir = _workdir(ctx.deployment.id, ctx.tenant_name)
    if not os.path.exists(deployment_workdir):
        return
    try:
        shutil.rmtree(deployment_workdir)
    except os.error:
        ctx.logger.warning('Failed deleting directory {0}. '
                           'Current directory content: {1}'.format(
                                deployment_workdir,
                                os.listdir(deployment_workdir), exc_info=True))


def _workdir(deployment_id, tenant):
    base_workdir = os.environ['CELERY_WORK_DIR']
    return os.path.join(base_workdir, 'deployments', tenant, deployment_id)
