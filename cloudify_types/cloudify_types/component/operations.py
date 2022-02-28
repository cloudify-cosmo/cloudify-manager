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
from cloudify.exceptions import NonRecoverableError
from cloudify.deployment_dependencies import (dependency_creator_generator,
                                              create_deployment_dependency)
from cloudify_rest_client.client import CloudifyClient
from cloudify_rest_client.exceptions import CloudifyClientError

from cloudify_types.utils import errors_nonrecoverable

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
    get_local_path,
    zip_files,
    should_upload_plugin,
    populate_runtime_with_wf_results,
    no_rerun_on_resume,
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
@errors_nonrecoverable
def upload_blueprint(**kwargs):
    resource_config = _get_desired_operation_input('resource_config', kwargs)
    client = _get_client(kwargs)

    blueprint = resource_config.get('blueprint', {})
    blueprint_id = blueprint.get('id') or ctx.instance.id
    blueprint_archive = blueprint.get('blueprint_archive')
    blueprint_file_name = blueprint.get('main_file_name')
    labels = blueprint.get('labels', [])

    if 'blueprint' not in ctx.instance.runtime_properties:
        ctx.instance.runtime_properties['blueprint'] = dict()

    ctx.instance.runtime_properties['blueprint']['id'] = blueprint_id
    ctx.instance.runtime_properties['blueprint']['blueprint_archive'] = \
        blueprint_archive
    ctx.instance.runtime_properties['blueprint']['application_file_name'] = \
        blueprint_file_name
    ctx.instance.runtime_properties['blueprint']['labels'] = \
        labels
    blueprint_exists = blueprint_id_exists(client, blueprint_id)

    if blueprint.get(EXTERNAL_RESOURCE) and not blueprint_exists:
        raise NonRecoverableError(
            f'Blueprint ID "{blueprint_id}" does not exist '
            f'on tenant "{ctx.tenant_name}", but {EXTERNAL_RESOURCE} '
            f'is {blueprint.get(EXTERNAL_RESOURCE)}.'
        )
    elif blueprint.get(EXTERNAL_RESOURCE) and blueprint_exists:
        ctx.logger.info("Using external blueprint.")
        return True
    elif blueprint_exists:
        ctx.logger.info(
            'Blueprint "%s" exists, but %s is %s, will use the existing one.',
            blueprint_id, EXTERNAL_RESOURCE, blueprint.get(EXTERNAL_RESOURCE))
        return True
    if not blueprint_archive:
        raise NonRecoverableError(
            f'No blueprint_archive supplied, but {EXTERNAL_RESOURCE} is False')
    if not validate_labels(labels):
        raise NonRecoverableError(
            "The provided labels are not valid. "
            "Labels must be a list of single-entry dicts, "
            "e.g. [{\'foo\': \'bar\'}]. "
            "This value was provided: %s." % labels
        )

    # Check if the ``blueprint_archive`` is not a URL then we need to
    # download it and pass the binaries to the client_args
    if _is_valid_url(blueprint_archive):
        blueprint_archive = ctx.download_resource(blueprint_archive)

    try:
        client.blueprints._upload(
            blueprint_id=blueprint_id,
            archive_location=blueprint_archive,
            application_file_name=blueprint_file_name,
            labels=labels
        )
        wait_for_blueprint_to_upload(blueprint_id, client)
    except CloudifyClientError as ex:
        if 'already exists' not in str(ex):
            raise NonRecoverableError(
                f'Client action "_upload" failed: {ex}.')
    return True


def validate_labels(labels):
    if not isinstance(labels, list) or not all(
            isinstance(label, dict) and len(label) == 1 for label in labels):
        return False
    return True


def _abort_if_secrets_clash(client, secrets):
    """Check that new secret names aren't already in use"""
    existing_secrets = {
        secret.key: secret.value for secret in client.secrets.list()
    }

    duplicate_secrets = set(secrets).intersection(existing_secrets)

    if duplicate_secrets:
        raise NonRecoverableError(
            f'The secrets: "{ ", ".join(duplicate_secrets) }" already exist, '
            f'not updating...')


def _set_secrets(client, secrets):
    if not secrets:
        return
    _abort_if_secrets_clash(client, secrets)
    for secret_name in secrets:
        client.secrets.create(
            key=secret_name,
            value=u'{0}'.format(secrets[secret_name]),
        )
        ctx.logger.info('Created secret %r', secret_name)


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
                    f'Provide wagon_path (got { plugin.get("wagon_path") }) '
                    f'and plugin_yaml_path (got '
                    f'{ plugin.get("plugin_yaml_path") })'
                )
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
                ctx.logger.warning('Plugin "%s" was already uploaded...',
                                   plugin_name)
                continue

            ctx.logger.info('Creating plugin "%s" zip archive...', plugin_name)
            zip_path = zip_files(zip_list)

            # upload plugin
            plugin = client.plugins.upload(plugin_path=zip_path)
            ctx.instance.runtime_properties['plugins'].append(
                plugin.id)
            ctx.logger.info('Uploaded %r', plugin.id)
        finally:
            for f in zip_list:
                os.remove(f)
            if zip_path:
                os.remove(zip_path)


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
def _create_inter_deployment_dependency(client, deployment_id):
    client.inter_deployment_dependencies.create(**create_deployment_dependency(
        dependency_creator_generator(COMPONENT, ctx.instance.id),
        source_deployment=ctx.deployment.id,
        target_deployment=deployment_id
    ))


@operation(resumable=True)
@errors_nonrecoverable
def create(timeout=EXECUTIONS_TIMEOUT, interval=POLLING_INTERVAL, **kwargs):
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
    # TODO capabilities are unused?
    # deployment_capabilities = deployment.get('capabilities')
    deployment_auto_suffix = deployment.get('auto_inc_suffix', False)
    deployment_labels = deployment.get('labels', [])
    _update_labels(deployment_labels, [{'csys-obj-parent': ctx.deployment.id}])
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
        _create_inter_deployment_dependency(client, deployment_id)

    return _wait_for_deployment_create(
        client,
        deployment_id,
        deployment_log_redirect=deployment.get('logs', True),
        timeout=timeout,
        interval=interval,
        workflow_end_state=kwargs.get('workflow_state', 'terminated'),
    )


def _try_to_remove_plugin(client, plugin_id):
    try:
        client.plugins.delete(plugin_id=plugin_id)
    except CloudifyClientError as ex:
        if 'currently in use in blueprints' in str(ex):
            ctx.logger.warning('Could not remove plugin "%s", it '
                               'is currently in use...', plugin_id)
        else:
            raise NonRecoverableError(
                f'Failed to remove plugin {plugin_id}: {ex}')


def _delete_plugins(client):
    plugins = ctx.instance.runtime_properties.get('plugins', [])

    for plugin_id in plugins:
        _try_to_remove_plugin(client, plugin_id)
        ctx.logger.info('Removed plugin "%s".', plugin_id)


def _delete_secrets(client, secrets):
    if not secrets:
        return

    for secret_name in secrets:
        client.secrets.delete(key=secret_name)
        ctx.logger.info('Removed secret "%r"', secret_name)


def _delete_runtime_properties():
    for property_name in [
        'deployment', 'blueprint', 'plugins', '_component_create_idd',
        '_component_create_deployment_id',
    ]:
        if property_name in ctx.instance.runtime_properties:
            del ctx.instance.runtime_properties[property_name]


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

    _delete_plugins(client)
    _delete_secrets(client, _get_desired_operation_input('secrets', kwargs))
    _delete_runtime_properties()

    return poll_result


@operation(resumable=True)
@errors_nonrecoverable
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
    client = _get_client(kwargs)
    config = _get_desired_operation_input('resource_config', kwargs)

    runtime_deployment_prop = ctx.instance.runtime_properties.get(
            'deployment', {})
    runtime_deployment_id = runtime_deployment_prop.get('id')

    deployment = config.get('deployment', {})
    deployment_id = (runtime_deployment_id or
                     deployment.get('id') or
                     ctx.instance.id)
    populate_runtime_with_wf_results(client, deployment_id)
