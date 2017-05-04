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
import tarfile
from os import path
from contextlib import contextmanager

from cloudify.utils import setup_logger
from cloudify_rest_client.executions import Execution
from cloudify_rest_client.exceptions import CloudifyClientError
from integration_tests.framework import utils, postgresql, docl


logger = setup_logger('testenv.utils')


def get_cfy():
    return utils.get_cfy()


def upload_mock_plugin(package_name, package_version):
    client = create_rest_client()
    temp_file_path = utils._create_mock_wagon(
            package_name,
            package_version)
    response = client.plugins.upload(temp_file_path)
    os.remove(temp_file_path)
    return response


def publish_event(queue, routing_key, event):
    exchange_name = 'cloudify-monitoring'
    exchange_type = 'topic'
    connection = utils.create_pika_connection()
    channel = connection.channel()
    try:
        channel.exchange_declare(exchange=exchange_name,
                                 type=exchange_type,
                                 durable=False,
                                 auto_delete=True,
                                 internal=False)
        channel.queue_declare(
                queue=queue,
                auto_delete=True,
                durable=False,
                exclusive=False)
        channel.queue_bind(exchange=exchange_name,
                           queue=queue,
                           routing_key=routing_key)
        channel.basic_publish(exchange=exchange_name,
                              routing_key=routing_key,
                              body=json.dumps(event))
    finally:
        channel.close()
        connection.close()


def create_rest_client(**kwargs):
    return utils.create_rest_client(**kwargs)


def wait_for_deployment_creation_to_complete(
        deployment_id, timeout_seconds=60):
    do_retries(func=verify_deployment_environment_creation_complete,
               timeout_seconds=timeout_seconds,
               deployment_id=deployment_id)


def verify_deployment_environment_creation_complete(deployment_id):
    # a workaround for waiting for the deployment environment creation to
    # complete
    client = create_rest_client()
    execs = client.executions.list(deployment_id)
    if not execs \
            or execs[0].status != Execution.TERMINATED \
            or execs[0].workflow_id != 'create_deployment_environment':
        log_path = ('/var/log/cloudify/mgmtworker/'
                    'cloudify.management_worker.log')
        logs = docl.execute('tail -n 100 {0}'.format(log_path))
        raise RuntimeError(
                "Expected a single execution for workflow "
                "'create_deployment_environment' with status 'terminated'; "
                "Found these executions instead: {0}.\nLast 100 lines for "
                "management worker log:\n{1}".format(
                        json.dumps(execs.items, indent=2), logs))


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
            time.sleep(1)


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


def delete_provider_context():
    postgresql.run_query('DELETE from provider_context')


def delete_snapshot_if_existing(snapshot_id):
    client = create_rest_client()

    try:
        client.snapshots.delete(snapshot_id)
    except CloudifyClientError as err:
        if 'not found' in str(err):
            pass
        else:
            raise


def upload_snapshot(path_to_snapshot, snapshot_id):
    client = create_rest_client()

    client.snapshots.upload(path_to_snapshot, snapshot_id)


def restore_snapshot(snapshot_id, tenant):
    client = create_rest_client()

    return client.snapshots.restore(
        snapshot_id,
        tenant_name=tenant,
        force=True,
    )


def upload_and_restore_snapshot(path_to_snapshot, snapshot_id, tenant):
    # TODO: Add getter from s3 once we reach that point

    # This and the force setting allow multiple tests to run on the same
    # container (the default for agentless tests)
    delete_snapshot_if_existing(snapshot_id)

    upload_snapshot(path_to_snapshot, snapshot_id)

    validate_snapshot(snapshot_id, path_to_snapshot)

    execution = restore_snapshot(snapshot_id, tenant)

    # If checking the workflow status immediately, we will be likely to cause
    # a deadlock on the database and make the restore fail
    # This may be possible to do using the cfy utility, but I've not managed
    # to be fast enough with it to trigger the issue.
    # NOTE: Jira should be opened for this
    time.sleep(3)
    wait_for_execution_to_end(
        execution,
        timeout_seconds=30,
        tolerate_client_errors=True,
    )


def validate_snapshot(snapshot_id, original_path):
    client = create_rest_client()

    snapshot = client.snapshots.get(snapshot_id)
    assert snapshot['status'] == 'uploaded', (
        'Snapshot from {path} did not upload correctly.'.format(
            path=original_path,
        )
    )


def wait_for_execution_to_end(execution,
                              timeout_seconds=240,
                              tolerate_client_errors=False):
    client = create_rest_client()
    deadline = time.time() + timeout_seconds
    while execution.status not in Execution.END_STATES:
        time.sleep(0.5)
        try:
            execution = client.executions.get(execution.id)
        except CloudifyClientError:
            if tolerate_client_errors:
                pass
            else:
                raise
        if time.time() > deadline:
            raise utils.TimeoutException(
                    'Execution timed out: \n{0}'
                    .format(json.dumps(execution, indent=2)))
    if execution.status == Execution.FAILED:
        raise RuntimeError(
                'Workflow execution failed: {0} [{1}]'.format(
                        execution.error,
                        execution.status))
    return execution
