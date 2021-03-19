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
from cloudify.manager import get_rest_client
from cloudify.workflows import workflow_context

from cloudify_rest_client.exceptions import CloudifyClientError
from dsl_parser import tasks


def _join_groups(client, deployment_id, groups):
    for group_name in groups:
        try:
            client.deployment_groups.add_deployments(
                group_name, deployment_ids=[deployment_id])
        except CloudifyClientError as e:
            if e.status_code != 404:
                raise
            client.deployment_groups.put(
                group_name, deployment_ids=[deployment_id])


@workflow
def create(ctx, labels=None, inputs=None, skip_plugins_validation=False, **_):
    client = get_rest_client(tenant=ctx.tenant_name)
    bp = client.blueprints.get(ctx.blueprint.id)
    deployment_plan = tasks.prepare_deployment_plan(
        bp.plan, client.secrets.get, inputs)
    nodes = deployment_plan['nodes']
    node_instances = deployment_plan['node_instances']

    ctx.logger.info('Creating %d nodes', len(nodes))
    client.nodes.create_many(ctx.deployment.id, nodes)
    ctx.logger.info('Creating %d node-instances', len(node_instances))
    client.node_instances.create_many(ctx.deployment.id, node_instances)
    ctx.logger.info('Setting deployment attributes')
    labels_to_create = labels or []
    labels_to_create += [
        {k: v} for k, labels_def in deployment_plan.get('labels', {}).items()
        for v in labels_def.get('values', [])
    ]
    client.deployments.set_attributes(
        ctx.deployment.id,
        description=deployment_plan['description'],
        workflows=deployment_plan['workflows'],
        inputs=deployment_plan['inputs'],
        policy_types=deployment_plan['policy_types'],
        policy_triggers=deployment_plan['policy_triggers'],
        groups=deployment_plan['groups'],
        scaling_groups=deployment_plan['scaling_groups'],
        outputs=deployment_plan['outputs'],
        capabilities=deployment_plan.get('capabilities', {}),
        labels=labels_to_create,
    )

    deployment_settings = deployment_plan.get('deployment_settings', {})
    _join_groups(client, ctx.deployment.id,
                 deployment_settings.get('default_groups', []))

    ctx.logger.info('Creating deployment work directory')
    _create_deployment_workdir(
        deployment_id=ctx.deployment.id,
        tenant=ctx.tenant_name,
        logger=ctx.logger)


@workflow
def delete(ctx, delete_logs, **_):
    ctx.logger.info('Deleting deployment environment: %s', ctx.deployment.id)
    _delete_deployment_workdir(ctx)
    if delete_logs:
        ctx.logger.info("Deleting management workers' logs for deployment %s",
                        ctx.deployment.id)
        _delete_logs(ctx)


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
    if os.path.exists(deployment_workdir):
        # Otherwise we experience pain on snapshot restore
        return
    os.makedirs(deployment_workdir)


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
    return os.path.join('/opt', 'manager', 'resources', 'deployments',
                        tenant, deployment_id)
