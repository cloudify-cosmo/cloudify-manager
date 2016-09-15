#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

import json
import os
import re
import sys
import uuid
import time
import tempfile
import tarfile
import shutil
from functools import wraps
from collections import namedtuple
from multiprocessing import Process
from os import path

import influxdb
import pika
import sh
import yaml
from wagon import wagon

from cloudify_cli import env as cli_env
from cloudify_rest_client import CloudifyClient
from cloudify.utils import setup_logger
from cloudify_rest_client.executions import Execution
from manager_rest.storage.storage_manager import get_storage_manager

from integration_tests import constants

PROVIDER_CONTEXT = {
    'cloudify': {
        'workflows': {
            'task_retries': 0,
            'task_retry_interval': 0,
            'subgraph_retries': 0
        }
    }
}
PROVIDER_NAME = 'integration_tests'

logger = setup_logger('testenv.utils')


def _write(stream, s):
    try:
        s = s.encode('utf-8')
    except UnicodeDecodeError:
        pass
    stream.write(s)


def sh_bake(command):
    return command.bake(
            _out=lambda line: _write(sys.stdout, line),
            _err=lambda line: _write(sys.stderr, line))


def get_manager_ip():
    return os.environ[constants.DOCL_CONTAINER_IP]


def create_rest_client(username=None,
                       password=None,
                       token=None,
                       rest_port=None,
                       rest_protocol=None,
                       cert_path=None,
                       trust_all=None):
    rest_port = rest_port or os.environ.get(
        constants.CLOUDIFY_REST_PORT, 80)
    rest_protocol = rest_protocol or ('https' if rest_port == '443' else
                                      'http')
    if username is False:
        username = None
    elif username is None:
        username = cli_env.get_username()

    if password is False:
        password = None
    elif password is None:
        password = password or cli_env.get_password()

    headers = None
    if (username is not None and password is not None) or (token is not None):
        if token is not None:
            headers = {'Authentication-Token': token}
        else:
            credentials = '{0}:{1}'.format(username, password)
            headers = {'Authorization':
                       'Basic {0}'.format(
                           cli_env.urlsafe_b64encode(credentials))}

    if cert_path is False:
        cert_path = None
    elif cert_path is None:
        cert_path = cert_path or cli_env.get_ssl_cert()

    if trust_all is None:
        trust_all = cli_env.get_ssl_trust_all()

    return CloudifyClient(
        host=get_manager_ip(),
        port=rest_port,
        protocol=rest_protocol,
        headers=headers,
        trust_all=trust_all,
        cert=cert_path)


def get_postgres_client_details():
    details = namedtuple('PGDetails', 'db_name username password host')
    return details('cloudify_db', 'cloudify', 'cloudify', get_manager_ip())


def get_remote_storage_manager():
    """Return the SQL storage manager connected to the remote manager
    """
    import integration_tests.postgresql
    integration_tests.postgresql.setup_app()
    return get_storage_manager()


def create_influxdb_client():
    return influxdb.InfluxDBClient(get_manager_ip(), 8086,
                                   'root', 'root', 'cloudify')


def create_pika_connection():
    credentials = pika.credentials.PlainCredentials(
        username='cloudify',
        password='c10udify')
    return pika.BlockingConnection(
        pika.ConnectionParameters(host=get_manager_ip(),
                                  credentials=credentials))


def get_cfy():
    return sh.cfy.bake(_err_to_out=True,
                       _out=lambda l: sys.stdout.write(l),
                       _tee=True)


def deploy_application(dsl_path,
                       timeout_seconds=30,
                       blueprint_id=None,
                       deployment_id=None,
                       wait_for_execution=True,
                       inputs=None):
    """
    A blocking method which deploys an application from the provided dsl path.
    """
    return deploy_and_execute_workflow(dsl_path=dsl_path,
                                       workflow_name='install',
                                       timeout_seconds=timeout_seconds,
                                       blueprint_id=blueprint_id,
                                       deployment_id=deployment_id,
                                       wait_for_execution=wait_for_execution,
                                       inputs=inputs)


def deploy(dsl_path, blueprint_id=None, deployment_id=None, inputs=None):
    client = create_rest_client()
    if not blueprint_id:
        blueprint_id = str(uuid.uuid4())
    blueprint = client.blueprints.upload(dsl_path, blueprint_id)
    if deployment_id is None:
        deployment_id = str(uuid.uuid4())
    deployment = client.deployments.create(
        blueprint.id,
        deployment_id,
        inputs=inputs)

    wait_for_deployment_creation_to_complete(
        deployment_id=deployment_id)
    return deployment


def wait_for_deployment_creation_to_complete(
        deployment_id, timeout_seconds=30):
    do_retries(func=verify_deployment_environment_creation_complete,
               timeout_seconds=timeout_seconds,
               deployment_id=deployment_id)


def deploy_and_execute_workflow(dsl_path,
                                workflow_name,
                                timeout_seconds=240,
                                blueprint_id=None,
                                deployment_id=None,
                                wait_for_execution=True,
                                parameters=None,
                                inputs=None):
    """
    A blocking method which deploys an application from the provided dsl path.
    and runs the requested workflows
    """
    deployment = deploy(dsl_path, blueprint_id, deployment_id, inputs)
    execution = execute_workflow(workflow_name, deployment.id, parameters,
                                 timeout_seconds, wait_for_execution)
    return deployment, execution.id


def execute_workflow(workflow_name, deployment_id,
                     parameters=None,
                     timeout_seconds=240,
                     wait_for_execution=True):
    """
    A blocking method which runs the requested workflow
    """
    client = create_rest_client()

    execution = client.executions.start(deployment_id, workflow_name,
                                        parameters=parameters or {})

    if wait_for_execution:
        wait_for_execution_to_end(execution,
                                  timeout_seconds=timeout_seconds)

    return execution


def verify_deployment_environment_creation_complete(deployment_id):
    # a workaround for waiting for the deployment environment creation to
    # complete
    client = create_rest_client()
    execs = client.executions.list(deployment_id)
    if not execs \
            or execs[0].status != Execution.TERMINATED \
            or execs[0].workflow_id != 'create_deployment_environment':
        # cyclic imports :(
        from integration_tests import docl
        log_path = ('/var/log/cloudify/mgmtworker/'
                    'cloudify.management_worker.log')
        logs = docl.execute('tail -n 100 {0}'.format(log_path))
        raise RuntimeError(
            "Expected a single execution for workflow "
            "'create_deployment_environment' with status 'terminated'; "
            "Found these executions instead: {0}.\nLast 100 lines for "
            "management worker log:\n{1}".format(
                json.dumps(execs.items, indent=2), logs))


def undeploy_application(deployment_id,
                         timeout_seconds=240,
                         is_delete_deployment=False,
                         parameters=None):
    """
    A blocking method which undeploys an application from the provided dsl
    path.
    """
    client = create_rest_client()
    execution = client.executions.start(deployment_id,
                                        'uninstall',
                                        parameters=parameters)
    wait_for_execution_to_end(execution, timeout_seconds=timeout_seconds)

    if execution.error and execution.error != 'None':
        raise RuntimeError(
            'Workflow execution failed: {0}'.format(execution.error))
    if is_delete_deployment:
        delete_deployment(deployment_id)


def delete_deployment(deployment_id, ignore_live_nodes=False):
    client = create_rest_client()
    return client.deployments.delete(deployment_id,
                                     ignore_live_nodes=ignore_live_nodes)


def is_node_started(node_id):
    client = create_rest_client()
    node_instance = client.node_instances.get(node_id)
    return node_instance['state'] == 'started'


def get_resource(resource):

    """
    Gets the path for the provided resource.
    :param resource: resource name relative to /resources.
    """
    import resources
    resources_path = path.dirname(resources.__file__)
    resource_path = path.join(resources_path, resource)
    if not path.exists(resource_path):
        raise RuntimeError("Resource '{0}' not found in: {1}".format(
            resource, resource_path))
    return resource_path


def wait_for_execution_to_end(execution, timeout_seconds=240):
    client = create_rest_client()
    deadline = time.time() + timeout_seconds
    while execution.status not in Execution.END_STATES:
        time.sleep(0.5)
        execution = client.executions.get(execution.id)
        if time.time() > deadline:
            raise TimeoutException('Execution timed out: \n{0}'
                                   .format(json.dumps(execution, indent=2)))
    if execution.status == Execution.FAILED:
        raise RuntimeError(
            'Workflow execution failed: {0} [{1}]'.format(execution.error,
                                                          execution.status))
    return execution


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


def timeout(seconds=60):
    def decorator(func):
        def wrapper(*args, **kwargs):
            process = Process(None, func, None, args, kwargs)
            process.start()
            process.join(seconds)
            if process.is_alive():
                process.terminate()
                raise TimeoutException(
                    'test timeout exceeded [timeout={0}'.format(seconds))
        return wraps(func)(wrapper)
    return decorator


def publish_event(queue, routing_key, event):
    exchange_name = 'cloudify-monitoring'
    exchange_type = 'topic'
    connection = create_pika_connection()
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


def delete_provider_context():
    # cyclic import :(
    import integration_tests.postgresql
    integration_tests.postgresql.run_query('DELETE from provider_context')


def restore_provider_context():
    delete_provider_context()
    client = create_rest_client()
    client.manager.create_context(PROVIDER_NAME, PROVIDER_CONTEXT)


def timestamp():
    now = time.strftime("%c")
    return now.replace(' ', '-')


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


class TimeoutException(Exception):

    def __init__(self, message):
        Exception.__init__(self, message)

    def __str__(self):
        return self.message


def upload_mock_plugin(package_name, package_version):
    client = create_rest_client()
    temp_file_path = _create_mock_wagon(package_name, package_version)
    response = client.plugins.upload(temp_file_path)
    os.remove(temp_file_path)
    return response


def _create_mock_wagon(package_name, package_version):
    module_src = tempfile.mkdtemp(
        prefix='plugin-{0}-'.format(package_name))
    try:
        with open(os.path.join(module_src, 'setup.py'), 'w') as f:
            f.write('from setuptools import setup\n')
            f.write('setup(name="{0}", version={1})'.format(
                package_name, package_version))
        wagon_client = wagon.Wagon(module_src)
        result = wagon_client.create(
            archive_destination_dir=tempfile.gettempdir(),
            force=True)
    finally:
        shutil.rmtree(module_src)
    return result


class YamlPatcher(object):

    pattern = re.compile("(.+)\[(\d+)\]")
    set_pattern = re.compile("(.+)\[(\d+|append)\]")

    def __init__(self, yaml_path, is_json=False, default_flow_style=True):
        self.yaml_path = yaml_path
        with open(self.yaml_path) as f:
            self.obj = yaml.load(f) or {}
        self.is_json = is_json
        self.default_flow_style = default_flow_style

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not exc_type:
            output = json.dumps(self.obj) if self.is_json else yaml.safe_dump(
                self.obj, default_flow_style=self.default_flow_style)
            with open(self.yaml_path, 'w') as f:
                f.write(output)

    def merge_obj(self, obj_prop_path, merged_props):
        obj = self._get_object_by_path(obj_prop_path)
        for key, value in merged_props.items():
            obj[key] = value

    def set_value(self, prop_path, new_value):
        obj, prop_name = self._get_parent_obj_prop_name_by_path(prop_path)
        list_item_match = self.set_pattern.match(prop_name)
        if list_item_match:
            prop_name = list_item_match.group(1)
            obj = obj[prop_name]
            if not isinstance(obj, list):
                raise AssertionError('Cannot set list value for not list item '
                                     'in {0}'.format(prop_path))
            raw_index = list_item_match.group(2)
            if raw_index == 'append':
                obj.append(new_value)
            else:
                obj[int(raw_index)] = new_value
        else:
            obj[prop_name] = new_value

    def append_value(self, prop_path, value):
        obj, prop_name = self._get_parent_obj_prop_name_by_path(prop_path)
        obj[prop_name] = obj[prop_name] + value

    def _split_path(self, path):
        # allow escaping '.' with '\.'
        parts = re.split('(?<![^\\\\]\\\\)\.', path)
        return [p.replace('\.', '.').replace('\\\\', '\\') for p in parts]

    def _get_object_by_path(self, prop_path):
        current = self.obj
        for prop_segment in self._split_path(prop_path):
            match = self.pattern.match(prop_segment)
            if match:
                index = int(match.group(2))
                property_name = match.group(1)
                if property_name not in current:
                    self._raise_illegal(prop_path)
                if type(current[property_name]) != list:
                    self._raise_illegal(prop_path)
                current = current[property_name][index]
            else:
                if prop_segment not in current:
                    current[prop_segment] = {}
                current = current[prop_segment]
        return current

    def delete_property(self, prop_path, raise_if_missing=True):
        obj, prop_name = self._get_parent_obj_prop_name_by_path(prop_path)
        if prop_name in obj:
            obj.pop(prop_name)
        elif raise_if_missing:
            raise KeyError('cannot delete property {0} as its not a key in '
                           'object {1}'.format(prop_name, obj))

    def _get_parent_obj_prop_name_by_path(self, prop_path):
        split = self._split_path(prop_path)
        if len(split) == 1:
            return self.obj, prop_path
        parent_path = '.'.join(p.replace('.', '\.') for p in split[:-1])
        parent_obj = self._get_object_by_path(parent_path)
        prop_name = split[-1]
        return parent_obj, prop_name

    @staticmethod
    def _raise_illegal(prop_path):
        raise RuntimeError('illegal path: {0}'.format(prop_path))


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
