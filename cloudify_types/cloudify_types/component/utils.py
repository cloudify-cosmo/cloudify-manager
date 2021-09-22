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
import json
import shutil
import zipfile
import tempfile
from shutil import copy

import yaml
import requests

from cloudify import ctx
from cloudify._compat import urlparse
from cloudify.exceptions import NonRecoverableError

from cloudify_types.utils import get_deployment_by_id

from .constants import CAPABILITIES


def update_runtime_properties(_type, _key, _value):
    ctx.instance.runtime_properties[_type][_key] = _value


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


def zip_files(files_paths):
    source_folder = tempfile.mkdtemp()
    destination_zip = source_folder + '.zip'
    for path in files_paths:
        copy(path, source_folder)
    _zipping(source_folder, destination_zip, include_folder=False)
    shutil.rmtree(source_folder)
    return destination_zip


def blueprint_id_exists(client, blueprint_id):
    """
    Searching for blueprint_id in all blueprints in order to differentiate
    not finding the blueprint then other kinds of errors, like server
    failure.
    """
    blueprint = client.blueprints.list(_include=['id'], id=blueprint_id)
    return True if blueprint else False


def deployment_id_exists(client, deployment_id):
    deployment = get_deployment_by_id(client, deployment_id)
    return True if deployment else False


def should_upload_plugin(plugin_yaml_path, existing_plugins):
    with open(plugin_yaml_path, 'r') as plugin_yaml_file:
        plugin_yaml = yaml.safe_load(plugin_yaml_file)
    plugins = plugin_yaml.get('plugins')
    for plugin_info in plugins.values():
        package_name = plugin_info.get('package_name')
        package_version = str(plugin_info.get('package_version'))
        distribution = plugin_info.get('distribution')

        for plugin in existing_plugins:
            if (plugin.package_name == package_name and
                    plugin.package_version == package_version and
                    plugin.distribution == distribution):
                return False
    return True


def populate_runtime_with_wf_results(client,
                                     deployment_id,
                                     node_instance=None):
    if not node_instance:
        node_instance = ctx.instance
    ctx.logger.info('Fetching "%s" deployment capabilities..', deployment_id)

    if CAPABILITIES not in node_instance.runtime_properties:
        node_instance.runtime_properties[CAPABILITIES] = dict()

    ctx.logger.debug('Deployment ID is %s', deployment_id)
    response = client.deployments.capabilities.get(deployment_id)
    dep_capabilities = response.get(CAPABILITIES)
    node_instance.runtime_properties[CAPABILITIES] = dep_capabilities
    ctx.logger.info('Fetched capabilities:\n%s',
                    json.dumps(dep_capabilities, indent=1))
