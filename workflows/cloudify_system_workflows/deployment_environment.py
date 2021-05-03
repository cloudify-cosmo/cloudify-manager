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
from datetime import datetime
import unicodedata

from retrying import retry

from cloudify.decorators import workflow
from cloudify.deployment_dependencies import create_deployment_dependency
from cloudify.manager import get_rest_client
from cloudify.workflows import workflow_context

from cloudify.utils import parse_utc_datetime_relative
from cloudify_rest_client.client import CloudifyClient
from cloudify_rest_client.exceptions import CloudifyClientError
from dsl_parser import constants as dsl
from dsl_parser import tasks


def _get_display_name(display_name, settings):
    display_name = display_name or settings.get('display_name')
    if not display_name:
        return

    if len(display_name) > 256:
        raise ValueError(
            'The deployment display name is too long. '
            'Maximum allowed length is 256 characters'
        )
    if any(unicodedata.category(char)[0] == 'C' for char in display_name):
        raise ValueError(
            'The deployment display name contains illegal characters. '
            'Control characters are not allowed'
        )

    return unicodedata.normalize('NFKC', display_name)


def _parse_plan_datetime(time_expression, base_datetime):
    """
    :param time_expression: Either a string representing an absolute
        datetime, or a relative time delta, such as '+4 hours' or '+1y+1d'.
    :param base_datetime: a datetime object representing the absolute date
        and time to which we apply the time delta.
    :return: A naive datetime object, in UTC time.
    """
    time_fmt = '%Y-%m-%d %H:%M:%S'
    if time_expression.startswith('+'):
        return parse_utc_datetime_relative(time_expression, base_datetime)
    return datetime.strptime(time_expression, time_fmt)


def _create_schedules(client, deployment_id, schedules):
    base_time = datetime.utcnow()
    for name, spec in schedules.items():
        workflow_id = spec.pop('workflow')
        if 'since' in spec:
            spec['since'] = _parse_plan_datetime(spec['since'], base_time)
        if 'until' in spec:
            spec['until'] = _parse_plan_datetime(spec['until'], base_time)
        if 'workflow_parameters' in spec:
            spec['parameters'] = spec.pop('workflow_parameters')
        client.execution_schedules.create(
            name,
            deployment_id=deployment_id,
            workflow_id=workflow_id,
            **spec
        )


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


def _get_deployment_labels(new_labels, plan_labels):
    labels = {tuple(label) for label in new_labels}
    for name, label_spec in plan_labels.items():
        labels |= {(name.lower(), value) for value in
                   label_spec.get('values', [])}
    return [{k: v} for k, v in labels]


@workflow
def create(ctx, labels=None, inputs=None, skip_plugins_validation=False,
           display_name=None, **_):
    client = get_rest_client(tenant=ctx.tenant_name)
    bp = client.blueprints.get(ctx.blueprint.id)
    deployment_plan = tasks.prepare_deployment_plan(
        bp.plan, client.secrets.get, inputs,
        runtime_only_evaluation=ctx.deployment.runtime_only_evaluation)
    nodes = deployment_plan['nodes']
    node_instances = deployment_plan['node_instances']

    ctx.logger.info('Creating %d nodes', len(nodes))
    client.nodes.create_many(ctx.deployment.id, nodes)
    ctx.logger.info('Creating %d node-instances', len(node_instances))
    client.node_instances.create_many(ctx.deployment.id, node_instances)

    labels_to_create = _get_deployment_labels(
        labels or [],
        deployment_plan.get('labels', {}))

    ctx.logger.info('Setting deployment attributes')
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
    # deployment_settings can depend on labels etc, so we must evaluate
    # functions in it after setting labels
    deployment_settings = client.evaluate.functions(
        ctx.deployment.id,
        {},
        deployment_plan.get('deployment_settings', {}),
    )['payload']
    display_name = _get_display_name(display_name, deployment_settings)
    if display_name:
        client.deployments.set_attributes(
            ctx.deployment.id, display_name=display_name)
    _join_groups(client, ctx.deployment.id,
                 deployment_settings.get('default_groups', []))
    _create_schedules(client, ctx.deployment.id,
                      deployment_settings.get('default_schedules', {}))

    ctx.logger.info('Creating deployment work directory')
    _create_deployment_workdir(
        deployment_id=ctx.deployment.id,
        tenant=ctx.tenant_name,
        logger=ctx.logger)

    new_dependencies = deployment_plan.setdefault(
        dsl.INTER_DEPLOYMENT_FUNCTIONS, {})
    if new_dependencies:
        ctx.logger.info('Creating inter-deployment dependencies')
        manager_ips = [manager.private_ip
                       for manager in client.manager.get_managers()]
        ext_client, client_config, ext_deployment_id = \
            _get_external_clients(nodes, manager_ips)

        local_tenant_name = ctx.deployment.tenant_name if ext_client else None
        local_idds, external_idds = _create_inter_deployment_dependencies(
            [manager.private_ip for manager in client.manager.get_managers()],
            client_config, new_dependencies, ctx.deployment.id,
            local_tenant_name, bool(ext_client), ext_deployment_id)
        if local_idds:
            client.inter_deployment_dependencies.create_many(
                ctx.deployment.id,
                local_idds)
        if external_idds:
            ext_client.inter_deployment_dependencies.create_many(
                ctx.deployment.id,
                external_idds)


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


def _create_inter_deployment_dependencies(manager_ips: list,
                                          client_config,
                                          new_dependencies: dict,
                                          local_deployment_id: str,
                                          local_tenant_name: str,
                                          external: bool,
                                          ext_deployment_id: str) -> tuple:
    local_idds = []
    external_idds = []
    for func_id, deployment_id_func in new_dependencies.items():
        target_deployment_id, target_deployment_func = deployment_id_func
        if external:
            local_idds += [
                create_deployment_dependency(
                    dependency_creator=func_id,
                    target_deployment=None,
                    external_target={
                        'deployment': (ext_deployment_id
                                       if ext_deployment_id else None),
                        'client_config': client_config
                    })]
            external_idds += [
                create_deployment_dependency(
                    dependency_creator=func_id,
                    target_deployment=(target_deployment_id
                                       if target_deployment_id else ' '),
                    external_source={
                        'deployment': local_deployment_id,
                        'tenant': local_tenant_name,
                        'host': manager_ips,
                    })]
        else:
            # It should be safe to assume that if the target_deployment
            # is known, there's no point passing target_deployment_func.
            # Also because in this case the target_deployment_func will
            # be of type string, while REST endpoint expects a dict.
            local_idds += [
                create_deployment_dependency(
                    dependency_creator=func_id,
                    target_deployment=target_deployment_id,
                    target_deployment_func=(
                        target_deployment_func if not target_deployment_id
                        else None)
                )]
    return local_idds, external_idds


def _get_external_clients(nodes: list, manager_ips: list):
    client_config = None
    target_deployment = None
    for node in nodes:
        if node['type'] in ['cloudify.nodes.Component',
                            'cloudify.nodes.SharedResource']:
            client_config = node['properties'].get('client')
            target_deployment = node['properties'].get(
                'resource_config').get('deployment')
            break
    external_client = None
    if client_config:
        internal_hosts = ({'127.0.0.1', 'localhost'} | set(manager_ips))
        host = client_config['host']
        host = {host} if type(host) == str else set(host)
        if not (host & internal_hosts):
            external_client = CloudifyClient(**client_config)

    return external_client, client_config, \
        target_deployment.get('id') if target_deployment else None


@workflow
def update_deployment(ctx, **kwargs):
    """Run an update on this deployment. Any kwargs are passed to the update.

    This exposes deployment update creation as a workflow on the deployment.
    """
    client = get_rest_client(tenant=ctx.tenant_name)
    deployment_update = \
        client.deployment_updates.update_with_existing_blueprint(
            deployment_id=ctx.deployment.id,
            **kwargs
        )
    ctx.logger.info('Started update of deployment %s: %s',
                    ctx.deployment.id, deployment_update.id)
