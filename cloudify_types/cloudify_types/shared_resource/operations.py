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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from cloudify import manager, ctx
from cloudify.decorators import operation

from cloudify.constants import SHARED_RESOURCE
from cloudify.exceptions import NonRecoverableError
from cloudify_rest_client.exceptions import CloudifyClientError

from cloudify_types.utils import (errors_nonrecoverable,
                                  get_desired_operation_input,
                                  get_deployment_by_id,
                                  get_client, get_idd,
                                  capabilities_diff,
                                  validate_deployment_status)

from cloudify_types.component.utils import (
    populate_runtime_with_wf_results)
from .constants import WORKFLOW_EXECUTION_TIMEOUT
from .execute_shared_resource_workflow import (
    execute_shared_resource_workflow, execute_workflow_base)


def _mark_verified_shared_resource_node(deployment_id):
    """
    Used to mark SharedResource node that is valid after verification
    that the deployment exists, which will be used be users like
    the UI.
    """
    ctx.instance.runtime_properties['deployment'] = {'id': deployment_id}


def _checkin_resource_consumer(client, deployment_id):
    deployment = client.deployments.get(deployment_id)
    type_labels = _get_label_values(deployment.labels, 'csys-obj-type')
    if deployment.installation_status == 'inactive':
        if 'on-demand-resource' in type_labels:
            execute_workflow_base(client, 'install', deployment_id, queue=True)
        else:
            raise NonRecoverableError(
                f'SharedResource\'s deployment "{deployment_id}" is in an '
                f'inactive state and isn\'t labeled as '
                f'`csys-obj-type: on-demand-resource`. Please install the '
                f'deployment first')


def _checkout_resource_consumer(client, deployment_id):
    deployment = client.deployments.get(deployment_id)
    type_labels = _get_label_values(deployment.labels, 'csys-obj-type')
    consumers_list = _get_label_values(deployment.labels, 'csys-consumer-id')
    on_demand_uninstall = ('on-demand-resource' in type_labels and
                           'on-demand-uninstall-off' not in type_labels)
    if (on_demand_uninstall and not consumers_list and
            deployment.installation_status == 'active'):
        try:
            execute_workflow_base(client, 'uninstall', deployment_id)
        except CloudifyClientError as e:
            if e.status_code == 400:
                ctx.logger.warning(
                    'Uninstall of shared resource deployment "%s" is blocked. '
                    'Error: %s.', deployment.id, str(e), ctx.deployment.id)
            else:
                raise


def _verify_source_deployment_in_consumers(client, deployment_id):
    deployment = client.deployments.get(deployment_id)
    consumers_list = _get_label_values(deployment.labels, 'csys-consumer-id')
    if ctx.deployment.id not in consumers_list:
        ctx.logger.warning(
            'Source deployment "%s" is not a consumer of shared resource '
            'deployment "%s"!', ctx.deployment.id, deployment.id)


def _get_label_values(labels_list, key):
    values = []
    for label in labels_list:
        if label['key'] == key:
            values.append(label['value'])
    return values


@operation(resumable=True)
@errors_nonrecoverable
def connect_deployment(**kwargs):
    config = get_desired_operation_input('resource_config', kwargs)
    deployment = config.get('deployment', '')
    deployment_id = deployment.get('id', '')
    client, is_external_host = get_client(kwargs)
    _inter_deployment_dependency, _local_dependency_params = \
        get_idd(deployment_id, is_external_host, SHARED_RESOURCE, kwargs)

    ctx.logger.info('Validating that "%s" SharedResource\'s deployment '
                    'exists on tenant "%s"...', deployment_id, ctx.tenant_name)
    if is_external_host:
        manager.get_rest_client().inter_deployment_dependencies.create(
            **_local_dependency_params)

    deployment = get_deployment_by_id(client, deployment_id)
    if not deployment:
        raise NonRecoverableError(
            f'SharedResource\'s deployment ID "{deployment_id}" does '
            f'not exist on tenant "{ctx.tenant_name}", '
            f'please verify the given ID.')
    _mark_verified_shared_resource_node(deployment_id)
    populate_runtime_with_wf_results(client, deployment_id)
    _checkin_resource_consumer(client, deployment_id)
    client.inter_deployment_dependencies.create(**_inter_deployment_dependency)
    return True


@operation(resumable=True)
@errors_nonrecoverable
def disconnect_deployment(**kwargs):
    client, is_external_host = get_client(kwargs)
    config = get_desired_operation_input('resource_config', kwargs)
    deployment = config.get('deployment', '')
    deployment_id = deployment.get('id', '')
    runtime_deployment_prop = ctx.instance.runtime_properties.get(
        'deployment', {})
    runtime_deployment_id = runtime_deployment_prop.get('id')
    _inter_deployment_dependency, _local_dependency_params = \
        get_idd(deployment_id, is_external_host, SHARED_RESOURCE, kwargs)
    target_deployment = runtime_deployment_id or deployment_id
    ctx.logger.info('Removing inter-deployment dependency between this '
                    'deployment ("%s") and "%s" SharedResource\'s '
                    'deployment...', ctx.deployment.id, target_deployment)
    _inter_deployment_dependency['target_deployment'] = target_deployment

    if is_external_host:
        _local_dependency_params['target_deployment'] = ' '
        manager.get_rest_client().inter_deployment_dependencies.delete(
            **_local_dependency_params)

    _verify_source_deployment_in_consumers(client, deployment_id)
    client.inter_deployment_dependencies.delete(**_inter_deployment_dependency)
    _checkout_resource_consumer(client, deployment_id)
    return True


@operation(resumable=True)
@errors_nonrecoverable
def execute_workflow(workflow_id,
                     parameters,
                     timeout=WORKFLOW_EXECUTION_TIMEOUT,
                     redirect_logs=True,
                     **_):
    return execute_shared_resource_workflow(workflow_id,
                                            parameters,
                                            timeout,
                                            redirect_logs)


@operation(resumable=True)
@errors_nonrecoverable
def refresh(**kwargs):
    config = get_desired_operation_input('resource_config', kwargs)
    deployment = config.get('deployment', '')
    deployment_id = deployment.get('id', '')
    client, _ = get_client(kwargs)
    populate_runtime_with_wf_results(client, deployment_id)


@operation(resumable=True)
def check_drift(**kwargs):
    # Discover the drift by comparing the capabilities of a deployment to the
    # runtime properties / capabilities of a node_instance
    config = get_desired_operation_input('resource_config', kwargs)
    deployment_id = config.get('deployment', {}).get('id')
    client, _ = get_client(kwargs)
    deployment_capabilities = client.deployments.capabilities\
        .get(deployment_id)\
        .get('capabilities')
    node_instance_capabilities = client.node_instances\
        .get(kwargs['ctx'].instance.id, _include=['id', 'runtime_properties'])\
        .get('runtime_properties', {})\
        .get('capabilities')

    modified_keys = list(capabilities_diff(
        deployment_capabilities,
        node_instance_capabilities
    ))
    return {'capabilities': modified_keys} if modified_keys else None


@operation(resumable=True)
def check_status(**kwargs):
    """Discover status of a deployment basing on its different attributes."""
    config = get_desired_operation_input('resource_config', kwargs)
    deployment_id = config.get('deployment', {}).get('id')
    client, _ = get_client(kwargs)
    deployment = client.deployments.get(deployment_id)
    validate_deployment_status(deployment)
