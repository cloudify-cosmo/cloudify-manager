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
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

import json
import os
import uuid
import pika
import requests
import time
import urllib

from contextlib import contextmanager
from functools import wraps
from celery import Celery
from multiprocessing import Process
from cloudify.utils import setup_logger
from cloudify_rest_client import CloudifyClient
from cloudify_rest_client.executions import Execution
from os import path
from testenv.processes.manager_rest import MANAGER_REST_PORT


PROVIDER_CONTEXT = {
    'cloudify': {
        'workflows': {
            'task_retries': 0,
            'task_retry_interval': 0
        }
    }
}
PROVIDER_NAME = 'integration_tests'


celery = Celery(broker='amqp://',
                backend='amqp://')
celery.conf.update(
    CELERY_TASK_SERIALIZER="json",
    CELERY_TASK_RESULT_EXPIRES=600)


logger = setup_logger('testenv.utils')


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


def build_includes(directory):

    includes = []

    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            file_path = os.path.join(root, filename)
            if '__init__' in file_path:
                continue
            if 'pyc' in file_path:
                continue
            module = os.path.splitext(file_path)[0].replace(
                directory, '').strip('/').replace('/', '.')
            includes.append(module)

    return includes


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
        from testenv import TestEnvironment  # avoid cyclic import
        logs = TestEnvironment.read_celery_management_logs() or ''
        logs = logs[len(logs) - 100000:]
        raise RuntimeError(
            "Expected a single execution for workflow "
            "'create_deployment_environment' with status 'terminated'; "
            "Found these executions instead: {0}.\nCelery log:\n{1}".format(
                json.dumps(execs, indent=2), logs))


def undeploy_application(deployment_id,
                         timeout_seconds=240,
                         delete_deployment=False):
    """
    A blocking method which undeploys an application from the provided dsl
    path.
    """
    client = create_rest_client()
    execution = client.executions.start(deployment_id,
                                        'uninstall')
    wait_for_execution_to_end(execution, timeout_seconds=timeout_seconds)

    if execution.error and execution.error != 'None':
        raise RuntimeError(
            'Workflow execution failed: {0}'.format(execution.error))
    if delete_deployment:
        time.sleep(5)  # elasticsearch...
        client.deployments.delete(deployment_id)


def is_node_started(node_id):
    client = create_rest_client()
    node_instance = client.node_instances.get(node_id)
    return node_instance['state'] == 'started'


def create_rest_client():
    return CloudifyClient(host='localhost', port=MANAGER_REST_PORT)


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
            func(**kwargs)
            break
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


def send_task(task, queue, args=None):
    task_name = task.name.replace('mock_plugins.', '')
    return celery.send_task(
        name=task_name,
        args=args,
        queue=queue)


def publish_event(queue,
                  routing_key,
                  event,
                  exchange_name='cloudify-monitoring',
                  exchange_type='topic'):
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()
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
    channel.close()
    connection.close()


def delete_provider_context():
    requests.delete('http://localhost:9200'
                    '/cloudify_storage/provider_context/CONTEXT')


def restore_provider_context():
    delete_provider_context()
    client = create_rest_client()
    client.manager.create_context(PROVIDER_NAME, PROVIDER_CONTEXT)


def wait_for_url(url, timeout=15):
    end = time.time() + timeout

    while end >= time.time():
        try:
            status = urllib.urlopen(url).getcode()
            if status == 200:
                return
        except IOError:
            time.sleep(1)

    raise RuntimeError('Url {0} is not available (waited {1} '
                       'seconds)'.format(url, timeout))


def timestamp():
    now = time.strftime("%c")
    return now.replace(' ', '-')


@contextmanager
def update_storage(ctx):

    """
    A context manager for updating plugin state.

    :param ctx: task invocation context
    """

    deployment_id = ctx.deployment.id
    plugin_name = ctx.plugin
    if plugin_name is None:

        # hack for tasks that are executed locally.
        if ctx.task_name.startswith('cloudify_agent'):
            plugin_name = 'agent'

    storage_file_path = os.path.join(
        os.environ['TEST_WORKING_DIR'],
        'plugins-storage',
        '{0}.json'.format(plugin_name)
    )

    # create storage file
    # if it doesn't exist
    if not os.path.exists(storage_file_path):
        f = open(storage_file_path, 'w')
        json.dump({}, f)

    with open(storage_file_path, 'r') as f:
        data = json.load(f)
        if deployment_id not in data:
            data[deployment_id] = {}
        yield data.get(deployment_id)
    with open(storage_file_path, 'w') as f:
        json.dump(data, f, indent=2)
        f.write(os.linesep)


class TimeoutException(Exception):

    def __init__(self, message):
        Exception.__init__(self, message)

    def __str__(self):
        return self.message
