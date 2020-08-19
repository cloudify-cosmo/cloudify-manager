########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
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

from retrying import retry

from cloudify.decorators import workflow
from cloudify.workflows import workflow_context
from cloudify.workflows import tasks as workflow_tasks
from cloudify.manager import get_rest_client


def generate_create_dep_tasks_graph(ctx):
    graph = ctx.graph_mode()
    sequence = graph.sequence()
    sequence.add(
        ctx.send_event('Creating deployment work directory'),
        ctx.local_task(_create_deployment_workdir,
                       kwargs={'deployment_id': ctx.deployment.id,
                               'tenant': ctx.tenant_name,
                               'logger': ctx.logger}))

    return graph


@workflow
def create(ctx, **_):
    graph = generate_create_dep_tasks_graph(ctx)
    return graph.execute()


@workflow
def delete(ctx,
           deployment_plugins_to_uninstall,
           workflow_plugins_to_uninstall,
           delete_logs,
           **_):
    graph = ctx.graph_mode()
    sequence = graph.sequence()

    sequence.add(
        ctx.send_event(
            'Deleting deployment [{}] environment'.format(
                ctx.deployment.id)))

    graph.execute()
    _delete_deployment_workdir(ctx)
    if delete_logs:
        ctx.send_event(
            "Deleting management workers' logs for deployment")
        _delete_logs(ctx)
    _send_request_to_delete_deployment_from_db(ctx)


def _send_request_to_delete_deployment_from_db(ctx):
    client = get_rest_client()
    client.deployments.delete(deployment_id=ctx.deployment.id,
                              force=True,
                              delete_db_mode=True)


def _delete_logs(ctx):
    log_dir = os.environ.get('AGENT_LOG_DIR')
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
                    'Failed truncating {0}.'.format(log_file_path),
                    exc_info=True)
        for rotated_log_file_path in glob.glob('{0}.*'.format(
                log_file_path)):
            try:
                os.remove(rotated_log_file_path)
            except IOError:
                ctx.logger.exception(
                    'Failed removing rotated log file {0}.'.format(
                        rotated_log_file_path), exc_info=True)


def _ignore_task_on_fail_and_send_event(task, ctx):
    def failure_handler(tsk):
        ctx.send_event('Ignoring task {0} failure'.format(tsk.name))
        return workflow_tasks.HandlerResult.ignore()

    task.on_failure = failure_handler


def _retry_if_file_already_exists(exception):
    """Retry if file already exist exception raised."""
    return (
        isinstance(exception, OSError) and
        exception.errno == errno.EEXIST
    )


@workflow_context.task_config(send_task_events=False)
@retry(retry_on_exception=_retry_if_file_already_exists,
       stop_max_delay=60000,
       wait_fixed=2000)
def _create_deployment_workdir(deployment_id, logger, tenant):
    deployment_workdir = _workdir(deployment_id, tenant)
    try:
        os.makedirs(deployment_workdir)
    except OSError as e:
        if e.errno == errno.EEXIST:
            dir_content = os.listdir(deployment_workdir)
            # if dir exists and empty then no problem
            if dir_content:
                logger.error('Failed creating directory %s. '
                             'Current directory content: %s',
                             deployment_workdir, dir_content)
                raise
            else:
                logger.warn('Using existing empty deployment directory '
                            '{0}'.format(deployment_workdir))
        else:
            raise


def _delete_deployment_workdir(ctx):
    deployment_workdir = _workdir(ctx.deployment.id, ctx.tenant_name)
    if not os.path.exists(deployment_workdir):
        return
    try:
        shutil.rmtree(deployment_workdir)
    except os.error:
        ctx.logger.warning(
            'Failed deleting directory %s. Current directory content: %s',
            deployment_workdir, os.listdir(deployment_workdir), exc_info=True)


def _workdir(deployment_id, tenant):
    base_workdir = os.environ['AGENT_WORK_DIR']
    return os.path.join(base_workdir, 'deployments', tenant, deployment_id)
