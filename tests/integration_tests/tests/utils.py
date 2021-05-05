#########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sh
import json
import time
import wagon
import socket
import shutil
import tarfile
import tempfile

from os import path
from contextlib import contextmanager
from datetime import datetime, timedelta

from cloudify.utils import setup_logger
from cloudify.models_states import BlueprintUploadState
from cloudify_rest_client.executions import Execution
from integration_tests.framework import utils, docker
from integration_tests.framework.constants import ADMIN_TOKEN_SCRIPT

logger = setup_logger('testenv.utils')


def upload_mock_plugin(client,
                       package_name,
                       package_version,
                       corrupt_plugin=False):
    temp_file_path = _create_mock_wagon(package_name, package_version)

    if corrupt_plugin:
        _corrupt_plugin(temp_file_path, package_name)

    try:
        # Path relative to resources folder
        yaml_path = get_resource(path.join('plugins',
                                           package_name,
                                           'plugin.yaml'))
    except RuntimeError:
        # Default to the script-plugin if package-name has no plugin.yaml
        yaml_path = get_resource('plugins/plugin.yaml')

    with utils.zip_files([temp_file_path, yaml_path]) as zip_path:
        response = client.plugins.upload(zip_path)

    os.remove(temp_file_path)
    return response


def _corrupt_plugin(wagon_archive, package_name):
    temp_dir = tempfile.mkdtemp()
    utils.unzip(wagon_archive, temp_dir)
    shutil.rmtree(os.path.join(temp_dir, package_name, 'wheels'))
    utils.create_zip(os.path.join(temp_dir, '.'), wagon_archive)
    shutil.rmtree(temp_dir)


def _create_mock_wagon(package_name, package_version):
    module_src = tempfile.mkdtemp(prefix='plugin-{0}-'.format(package_name))
    try:
        # Check whether setup.py exists in plugins path
        get_resource(path.join('plugins', package_name, 'setup.py'))
    except RuntimeError:
        try:
            with open(path.join(module_src, 'setup.py'), 'w') as f:
                f.write('from setuptools import setup\n')
                f.write('setup(name="{0}", version={1})'.format(
                    package_name, package_version))
            result = wagon.create(
                module_src,
                archive_destination_dir=tempfile.gettempdir(),
                force=True,
            )
        finally:
            shutil.rmtree(module_src)
        return result

    return wagon.create(
        get_resource(path.join('plugins', package_name)),
        archive_destination_dir=tempfile.gettempdir(),
        force=True,
    )


def create_rest_client(**kwargs):
    return utils.create_rest_client(**kwargs)


def wait_for_deployment_creation_to_complete(
        container_id, deployment_id, client, timeout_seconds=120):
    do_retries(func=verify_deployment_env_created,
               exception_class=Exception,
               timeout_seconds=timeout_seconds,
               container_id=container_id,
               deployment_id=deployment_id, client=client)


def verify_deployment_env_created(container_id, deployment_id, client):
    # A workaround for waiting for the deployment environment creation to
    # complete
    client = client or create_rest_client(
        host=docker.get_manager_ip(container_id))
    execs = client.executions.list(deployment_id=deployment_id)
    if not execs \
            or execs[0].status != Execution.TERMINATED \
            or execs[0].workflow_id != 'create_deployment_environment':
        log_path = '/var/log/cloudify/mgmtworker/mgmtworker.log'
        logs = docker.execute(container_id, ['tail', '-n', '100', log_path])
        raise RuntimeError(
            "Expected a single execution for workflow "
            "'create_deployment_environment' with status 'terminated'; "
            "Found these executions instead: {0}.\nLast 100 lines for "
            "management worker log:\n{1}"
            .format(json.dumps(execs.items, indent=2), logs))


def wait_for_deployment_deletion_to_complete(
        deployment_id, client, timeout_seconds=120):
    do_retries(func=verify_deployment_delete_complete,
               timeout_seconds=timeout_seconds,
               deployment_id=deployment_id,
               client=client)


def wait_for_blueprint_upload(
        blueprint_id, client, require_success=True, timeout_seconds=30):
    func = (verify_blueprint_uploaded_successfully if require_success else
            verify_blueprint_upload_ended)
    do_retries(func=func,
               timeout_seconds=timeout_seconds,
               blueprint_id=blueprint_id,
               client=client)


def verify_deployment_delete_complete(deployment_id, client):
    deployment = client.deployments.list(id=deployment_id)
    if deployment:
        raise RuntimeError('Deployment with id {0} was not deleted yet.'
                           .format(deployment_id))


def verify_blueprint_uploaded_successfully(blueprint_id, client):
    blueprint = client.blueprints.get(blueprint_id)
    if blueprint['state'] != BlueprintUploadState.UPLOADED:
        raise RuntimeError('Blueprint with id {0} was not uploaded yet.'
                           .format(blueprint_id))


def verify_blueprint_upload_ended(blueprint_id, client):
    # blueprint_upload can finish in any end state
    blueprint = client.blueprints.get(blueprint_id)
    if blueprint['state'] not in BlueprintUploadState.END_STATES:
        raise RuntimeError('Blueprint with id {0} upload has not ended '
                           'yet.'.format(blueprint_id))


def get_resource(resource):

    """
    Gets the path for the provided resource.
    :param resource: resource name relative to /resources.
    """
    from integration_tests import resources
    resources_path = path.dirname(resources.__file__)
    resource_path = path.join(resources_path, resource)
    if not path.exists(resource_path):
        raise RuntimeError("Resource '{0}' not found in: {1}".format(
            resource, resource_path))
    return resource_path


def do_retries(func,
               timeout_seconds=10,
               exception_class=BaseException,
               **kwargs):
    deadline = time.time() + timeout_seconds
    while True:
        try:
            return func(**kwargs)
        except exception_class:
            if time.time() > deadline:
                raise
            time.sleep(0.5)


def do_retries_boolean(func, timeout_seconds=10, **kwargs):
    deadline = time.time() + timeout_seconds
    while True:
        return_value = func(**kwargs)
        if return_value:
            break
        else:
            if time.time() > deadline:
                raise RuntimeError(
                    'function {0} did not return True in {1} seconds'
                    .format(func.__name__, timeout_seconds)
                )
            time.sleep(0.5)


def create_self_signed_certificate(target_certificate_path,
                                   target_key_path,
                                   common_name):
    openssl = sh.openssl
    # Includes SAN to allow this cert to be valid for localhost (by name),
    # 127.0.0.1 (IP), and including the CN in the IP list, as some clients
    # ignore the CN when SAN is present. While this may only apply to
    # HTTPS (RFC 2818), including it here is probably best in case of SSL
    # library implementation 'fun'.
    openssl.req(
        '-x509', '-newkey', 'rsa:2048', '-sha256',
        '-keyout', target_key_path,
        '-out', target_certificate_path,
        '-days', '365', '-nodes',
        '-subj', '/CN={0}'.format(common_name))


def tar_blueprint(blueprint_path, dest_dir):
    """
    creates a tar archive out of a blueprint dir.

    :param blueprint_path: the path to the blueprint.
    :param dest_dir: destination dir for the path
    :return: the path for the dir.
    """
    blueprint_path = os.path.expanduser(blueprint_path)
    app_name = os.path.basename(os.path.splitext(blueprint_path)[0])
    blueprint_directory = os.path.dirname(blueprint_path) or os.getcwd()
    return tar_file(blueprint_directory, dest_dir, app_name)


def tar_file(file_to_tar, destination_dir, tar_name=''):
    """
    tar a file into a destination dir.
    :param file_to_tar:
    :param destination_dir:
    :param tar_name: optional tar name.
    :return:
    """
    tar_name = tar_name or os.path.basename(file_to_tar)
    tar_path = os.path.join(destination_dir, '{0}.tar.gz'.format(tar_name))
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(file_to_tar, arcname=tar_name)
    return tar_path


@contextmanager
def patch_yaml(yaml_path, is_json=False, default_flow_style=True):
    with utils.YamlPatcher(yaml_path,
                           is_json=is_json,
                           default_flow_style=default_flow_style) as patch:
        yield patch


def run_postgresql_command(container_id, cmd):
    return docker.execute(
        container_id,
        'sudo -u postgres psql cloudify_db -c "{0}"'.format(cmd)
    )


def generate_scheduled_for_date():
    now = datetime.utcnow()
    # Schedule the execution for 1 minute in the future
    scheduled_for = now + timedelta(minutes=1)
    return scheduled_for.strftime('%Y%m%d%H%M+0000')


def create_tenants_and_add_users(client, num_of_tenants):
    for i in range(num_of_tenants):
        tenant_name = 'tenant_{0}'.format(i)
        username = 'user_{0}'.format(i)
        client.tenants.create(tenant_name)
        client.users.create(username, 'password', role='default')
        client.tenants.add_user(username, tenant_name, role='manager')


def wait_for_rest(obj, timeout_sec):
    end = time.time() + timeout_sec
    while not time.time() > end:
        docker_host = obj.get_docker_host()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        p_open = sock.connect_ex((docker_host, 80)) == 0
        if p_open:
            return True
    return False


def assert_messages_in_log(container_id, workdir, messages, log_path):
    tmp_log_path = str(workdir / 'test_log')
    docker.copy_file_from_manager(container_id, log_path, tmp_log_path)
    with open(tmp_log_path) as f:
        data = f.readlines()
    for message in messages:
        assert message in str(data)
