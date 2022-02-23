import glob
import os
import shutil
import errno
from datetime import datetime
from functools import partial
import unicodedata

from retrying import retry

from cloudify.decorators import workflow
from cloudify.manager import get_rest_client, _get_workdir_path
from cloudify.workflows import workflow_context

from cloudify.utils import parse_utc_datetime_relative
from cloudify_rest_client.exceptions import CloudifyClientError
from dsl_parser import tasks

from . import idd
from .search_utils import get_deployments_with_rest, get_blueprints_with_rest


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


def format_plan_schedule(schedule):
    """Format a schedule from the plan form, to the REST form.

    Use this to re-format schedules from the plan, to the style accepted by
    the restservice.
    """
    base_time = datetime.utcnow()
    schedule['workflow_id'] = schedule.pop('workflow')
    if 'since' in schedule:
        schedule['since'] = _parse_plan_datetime(schedule['since'], base_time)
    if 'until' in schedule:
        schedule['until'] = _parse_plan_datetime(schedule['until'], base_time)
    if 'workflow_parameters' in schedule:
        schedule['parameters'] = schedule.pop('workflow_parameters')
    return schedule


def _create_schedules(client, deployment_id, schedules):
    for name, spec in schedules.items():
        client.execution_schedules.create(
            name,
            deployment_id=deployment_id,
            **format_plan_schedule(spec.copy())
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
        bp.plan,
        inputs=inputs,
        runtime_only_evaluation=ctx.deployment.runtime_only_evaluation,
        get_secret_method=client.secrets.get,
        get_deployments_method=partial(get_deployments_with_rest, client),
        get_blueprints_method=partial(get_blueprints_with_rest, client),
    )
    nodes = deployment_plan['nodes']
    node_instances = deployment_plan['node_instances']

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
        resource_tags=deployment_plan.get('resource_tags'),
    )

    ctx.logger.info('Creating %d nodes', len(nodes))
    client.nodes.create_many(ctx.deployment.id, nodes)
    ctx.logger.info('Creating %d node-instances', len(node_instances))
    client.node_instances.create_many(ctx.deployment.id, node_instances)

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

    idd.create(ctx, client, deployment_plan)


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
    deployment_workdir = _get_workdir_path(deployment_id, tenant)
    if os.path.exists(deployment_workdir):
        # Otherwise we experience pain on snapshot restore
        return
    os.makedirs(deployment_workdir)


def _delete_deployment_workdir(ctx):
    deployment_workdir = _get_workdir_path(ctx.deployment.id, ctx.tenant_name)
    if not os.path.exists(deployment_workdir):
        return
    try:
        shutil.rmtree(deployment_workdir)
    except os.error:
        ctx.logger.warning(
            'Failed deleting directory %s. Current directory content: %s',
            deployment_workdir, os.listdir(deployment_workdir), exc_info=True)


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
