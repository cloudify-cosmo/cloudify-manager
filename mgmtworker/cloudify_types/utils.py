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
import sys
import json
import shutil
import zipfile
import tempfile
import functools
from shutil import copy
from urllib.parse import urlparse

import yaml
import requests

from cloudify import manager, ctx
from cloudify.utils import exception_to_error_cause
from cloudify_rest_client.client import CloudifyClient
from cloudify_rest_client.exceptions import (CloudifyClientError,
                                             ForbiddenWhileCancelling)
from cloudify.exceptions import NonRecoverableError, OperationRetry
from cloudify.deployment_dependencies import (format_dependency_creator,
                                              build_deployment_dependency)
from cloudify.models_states import DeploymentState, ExecutionState

from cloudify_types.constants import EXTERNAL_RESOURCE
from cloudify_types.polling import wait_for_blueprint_to_upload


def generate_traceback_exception():
    _, exc_value, exc_traceback = sys.exc_info()
    response = exception_to_error_cause(exc_value, exc_traceback)
    return response


def errors_nonrecoverable(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ForbiddenWhileCancelling:
            raise OperationRetry()
        except Exception as ex:
            response = generate_traceback_exception()

            ctx.logger.error(
                'Error traceback %s with message %s',
                response['traceback'], response['message'])

            raise NonRecoverableError(f'Error in {f.__name__}: {ex}')
    return wrapper


def get_deployment_by_id(client, deployment_id):
    """
    Searching for deployment_id in all deployments in order to differentiate
    not finding the deployment then other kinds of errors, like server
    failure.
    """
    deployments = client.deployments.list(_include=['id'], id=deployment_id)
    return deployments[0] if deployments else None


def get_desired_operation_input(key, args):
    """ Resolving a key's value from kwargs or
    runtime properties, node properties in the order of priority.
    """
    return (args.get(key) or
            ctx.instance.runtime_properties.get(key) or
            ctx.node.properties.get(key))


def _is_client_external(client, client_config):
    tenant = client_config.get('tenant')
    if tenant and tenant != ctx.tenant_name:
        return True

    manager_ips = set()
    for mgr in manager.get_rest_client().manager.get_managers():
        manager_ips |= {mgr.private_ip, mgr.public_ip}
    internal_hosts = {'127.0.0.1', 'localhost'} | manager_ips
    host = {client.host} if isinstance(client.host, str) else set(client.host)
    is_internal = host & internal_hosts
    if is_internal and (host - internal_hosts):
        ctx.logger.warning(
            'Only partial match between the destination client host and '
            'the local manager: the following IPs are external: %s. '
            'Treating as local client.', list(host - internal_hosts))
    return not is_internal


def get_client(kwargs):
    client_config = get_desired_operation_input('client', kwargs)
    if client_config:
        client = CloudifyClient(**client_config)
        is_external_host = _is_client_external(client, client_config)
    else:
        client = manager.get_rest_client()
        is_external_host = False
    return client, is_external_host


def get_idd(deployment_id, is_external_host, dependency_type, kwargs):
    inter_deployment_dependency = build_deployment_dependency(
        format_dependency_creator(dependency_type, ctx.instance.id),
        source_deployment=ctx.deployment.id,
        target_deployment=deployment_id
    )
    local_dependency = None
    if is_external_host:
        client_config = get_desired_operation_input('client', kwargs)
        manager_ips = set()
        for mgr in manager.get_rest_client().manager.get_managers():
            manager_ips |= {mgr.public_ip}
        local_dependency = build_deployment_dependency(
            format_dependency_creator(dependency_type, ctx.instance.id),
            source_deployment=ctx.deployment.id,
            external_target={
                'deployment': deployment_id,
                'client_config': client_config
            },
        )
        inter_deployment_dependency['external_source'] = {
            'deployment': ctx.deployment.id,
            'tenant': ctx.tenant_name,
            'host': list(manager_ips)
        }
    return inter_deployment_dependency, local_dependency


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


def _delete_runtime_properties(property_list):
    for property_name in property_list:
        if property_name in ctx.instance.runtime_properties:
            del ctx.instance.runtime_properties[property_name]


def delete_plugins_secrets_and_runtime(client, secrets, property_list):
    _delete_plugins(client)
    _delete_secrets(client, secrets)
    _delete_runtime_properties(property_list)


def upload_secrets_and_plugins(client, kwargs):
    secrets = get_desired_operation_input('secrets', kwargs)
    _set_secrets(client, secrets)
    plugins = get_desired_operation_input('plugins', kwargs)
    _upload_plugins(client, plugins)


def _is_internal_path(candidate):
    parse_url = urlparse(candidate)
    return not (parse_url.netloc and parse_url.scheme)


def do_upload_blueprint(client, blueprint):
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

    # If the ``blueprint_archive`` is not a URL then we need to download
    # it from within the main blueprint in the file-server and pass the
    # binaries to the client_args
    is_directory = False
    if _is_internal_path(blueprint_archive):
        res = ctx.get_resource(blueprint_archive)
        try:
            res_dict = json.loads(res)
            if isinstance(res_dict, dict):
                is_directory = True
        except ValueError:
            # The downloaded blueprint isn't a json (it might be a zip!)
            # Either json.loads failed, or unicode decode failed.
            pass
        if is_directory:
            blueprint_archive = ctx.download_directory(blueprint_archive)
        else:
            blueprint_archive = ctx.download_resource(blueprint_archive)

    try:
        if is_directory:
            client.blueprints.upload(
                entity_id=blueprint_id,
                path=os.path.join(blueprint_archive, blueprint_file_name),
                labels=labels,
                skip_size_limit=True,
                async_upload=True,
            )
        else:
            client.blueprints._upload(
                blueprint_id=blueprint_id,
                archive_location=blueprint_archive,
                application_file_name=blueprint_file_name,
                labels=labels,
                async_upload=True,
            )
        wait_for_blueprint_to_upload(blueprint_id, client)
    except CloudifyClientError as ex:
        if 'already exists' not in str(ex):
            raise NonRecoverableError(
                f'Client action "_upload" failed: {ex}.')
    return True


def blueprint_id_exists(client, blueprint_id):
    """
    Searching for blueprint_id in all blueprints in order to differentiate
    not finding the blueprint then other kinds of errors, like server
    failure.
    """
    blueprint = client.blueprints.list(_include=['id'], id=blueprint_id)
    return True if blueprint else False


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


def validate_labels(labels):
    if not isinstance(labels, list) or not all(
            isinstance(label, dict) and len(label) == 1 for label in labels):
        return False
    return True


def should_upload_plugin(plugin_yaml_path, existing_plugins):
    with open(plugin_yaml_path, 'r') as plugin_yaml_file:
        plugin_yaml = yaml.safe_load(plugin_yaml_file)
    plugins = plugin_yaml.get('plugins')
    for plugin_info in plugins.values():
        package_name = plugin_info.get('package_name')
        package_version = str(plugin_info.get('package_version'))

        for plugin in existing_plugins:
            if (plugin.package_name == package_name and
                    plugin.package_version == package_version):
                return False
    return True


def zip_files(files_paths):
    source_folder = tempfile.mkdtemp()
    destination_zip = source_folder + '.zip'
    for path in files_paths:
        copy(path, source_folder)
    _zipping(source_folder, destination_zip, include_folder=False)
    shutil.rmtree(source_folder)
    return destination_zip


def get_local_path(source, destination=None, create_temp=False):
    allowed_schemes = ['http', 'https']
    if urlparse(source).scheme in allowed_schemes:
        downloaded_file = download_file(source, destination, keep_name=True)
        return downloaded_file
    elif os.path.isfile(source):
        if not destination and create_temp:
            source_name = os.path.basename(source)
            destination = os.path.join(tempfile.mkdtemp(), source_name)
        if destination:
            shutil.copy(source, destination)
            return destination
        else:
            return source
    else:
        raise NonRecoverableError(
            f'Provide either a path to a local file, or a remote URL '
            f'using one of the allowed schemes: {allowed_schemes}')


def download_file(url, destination=None, keep_name=False):
    """
    :param url: Location of the file to download
    :type url: str
    :param destination:
        Location where the file should be saved (autogenerated by default)
    :param keep_name: use the filename from the url as destination filename
    :type destination: str | None
    :returns: Location where the file was saved
    :rtype: str
    """

    if not destination:
        if keep_name:
            path = urlparse(url).path
            name = os.path.basename(path)
            destination = os.path.join(tempfile.mkdtemp(), name)
        else:
            fd, destination = tempfile.mkstemp()
            os.close(fd)

    ctx.logger.info('Downloading %s to %s...', url, destination)

    try:
        response = requests.get(url, stream=True)
    except requests.exceptions.RequestException as ex:
        raise NonRecoverableError(f'Failed to download {url}. ({ex})')

    final_url = response.url
    if final_url != url:
        ctx.logger.info('Redirected to %s', final_url)

    try:
        with open(destination, 'wb') as destination_file:
            for chunk in response.iter_content(None):
                destination_file.write(chunk)
    except IOError as ex:
        raise NonRecoverableError(f'Failed to download {url}. ({ex})')

    return destination


def _zipping(source, destination, include_folder=True):
    ctx.logger.debug('Creating zip archive: %s...', destination)
    with zipfile.ZipFile(destination, 'w') as zip_file:
        for root, _, files in os.walk(source):
            for filename in files:
                file_path = os.path.join(root, filename)
                source_dir = os.path.dirname(source) if include_folder\
                    else source
                zip_file.write(
                    file_path, os.path.relpath(file_path, source_dir))
    ctx.logger.debug('Successful zip archive creation')
    return destination


def dict_sum_diff(a, b):
    a_dict = a if isinstance(a, dict) else {}
    b_dict = b if isinstance(b, dict) else {}
    for k in a_dict.keys() | b_dict.keys():
        if a_dict.get(k) != b_dict.get(k):
            yield k


def current_deployment_id(**kwargs):
    config = get_desired_operation_input('resource_config', kwargs)
    runtime_deployment_prop = ctx.instance.runtime_properties.get(
        'deployment', {})
    runtime_deployment_id = runtime_deployment_prop.get('id')
    deployment = config.get('deployment', {})
    return runtime_deployment_id \
        or deployment.get('id') \
        or ctx.instance.id


def validate_deployment_status(deployment, validate_drifted=True):
    if deployment.installation_status != DeploymentState.ACTIVE:
        raise NonRecoverableError(
            f"Expected deployment '{deployment.id}' to be installed, but got "
            f"installation status: '{deployment.installation_status}'")
    if deployment.deployment_status != DeploymentState.GOOD:
        raise NonRecoverableError(
            f"Expected deployment '{deployment.id}' to be in a good state, "
            f"but got deployment status: '{deployment.deployment_status}'")
    if deployment.latest_execution_status == ExecutionState.FAILED:
        raise NonRecoverableError(
            f"The latest execution for '{deployment.id}' failed")
    if deployment.unavailable_instances > 0:
        raise NonRecoverableError(
            f"There are {deployment.unavailable_instances} unavailable "
            f"instances in deployment '{deployment.id}'")
    if validate_drifted and deployment.drifted_instances > 0:
        raise NonRecoverableError(
            f"There are {deployment.drifted_instances} drifted "
            f"instances in deployment '{deployment.id}'")
