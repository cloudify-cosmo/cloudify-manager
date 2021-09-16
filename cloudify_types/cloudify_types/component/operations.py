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

import os
import time
from cloudify import manager, ctx
from cloudify.decorators import operation
from cloudify.constants import COMPONENT
from cloudify._compat import urlparse
from cloudify.exceptions import NonRecoverableError, OperationRetry
from cloudify.deployment_dependencies import (dependency_creator_generator,
                                              create_deployment_dependency)
from cloudify_rest_client.client import CloudifyClient
from cloudify_rest_client.exceptions import (
    CloudifyClientError,
    ForbiddenWhileCancelling,
)

from cloudify_types.utils import proxy_operation

from .component import Component
from .polling import (
    poll_with_timeout,
    is_all_executions_finished,
    verify_execution_state,
    wait_for_blueprint_to_upload
)
from .constants import (
    DEPLOYMENTS_CREATE_RETRIES,
    EXECUTIONS_TIMEOUT,
    POLLING_INTERVAL,
    EXTERNAL_RESOURCE
)
from .utils import (
    blueprint_id_exists,
    deployment_id_exists,
    update_runtime_properties,
    get_local_path,
    zip_files,
    should_upload_plugin,
    populate_runtime_with_wf_results
)


def _is_valid_url(candidate):
    parse_url = urlparse(candidate)
    return not (parse_url.netloc and parse_url.scheme)


def _get_desired_operation_input(key, args):
    """ Resolving a key's value from kwargs or
    runtime properties, node properties in the order of priority.
    """
    return (args.get(key) or
            ctx.instance.runtime_properties.get(key) or
            ctx.node.properties.get(key))


def _get_client(kwargs):
    client_config = _get_desired_operation_input('client', kwargs)
    if client_config:
        return CloudifyClient(**client_config)
    else:
        return manager.get_rest_client()


@operation(resumable=True)
def upload_blueprint(**kwargs):
    resource_config = _get_desired_operation_input('resource_config', kwargs)
    client = _get_client(kwargs)

    blueprint = resource_config.get('blueprint', {})
    blueprint_id = blueprint.get('id') or ctx.instance.id
    blueprint_archive = blueprint.get('blueprint_archive')
    blueprint_file_name = blueprint.get('main_file_name')

    if 'blueprint' not in ctx.instance.runtime_properties:
        ctx.instance.runtime_properties['blueprint'] = dict()

    update_runtime_properties('blueprint', 'id', blueprint_id)
    update_runtime_properties(
        'blueprint', 'blueprint_archive', blueprint_archive)
    update_runtime_properties(
        'blueprint', 'application_file_name', blueprint_file_name)

    blueprint_exists = blueprint_id_exists(client, blueprint_id)

    if blueprint.get(EXTERNAL_RESOURCE) and not blueprint_exists:
        raise NonRecoverableError(
            'Blueprint ID \"{0}\" does not exist, '
            'but {1} is {2}.'.format(
                blueprint_id,
                EXTERNAL_RESOURCE,
                blueprint.get(EXTERNAL_RESOURCE)))
    elif blueprint.get(EXTERNAL_RESOURCE) and blueprint_exists:
        ctx.logger.info("Using external blueprint.")
        return True
    elif blueprint_exists:
        ctx.logger.info(
            'Blueprint ID "{0}" exists, '
            'but {1} is {2}, will use the existing one.'.format(
                blueprint_id,
                EXTERNAL_RESOURCE,
                blueprint.get(EXTERNAL_RESOURCE)))
        return True
    if not blueprint_archive:
        raise NonRecoverableError(
            'No blueprint_archive supplied, '
            'but {0} is False'.format(EXTERNAL_RESOURCE))

    # Check if the ``blueprint_archive`` is not a URL then we need to
    # download it and pass the binaries to the client_args
    if _is_valid_url(blueprint_archive):
        blueprint_archive = ctx.download_resource(blueprint_archive)

    try:
        client.blueprints._upload(
            blueprint_id=blueprint_id,
            archive_location=blueprint_archive,
            application_file_name=blueprint_file_name)
        wait_for_blueprint_to_upload(blueprint_id, client)
    except CloudifyClientError as ex:
        if 'already exists' not in str(ex):
            raise NonRecoverableError(
                'Client action "_upload" failed: {0}.'.format(ex))
    return True


def _verify_secrets_clash(client, secrets):
    existing_secrets = {
        secret.key: secret.value for secret in client.secrets.list()
    }

    duplicate_secrets = set(secrets).intersection(existing_secrets)

    if duplicate_secrets:
        raise NonRecoverableError('The secrets: {0} already exist, '
                                  'not updating...'.format(
                                    '"' + '", "'.join(duplicate_secrets)
                                    + '"'))


def _set_secrets(client, secrets):
    if not secrets:
        return

    _verify_secrets_clash(client, secrets)

    for secret_name in secrets:
        client.secrets.create(
            key=secret_name,
            value=u'{0}'.format(secrets[secret_name]),
        )
        ctx.logger.info('Created secret {}'.format(repr(secret_name)))



def _upload_plugins(client, plugins):
    if (not plugins or 'plugins' in ctx.instance.runtime_properties):
        # No plugins to install or already uploaded them.
        return

    ctx.instance.runtime_properties['plugins'] = []
    existing_plugins = client.plugins.list()

    for plugin_name, plugin in plugins.items():
        zip_list = []
        zip_path = None
        try:
            if (not plugin.get('wagon_path') or
                    not plugin.get('plugin_yaml_path')):
                raise NonRecoverableError(
                    'You should provide both values wagon_path: {}'
                    ' and plugin_yaml_path: {}'
                    .format(repr(plugin.get('wagon_path')),
                            repr(plugin.get('plugin_yaml_path'))))
            wagon_path = get_local_path(plugin['wagon_path'],
                                        create_temp=True)
            yaml_path = get_local_path(plugin['plugin_yaml_path'],
                                       create_temp=True)
            zip_list = [wagon_path, yaml_path]
            if 'icon_png_path' in plugin:
                icon_path = get_local_path(plugin['icon_png_path'],
                                           create_temp=True)
                zip_list.append(icon_path)
            if not should_upload_plugin(yaml_path, existing_plugins):
                ctx.logger.warning('Plugin "{0}" was already '
                                   'uploaded...'.format(plugin_name))
                continue

            ctx.logger.info('Creating plugin "{0}" zip '
                            'archive...'.format(plugin_name))
            zip_path = zip_files(zip_list)

            # upload plugin
            plugin = client.plugins.upload(plugin_path=zip_path)
            ctx.instance.runtime_properties['plugins'].append(
                plugin.id)
            ctx.logger.info('Uploaded {}'.format(repr(plugin.id)))
        finally:
            for f in zip_list:
                os.remove(f)
            if zip_path:
                os.remove(zip_path)


def _generate_suffix_deployment_id(client, deployment_id):
    dep_exists = True
    suffix_index = ctx.instance.runtime_properties['deployment'].get(
        'current_suffix_index', 0)

    while dep_exists:
        suffix_index += 1
        inc_deployment_id = '{0}-{1}'.format(deployment_id, suffix_index)
        dep_exists = deployment_id_exists(client, inc_deployment_id)

    update_runtime_properties('deployment',
                              'current_suffix_index',
                              suffix_index)
    return inc_deployment_id


@operation(resumable=True)
def create(timeout=EXECUTIONS_TIMEOUT, interval=POLLING_INTERVAL,
           **kwargs):
    client = _get_client(kwargs)
    secrets = _get_desired_operation_input('secrets', kwargs)
    _set_secrets(client, secrets)
    plugins = _get_desired_operation_input('plugins', kwargs)
    _upload_plugins(client, plugins)

    if 'deployment' not in ctx.instance.runtime_properties:
        ctx.instance.runtime_properties['deployment'] = dict()

    config = _get_desired_operation_input('resource_config', kwargs)

    runtime_deployment_prop = ctx.instance.runtime_properties.get(
            'deployment', {})
    runtime_deployment_id = runtime_deployment_prop.get('id')

    deployment = config.get('deployment', {})
    deployment_id = (runtime_deployment_id or
                     deployment.get('id') or
                     ctx.instance.id)
    deployment_inputs = deployment.get('inputs', {})
    deployment_capabilities = deployment.get('capabilities')
    deployment_log_redirect = deployment.get('logs', True)
    deployment_auto_suffix = deployment.get('auto_inc_suffix', False)

    blueprint = config.get('blueprint', {})
    blueprint_id = blueprint.get('id') or ctx.instance.id

    _inter_deployment_dependency = create_deployment_dependency(
        dependency_creator_generator(COMPONENT, ctx.instance.id),
        ctx.deployment.id)

    if deployment_auto_suffix:
        base_deployment_id = deployment_id
    elif deployment_id_exists(client, deployment_id):
        raise NonRecoverableError(
            'Component\'s deployment ID "{0}" already exists, '
            'please verify the chosen name.'.format(
                deployment_id))

    retries = DEPLOYMENTS_CREATE_RETRIES
    while True:
        if deployment_auto_suffix:
            deployment_id = _generate_suffix_deployment_id(
                client, base_deployment_id)
        _inter_deployment_dependency['target_deployment'] = \
            deployment_id

        update_runtime_properties('deployment', 'id', deployment_id)
        ctx.logger.info('Creating "{0}" component deployment.'
                        .format(deployment_id))
        try:
            client.deployments.create(
                blueprint_id=blueprint_id,
                deployment_id=deployment_id,
                inputs=deployment_inputs
            )
            break
        except CloudifyClientError as ex:
            if ex.error_code == 'conflict_error' \
                    and deployment_auto_suffix and retries > 0:
                ctx.logger.info(
                    f'Component\'s deployment ID "{deployment_id}" '
                    'already exists, will try to automatically create an '
                    'ID with a new suffix.')
                retries -= 1
            else:
                raise ex

    client.inter_deployment_dependencies.create(**_inter_deployment_dependency)

    executions = client.executions.list(
        deployment_id=deployment_id,
        _include=['workflow_id', 'id']
    )

    # Retrieve the ``execution_id`` associated with the current deployment
    execution_id = [execution.get('id') for execution in executions
                    if (execution.get('workflow_id') ==
                        'create_deployment_environment')]

    # If the ``execution_id`` cannot be found raise error
    if not execution_id:
        raise NonRecoverableError(
            'No execution Found for component "{}"'
            ' deployment'.format(deployment_id)
        )

    # If a match was found there can only be one, so we will extract it.
    execution_id = execution_id[0]
    ctx.logger.info('Found execution id "{0}" for deployment id "{1}"'
                    .format(execution_id,
                            deployment_id))
    return verify_execution_state(client,
                                  execution_id,
                                  deployment_id,
                                  deployment_log_redirect,
                                  kwargs.get('workflow_state', 'terminated'),
                                  timeout,
                                  interval)


def _try_to_remove_plugin(client, plugin_id):
    try:
        client.plugins.delete(plugin_id=plugin_id)
    except CloudifyClientError as ex:
        if 'currently in use in blueprints' in str(ex):
            ctx.logger.warning('Could not remove plugin "{0}", it '
                               'is currently in use...'.format(plugin_id))
        else:
            raise NonRecoverableError('Failed to remove plugin '
                                      '"{0}"....'.format(plugin_id))


def _delete_plugins(client):
    plugins = ctx.instance.runtime_properties.get('plugins', [])

    for plugin_id in plugins:
        _try_to_remove_plugin(client, plugin_id)
        ctx.logger.info('Removed plugin "{0}".'.format(plugin_id))


def _delete_secrets(client, secrets):
    if not secrets:
        return

    for secret_name in secrets:
        client.secrets.delete(key=secret_name)
        ctx.logger.info('Removed secret "{}"'.format(repr(secret_name)))


def _delete_runtime_properties():
    for property_name in ['deployment', 'blueprint', 'plugins']:
        if property_name in ctx.instance.runtime_properties:
            del ctx.instance.runtime_properties[property_name]


@operation(resumable=True)
def delete(timeout=EXECUTIONS_TIMEOUT, **kwargs):
    client = _get_client(kwargs)
    ctx.logger.info("Wait for component's stop deployment operation "
                    "related executions.")
    config = _get_desired_operation_input('resource_config', kwargs)
    runtime_deployment_prop = ctx.instance.runtime_properties.get(
            'deployment', {})
    runtime_deployment_id = runtime_deployment_prop.get('id')

    deployment = config.get('deployment', {})
    deployment_id = (runtime_deployment_id or
                     deployment.get('id') or
                     ctx.instance.id)
    blueprint = config.get('blueprint', {})
    blueprint_id = blueprint.get('id') or ctx.instance.id

    _inter_deployment_dependency = create_deployment_dependency(
        dependency_creator_generator(COMPONENT, ctx.instance.id),
        ctx.deployment.id)

    poll_with_timeout(
        lambda:
        is_all_executions_finished(client, deployment_id),
        timeout=timeout,
        expected_result=True)

    ctx.logger.info('Delete component\'s "{0}" deployment'
                    .format(deployment_id))

    poll_result = True
    if not deployment_id_exists(client, deployment_id):
        # Could happen in case that deployment failed to install
        ctx.logger.warning('Didn\'t find component\'s "{0}" deployment,'
                           'so nothing to do and moving on.'
                           .format(deployment_id))
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
        ctx.logger.info('Delete component\'s blueprint "{0}".'
                        .format(blueprint_id))
        client.blueprints.delete(blueprint_id=blueprint_id)

    ctx.logger.info('Removing inter-deployment dependency between this '
                    'deployment ("{0}") and "{1}" the Component\'s '
                    'creator deployment...'.format(deployment_id,
                                                   ctx.deployment.id))
    _inter_deployment_dependency['target_deployment'] = \
        deployment_id
    _inter_deployment_dependency['is_component_deletion'] = True
    client.inter_deployment_dependencies.delete(**_inter_deployment_dependency)

    _delete_plugins(client)
    _delete_secrets(client, _get_desired_operation_input('secrets', kwargs))
    _delete_runtime_properties()

    return poll_result


@operation(resumable=True)
def execute_start(timeout=EXECUTIONS_TIMEOUT, interval=POLLING_INTERVAL,
                  **kwargs):
    client = _get_client(kwargs)
    config = _get_desired_operation_input('resource_config', kwargs)

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

    ctx.logger.info('Starting execution for "{0}" deployment'.format(
        deployment_id))
    execution = client.executions.start(**request_args)

    ctx.logger.debug('Execution start response: "{0}".'.format(execution))

    execution_id = execution['id']
    if not verify_execution_state(
            client,
            execution_id,
            deployment_id,
            deployment_log_redirect,
            kwargs.get('workflow_state', 'terminated'),
            timeout,
            interval):
        ctx.logger.error('Execution {0} failed for "{1}" '
                         'deployment'.format(execution_id,
                                             deployment_id))

    ctx.logger.info('Execution succeeded for "{0}" deployment'.format(
        deployment_id))
    populate_runtime_with_wf_results(client, deployment_id)
    return True
