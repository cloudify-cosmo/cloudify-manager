# Copyright (c) 2017-2019 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import time
from cloudify import manager, ctx
from cloudify.decorators import operation
from cloudify.constants import COMPONENT
from cloudify.exceptions import NonRecoverableError
from cloudify_rest_client.exceptions import CloudifyClientError

from cloudify_types.utils import (do_upload_blueprint,
                                  upload_secrets_and_plugins,
                                  delete_plugins_secrets_and_runtime,
                                  validate_labels,
                                  errors_nonrecoverable,
                                  get_desired_operation_input,
                                  get_client, get_idd,
                                  dict_sum_diff,
                                  current_deployment_id,
                                  validate_deployment_status)
from .polling import (
    poll_with_timeout,
    is_all_executions_finished,
    verify_execution_state,
)
from .constants import (
    DEPLOYMENTS_CREATE_RETRIES,
    EXECUTIONS_TIMEOUT,
    POLLING_INTERVAL,
    EXTERNAL_RESOURCE
)
from .utils import (
    deployment_id_exists,
    populate_runtime_with_wf_results,
    no_rerun_on_resume,
)


@operation(resumable=True)
@errors_nonrecoverable
def upload_blueprint(**kwargs):
    resource_config = get_desired_operation_input('resource_config', kwargs)
    client, is_external_host = get_client(kwargs)

    blueprint = resource_config.get('blueprint', {})
    do_upload_blueprint(client, blueprint)
    return True


def _create_deployment_id(base_deployment_id, auto_inc_suffix):
    if not auto_inc_suffix:
        yield base_deployment_id
    else:
        for ix in range(DEPLOYMENTS_CREATE_RETRIES):
            yield f'{base_deployment_id}-{ix}'


@no_rerun_on_resume('_component_create_deployment_id')
def _do_create_deployment(client, deployment_ids, deployment_kwargs):
    create_error = NonRecoverableError('Unknown error creating deployment')
    for deployment_id in deployment_ids:
        ctx.instance.runtime_properties['deployment']['id'] = deployment_id
        try:
            client.deployments.create(
                deployment_id=deployment_id,
                async_create=True,
                **deployment_kwargs)
            return deployment_id
        except CloudifyClientError as ex:
            create_error = ex
    raise create_error


def _wait_for_deployment_create(client, deployment_id,
                                deployment_log_redirect, timeout, interval,
                                workflow_end_state):
    """Wait for deployment's create_dep_env to finish"""
    create_execution = client.deployments.get(
        deployment_id,
        _include=['id', 'create_execution'],
    )['create_execution']
    if not create_execution:
        raise NonRecoverableError(
            f'No create execution found for deployment "{deployment_id}"')
    return verify_execution_state(client,
                                  create_execution,
                                  deployment_id,
                                  deployment_log_redirect,
                                  workflow_end_state,
                                  timeout,
                                  interval)


@no_rerun_on_resume('_component_create_idd')
def _create_inter_deployment_dependency(client, deployment_id,
                                        is_external_host, kwargs):
    _inter_deployment_dependency, _local_dependency = \
        get_idd(deployment_id, is_external_host, COMPONENT, kwargs)
    if is_external_host:
        manager.get_rest_client().inter_deployment_dependencies.create(
            **_local_dependency)
    client.inter_deployment_dependencies.create(**_inter_deployment_dependency)


@operation(resumable=True)
@errors_nonrecoverable
def create(timeout=EXECUTIONS_TIMEOUT, interval=POLLING_INTERVAL, **kwargs):
    client, is_external_host = get_client(kwargs)
    upload_secrets_and_plugins(client, kwargs)

    if 'deployment' not in ctx.instance.runtime_properties:
        ctx.instance.runtime_properties['deployment'] = dict()

    config = get_desired_operation_input('resource_config', kwargs)

    runtime_deployment_prop = ctx.instance.runtime_properties.get(
            'deployment', {})
    runtime_deployment_id = runtime_deployment_prop.get('id')

    deployment = config.get('deployment', {})
    deployment_id = (runtime_deployment_id or
                     deployment.get('id') or
                     ctx.instance.id)
    deployment_inputs = deployment.get('inputs', {})
    deployment_auto_suffix = deployment.get('auto_inc_suffix', False)
    deployment_labels = deployment.get('labels', [])
    if not is_external_host:
        _update_labels(
            deployment_labels, [{'csys-obj-parent': ctx.deployment.id}])
    if not validate_labels(deployment_labels):
        raise NonRecoverableError(
            "The provided deployment labels are not valid. "
            "Labels must be a list of single-entry dicts, "
            "e.g. [{\'foo\': \'bar\'}]. "
            "This value was provided: %s." % deployment_labels
        )

    blueprint = config.get('blueprint', {})
    blueprint_id = blueprint.get('id') or ctx.instance.id

    if not deployment.get(EXTERNAL_RESOURCE):
        deployment_id = _do_create_deployment(
            client,
            _create_deployment_id(deployment_id, deployment_auto_suffix),
            {'blueprint_id': blueprint_id,
             'inputs': deployment_inputs,
             'labels': deployment_labels},
        )
        ctx.logger.info('Creating "%s" component deployment', deployment_id)
        _create_inter_deployment_dependency(client, deployment_id,
                                            is_external_host, kwargs)

    return _wait_for_deployment_create(
        client,
        deployment_id,
        deployment_log_redirect=deployment.get('logs', True),
        timeout=timeout,
        interval=interval,
        workflow_end_state=kwargs.get('workflow_state', 'terminated'),
    )


def _update_labels(labels: list, new_labels: list):
    for new_label in new_labels:
        for key, value in new_label.items():
            found = False
            for n, label in enumerate(labels):
                if key not in label:
                    continue
                label[key] = value
                found = True
            if not found:
                labels.append({key: value})
    return labels


@operation(resumable=True)
@errors_nonrecoverable
def delete(timeout=EXECUTIONS_TIMEOUT, **kwargs):
    client, is_external_host = get_client(kwargs)
    ctx.logger.info("Wait for component's stop deployment operation "
                    "related executions.")
    config = get_desired_operation_input('resource_config', kwargs)
    runtime_deployment_prop = ctx.instance.runtime_properties.get(
            'deployment', {})
    runtime_deployment_id = runtime_deployment_prop.get('id')

    deployment = config.get('deployment', {})
    deployment_id = (runtime_deployment_id or
                     deployment.get('id') or
                     ctx.instance.id)
    blueprint = config.get('blueprint', {})
    blueprint_id = blueprint.get('id') or ctx.instance.id

    _inter_deployment_dependency, _local_dependency = \
        get_idd(deployment_id, is_external_host, COMPONENT, kwargs)

    poll_with_timeout(
        lambda: is_all_executions_finished(client, deployment_id),
        timeout=timeout,
        expected_result=True)

    ctx.logger.info('Delete component\'s "%s" deployment', deployment_id)

    poll_result = True
    if not deployment_id_exists(client, deployment_id):
        # Could happen in case that deployment failed to install
        ctx.logger.warning('Didn\'t find component\'s "%s" deployment,'
                           'so nothing to do and moving on.', deployment_id)
    else:
        client.deployments.delete(deployment_id=deployment_id)

        ctx.logger.info("Waiting for component's deployment delete.")
        poll_result = poll_with_timeout(
            lambda: deployment_id_exists(client, deployment_id),
            timeout=timeout,
            expected_result=False)

    ctx.logger.debug("Internal services cleanup.")
    time.sleep(POLLING_INTERVAL)

    ctx.logger.debug("Waiting for all system workflows to stop/finish.")
    poll_with_timeout(
        lambda: is_all_executions_finished(client),
        timeout=timeout,
        expected_result=True)

    if not blueprint.get(EXTERNAL_RESOURCE):
        ctx.logger.info('Delete component\'s blueprint "%s".', blueprint_id)
        client.blueprints.delete(blueprint_id=blueprint_id)

    ctx.logger.info('Removing inter-deployment dependency between this '
                    'deployment ("%s") and "%s" the Component\'s '
                    'creator deployment...',
                    deployment_id, ctx.deployment.id)
    _inter_deployment_dependency['target_deployment'] = \
        deployment_id
    _inter_deployment_dependency['is_component_deletion'] = True
    client.inter_deployment_dependencies.delete(**_inter_deployment_dependency)

    if is_external_host:
        _local_dependency['is_component_deletion'] = True
        manager.get_rest_client().inter_deployment_dependencies.delete(
            **_local_dependency)

    delete_plugins_secrets_and_runtime(
        client,
        get_desired_operation_input('secrets', kwargs),
        ['deployment', 'blueprint', 'plugins', '_component_create_idd',
         '_component_create_deployment_id']
    )
    return poll_result


@operation(resumable=True)
@errors_nonrecoverable
def execute_start(timeout=EXECUTIONS_TIMEOUT, interval=POLLING_INTERVAL,
                  **kwargs):
    client, _ = get_client(kwargs)
    config = get_desired_operation_input('resource_config', kwargs)

    runtime_deployment_prop = ctx.instance.runtime_properties.get(
            'deployment', {})
    runtime_deployment_id = runtime_deployment_prop.get('id')

    deployment = config.get('deployment', {})
    deployment_id = (runtime_deployment_id or
                     deployment.get('id') or
                     ctx.instance.id)
    deployment_log_redirect = deployment.get('logs', True)
    workflow_id = kwargs.get('workflow_id', 'create_deployment_environment')
    # Wait for the deployment to finish any executions
    if not poll_with_timeout(
            lambda: is_all_executions_finished(client, deployment_id),
            timeout=timeout,
            expected_result=True):
        return ctx.operation.retry(
            'The "{0}" deployment is not ready for execution.'.format(
                deployment_id))

    execution_args = config.get('executions_start_args', {})

    request_args = dict(
        deployment_id=deployment_id,
        workflow_id=workflow_id,
        **execution_args
    )
    if workflow_id == ctx.workflow_id:
        request_args.update(dict(parameters=ctx.workflow_parameters))

    ctx.logger.info('Starting execution for "%s" deployment', deployment_id)
    execution = client.executions.start(**request_args)

    ctx.logger.debug('Execution start response: "%s".', execution)

    execution_id = execution['id']
    if not verify_execution_state(
            client,
            execution_id,
            deployment_id,
            deployment_log_redirect,
            kwargs.get('workflow_state', 'terminated'),
            timeout,
            interval):
        ctx.logger.error('Execution %s failed for "%s" deployment',
                         execution_id, deployment_id)

    ctx.logger.info('Execution succeeded for "%s" deployment', deployment_id)
    populate_runtime_with_wf_results(client, deployment_id)
    return True


@operation(resumable=True)
@errors_nonrecoverable
def refresh(**kwargs):
    client, _ = get_client(kwargs)
    config = get_desired_operation_input('resource_config', kwargs)

    runtime_deployment_prop = ctx.instance.runtime_properties.get(
            'deployment', {})
    runtime_deployment_id = runtime_deployment_prop.get('id')

    deployment = config.get('deployment', {})
    deployment_id = (runtime_deployment_id or
                     deployment.get('id') or
                     ctx.instance.id)
    populate_runtime_with_wf_results(client, deployment_id)


def _diff_deployment(deployment_spec, deployment):
    """Return the names of attributes that drifted in the deployment

    :param deployment_spec: the specification of the deployment as given in
        node properties.resource_config
    :param deployment: actual deployment
    :return: list of attribute names, e.g. ["id", "labels"]
    """
    deployment_drift = []
    if not deployment_spec:
        return deployment_drift

    deployment_id = deployment.id
    if deployment_spec.get('auto_inc_suffix'):
        # if we created the deployment with auto_inc_suffix, the actual
        # deployment id is going to be `<dep_id>-<number>`, while in
        # node properties we only store the base "dep_id". Consider that
        # not drifted.
        deployment_id, _, _suffix = deployment_id.rpartition('-')

    if spec_deployment_id := deployment_spec.get('id'):
        if deployment_id != spec_deployment_id:
            deployment_drift.append('id')

    if spec_labels := {
        list(label.items())[0]
        for label in deployment_spec.get('labels', [])
        if label
    }:
        deployment_labels = deployment.labels or []
        current_labels = {
            (label['key'], label['value'])
            for label in deployment_labels
            if not label['key'].startswith('csys-')
        }
        if current_labels != spec_labels:
            deployment_drift.append('labels')

    if spec_inputs := deployment_spec.get('inputs'):
        if spec_inputs != deployment.inputs:
            deployment_drift.append('inputs')

    return deployment_drift


def _diff_blueprint(blueprint_spec, blueprint):
    """Return the names of attributes that drifted in the blueprint

    :param blueprint_spec: the specification of the blueprint as given in
        node properties.resource_config
    :param deployment: actual blueprint
    :return: list of attribute names, e.g. ["id", "labels"]
    """
    blueprint_drift = []
    if not blueprint_spec:
        return blueprint_spec

    if spec_blueprint_id := blueprint_spec.get('id'):
        if spec_blueprint_id != blueprint.id:
            blueprint_drift.append('id')

    spec_blueprint_labels = blueprint_spec.get('labels')
    if blueprint.labels and spec_blueprint_labels:
        blueprint_drift.append('labels')
    return blueprint_drift


@operation(resumable=True)
def check_drift(timeout=EXECUTIONS_TIMEOUT, **kwargs):
    deployment_id = current_deployment_id(**kwargs)
    client, _ = get_client(kwargs)
    drift = {}

    client.executions.start(
        deployment_id=deployment_id,
        workflow_id='check_drift'
    )
    poll_with_timeout(
        lambda: is_all_executions_finished(client, deployment_id),
        timeout=timeout,
        expected_result=True
    )

    node_properties = ctx.node.properties.get('resource_config')
    node_instance_runtime_properties = client.node_instances \
        .get(kwargs['ctx'].instance.id, _include=['id', 'runtime_properties'])\
        .get('runtime_properties')
    deployment = client.deployments.get(deployment_id)
    blueprint = client.blueprints.get(deployment.blueprint_id)

    # Discover different client configuration
    if get_desired_operation_input('client', kwargs):
        drift['client'] = True

    # Discover the capabilities drift
    modified_keys = list(dict_sum_diff(
        client.deployments.capabilities.get(deployment_id).get('capabilities'),
        node_instance_runtime_properties.get('capabilities'),
    ))
    if modified_keys:
        drift['capabilities'] = modified_keys

    if deployment_drift := _diff_deployment(
        node_properties.get('deployment', {}),
        deployment,
    ):
        drift['deployment'] = deployment_drift
    if blueprint_drift := _diff_blueprint(
        node_properties.get('blueprint', {}),
        blueprint,
    ):
        drift['blueprint'] = blueprint_drift

    return drift or None


@operation(resumable=True)
def check_status(timeout=EXECUTIONS_TIMEOUT, **kwargs):
    """Discover status of a deployment basing on its different attributes."""
    client, _ = get_client(kwargs)
    deployment_id = current_deployment_id(**kwargs)

    client.executions.start(
        deployment_id=deployment_id,
        workflow_id='check_status'
    )
    poll_with_timeout(
        lambda: is_all_executions_finished(client, deployment_id),
        timeout=timeout,
        expected_result=True
    )

    deployment = client.deployments.get(deployment_id)
    validate_deployment_status(deployment)


@operation
def heal(timeout=EXECUTIONS_TIMEOUT, **kwargs):
    """Run a `heal` workflow on a deployment identified by `deployment_id`"""
    client, _ = get_client(kwargs)
    deployment_id = current_deployment_id(**kwargs)

    heal_execution = client.executions.start(
        deployment_id=deployment_id,
        workflow_id='heal'
    )
    ctx.logger.info(
        'Heal of component deployment: %s, heal execution: %s',
        deployment_id, heal_execution.id
    )
    poll_with_timeout(
        lambda: is_all_executions_finished(client, deployment_id),
        timeout=timeout,
        expected_result=True
    )
    heal_execution = client.executions.get(heal_execution.id)
    ctx.logger.info(
        'Heal of component deployment: %s finished, execution status: %s',
        deployment_id, heal_execution.status
    )
    deployment = client.deployments.get(deployment_id)
    validate_deployment_status(deployment, validate_drifted=False)


@operation
def update(timeout=EXECUTIONS_TIMEOUT, **kwargs):
    """Run a `update` workflow on a deployment identified by `deployment_id`"""
    client, _ = get_client(kwargs)
    deployment_id = current_deployment_id(**kwargs)
    resource_config = ctx.node.properties.get('resource_config', {})

    drift = ctx.instance.drift
    update_kwargs = {}
    update_labels = []
    if 'client' in drift and drift['client']:
        raise NonRecoverableError(
            f'Update not available for "{deployment_id}" '
            'because of client drift'
        )
    if 'deployment' in drift and 'id' in drift['deployment']:
        raise NonRecoverableError(
            f'Update not available for "{deployment_id}" '
            'because of deployment_id change'
        )
    if 'blueprint' in drift and 'id' in drift['blueprint']:
        update_kwargs['blueprint_id'] = resource_config \
            .get('blueprint', {}) \
            .get('id')
    if 'deployment' in drift and 'inputs' in drift['deployment']:
        update_kwargs['inputs'] = resource_config \
            .get('deployment', {}) \
            .get('inputs')
    if 'deployment' in drift and 'labels' in drift['deployment']:
        update_labels = resource_config \
            .get('deployment', {}) \
            .get('labels')

    if update_kwargs:
        client.deployment_updates.update_with_existing_blueprint(
            deployment_id=deployment_id,
            **update_kwargs
        )
    if update_labels:
        deployment = client.deployments.get(deployment_id)
        deployment_labels = [
            {label['key']: label['value']} for label in deployment.labels
        ]
        deployment_labels.extend(update_labels)
        client.deployments.update_labels(deployment_id, deployment_labels)

    poll_with_timeout(
        lambda: is_all_executions_finished(client, deployment_id),
        timeout=timeout,
        expected_result=True
    )

    deployment = client.deployments.get(deployment_id)
    validate_deployment_status(deployment)
