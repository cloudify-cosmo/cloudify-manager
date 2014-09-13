########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import StringIO
import shutil
import logging
import os
import sys
import threading
import time
import traceback
import unittest
import json
import pika
import yaml

from os.path import dirname
from os import path
from testenv.constants import MANAGER_REST_PORT
from testenv.constants import RABBITMQ_VERBOSE_MESSAGES_ENABLED
from testenv.constants import RABBITMQ_POLLING_ENABLED
from testenv.constants import FILE_SERVER_RESOURCES_URI
from testenv.constants import FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER
from testenv.constants import FILE_SERVER_BLUEPRINTS_FOLDER
from testenv.constants import WORKERS_ENV_DIR_SUFFIX
from testenv.constants import TOP_LEVEL_DIR
from testenv.processes.elastic import ElasticSearchProcess
from testenv.processes.manager_rest import ManagerRestProcess
from testenv.processes.riemann import RiemannProcess
from testenv import utils
from cloudify.utils import setup_default_logger
from testenv.processes.celery import CeleryWorkerProcess
from cloudify.utils import id_generator
from testenv.utils import timestamp
from testenv.utils import update_storage
from testenv.utils import deploy_application

logger = setup_default_logger('TESTENV')
test_env_instance = None


class TestEnvironmentScope(object):
    CLASS = "CLASS"
    MODULE = "MODULE"
    PACKAGE = "PACKAGE"

    @staticmethod
    def validate(scope):
        if scope not in [
            TestEnvironmentScope.CLASS,
            TestEnvironmentScope.MODULE,
            TestEnvironmentScope.PACKAGE
        ]:
            raise AttributeError('Unknown test environment scope: ' +
                                 str(scope))


class TestCase(unittest.TestCase):
    """
    A test case for cloudify integration tests.
    """

    @classmethod
    def setUpClass(cls):
        TestEnvironment.create(TestEnvironmentScope.CLASS)

    @classmethod
    def tearDownClass(cls):
        TestEnvironment.destroy(TestEnvironmentScope.CLASS)

    def setUp(self):
        self.logger = logging.getLogger(self._testMethodName)
        self.logger.setLevel(logging.INFO)
        self.client = utils.create_rest_client()
        utils.restore_provider_context()
        TestEnvironment.start_celery_management_worker()

    def tearDown(self):
        TestEnvironment.stop_celery_management_worker()
        TestEnvironment.reset_elasticsearch_data()
        TestEnvironment.kill_celery_workers()

    def get_plugin_data(self, plugin_name, deployment_id=None, host_id=None, workflows=False, worker_name=False):

        """
        Retrieve the plugin state for a curtain deployment agent or host agent.

        :param deployment_id: the deployment id in question.
                              use this for querying deployment agents.
        :param host_id: the host id in question.
                        use this for querying host agents.
        :param plugin_name: the plugin in question.
        :return: plugin data relevant for the deployment.
        :rtype dict
        """

        # validations
        if host_id and deployment_id:
            raise RuntimeError("Cannot specify both 'deployment_id' and 'host_id'")
        if not host_id and not deployment_id and not worker_name:
            raise RuntimeError("Must specify either 'deployment_id' or 'host_id' or 'worker_name'")
        if host_id and workflows:
            raise RuntimeError('Host agent plugins cannot be workflows')
        if worker_name and host_id:
            raise RuntimeError("Cannot specify both 'worker_name' and 'host_id'")

        global test_env_instance

        # create worker instance to
        # get the workdir

        queue = None
        if worker_name:
            queue = worker_name
        elif deployment_id:
            if workflows:
                queue = '{0}_workflows'.format(deployment_id)
            else:
                queue = deployment_id
        elif host_id:
            queue = host_id

        worker = CeleryWorkerProcess(
            queues=[queue],
            test_working_dir=test_env_instance.test_working_dir
        )

        return self._get_plugin_data(
            plugin_name=plugin_name,
            deployment_id=deployment_id,
            host_id=host_id,
            worker_work_dir=worker.workdir
        )

    def _get_plugin_data(self,
                         plugin_name,
                         deployment_id,
                         host_id,
                         worker_work_dir):
        storage_file_path = os.path.join(
            worker_work_dir,
            '{0}.json'.format(plugin_name)
        )
        if not os.path.exists(storage_file_path):
            return {}
        with open(storage_file_path, 'r') as f:
            data = json.load(f)
            if host_id:
                # a host agent always belongs to
                # a single deployment
                return data.itervalues().next()
            # all other agents save
            # data per deployment
            if deployment_id not in data:
                data[deployment_id] = {}
            return data.get(deployment_id)


    @staticmethod
    def do_assertions(assertions_func, timeout=10, **kwargs):
        return utils.do_retries(assertions_func, timeout, AssertionError, **kwargs)

    @property
    def riemann_workdir(self):
        return TestEnvironment.riemann_workdir()

    def publish_riemann_event(self,
                              deployment_id,
                              node_name,
                              node_id='',
                              host='localhost',
                              service='service',
                              state='',
                              metric=0):
        event = {
            'host': host,
            'service': service,
            'state': state,
            'metric': metric,
            'time': int(time.time()),
            'node_name': node_name,
            'node_id': node_id
        }
        queue = '{0}-riemann'.format(deployment_id)
        utils.publish_event(queue, event)


class TestEnvironment(object):

    manager_rest_process = None
    elasticsearch_process = None
    riemann_process = None
    file_server_process = None
    celery_management_worker_process = None

    def __init__(self, scope):
        try:

            logger.info('Setting up test environment... [scope={0}]'.format(scope))
            self.scope = scope

            unique_name = 'TestEnvironment-{0}'.format(id_generator(4))

            self.test_working_dir = os.path.join(
                TOP_LEVEL_DIR,
                unique_name
            )
            os.makedirs(self.test_working_dir)

            self.fileserver_dir = path.join(self.test_working_dir, 'fileserver')

            # events/logs polling
            start_events_and_logs_polling()

            self.start_elasticsearch()
            self.start_riemann()
            self.start_fileserver()
            self.start_manager_rest()

        except BaseException as error:
            s_traceback = StringIO.StringIO()
            traceback.print_exc(file=s_traceback)
            logger.error("Error in test environment setup: %s", error)
            logger.error(s_traceback.getvalue())
            self.destroy_test_env()
            raise

    def start_management_worker(self):

        self.celery_management_worker_process = CeleryWorkerProcess(
            queues=['cloudify.management'],
            test_working_dir=self.test_working_dir,

            # these two plugins are already installed.
            # so we just need to append to the includes.
            # note that these are not mocks, but the actual production
            # code plugins.

            includes=[
                'riemann_controller.tasks',
                'cloudify_system_workflows.deployment_environment'
            ]
        )

        self.celery_management_worker_process.start()

    def start_riemann(self):
        riemann_config_path = self._get_riemann_config()
        libs_path = self._get_libs_path()
        self.riemann_process = RiemannProcess(riemann_config_path,
                                              libs_path)
        self.riemann_process.start()

    def start_manager_rest(self):

        from manager_rest.file_server import PORT as FS_PORT
        file_server_base_uri = 'http://localhost:{0}'.format(FS_PORT)
        self.manager_rest_process = ManagerRestProcess(
            MANAGER_REST_PORT,
            self.fileserver_dir,
            file_server_base_uri,
            FILE_SERVER_BLUEPRINTS_FOLDER,
            FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
            FILE_SERVER_RESOURCES_URI,
            self.test_working_dir)
        self.manager_rest_process.start()

    def start_elasticsearch(self):
        # elasticsearch
        self.elasticsearch_process = ElasticSearchProcess()
        self.elasticsearch_process.start()

    def start_fileserver(self):

        # workaround to update path
        manager_rest_path = \
            path.dirname(path.dirname(path.dirname(__file__)))
        manager_rest_path = path.join(manager_rest_path, 'rest-service')
        sys.path.append(manager_rest_path)

        os.mkdir(self.fileserver_dir)
        from manager_rest.file_server import FileServer
        from manager_rest.util import copy_resources

        self.file_server_process = FileServer(self.fileserver_dir)
        self.file_server_process.start()

        # copy resources (base yaml etc)
        resources_path = path.abspath(__file__)
        resources_path = path.dirname(resources_path)
        resources_path = path.dirname(resources_path)
        resources_path = path.dirname(resources_path)
        resources_path = path.join(resources_path, 'resources')
        copy_resources(self.fileserver_dir, resources_path)

        self.patch_source_urls(self.fileserver_dir)

    def kill_non_management_celery_workers(self):

        def kill_workers(state_path):
            with open(state_path, 'r') as state:
                data = json.load(state)
                for deployment_id in data.keys():
                    for worker_state in data[deployment_id].values():
                        worker_pids = worker_state['pids']
                        if worker_pids:
                            logger.info('Killing processes {0}'.format(str(worker_pids)))
                            os.system('kill -9 {0}'.format(' '.join(worker_pids)))
            logger.info('Deleting {0}'.format(state_path))
            os.remove(state_path)

        import os
        for root, dirs, files in os.walk(self.test_working_dir):
            for f in files:
                # workers are created only
                # via the worker installer, yey
                if f == 'worker_installer.json':
                    kill_workers(os.path.join(root, f))

    def destroy_test_env(self):
        logger.info('Destroying test environment... [scope={0}]'.format(
            self.scope))
        if self.riemann_process:
            self.riemann_process.close()
        if self.elasticsearch_process:
            self.elasticsearch_process.close()
        if self.manager_rest_process:
            self.manager_rest_process.close()
        if self.file_server_process:
            self.file_server_process.stop()
        self.delete_working_directory()

    def delete_working_directory(self):
        if os.path.exists(self.test_working_dir):
            logger.info('Deleting test environment from: %s',
                        self.test_working_dir)
            shutil.rmtree(self.test_working_dir, ignore_errors=True)

    @classmethod
    def _get_riemann_config(cls):
        manager_dir = cls._get_manager_root()
        plugins_dir = os.path.join(manager_dir, 'plugins')
        riemann_dir = os.path.join(plugins_dir, 'riemann-controller')
        package_dir = os.path.join(riemann_dir, 'riemann_controller')
        resources_dir = os.path.join(package_dir, 'resources')
        manager_config = os.path.join(resources_dir, 'manager.config')
        return manager_config

    @classmethod
    def _get_libs_path(cls):
        return path.join(cls._get_manager_root(), '.libs')

    @staticmethod
    def create(scope):

        """
        Creates the test environment if not already created.
        Save the environment as a global instance for further access.

        :param scope: The scope the test environment is created at.
        """
        global test_env_instance
        if not test_env_instance:
            test_env_instance = TestEnvironment(scope)
        return test_env_instance

    @staticmethod
    def destroy(scope):
        """
        Destroys the test environment if the provided scope matches the scope
        the environment was created with.
        :param scope: The scope this method is invoked from.
        """
        global test_env_instance
        if test_env_instance and test_env_instance.scope == scope:
            test_env_instance.destroy_test_env()

    @staticmethod
    def kill_celery_workers():
        global test_env_instance
        test_env_instance.kill_non_management_celery_workers()

    @staticmethod
    def reset_elasticsearch_data():
        global test_env_instance
        if test_env_instance and test_env_instance.elasticsearch_process:
            test_env_instance.elasticsearch_process.reset_data()

    @staticmethod
    def stop_celery_management_worker():
        global test_env_instance
        test_env_instance.celery_management_worker_process.stop()

    @staticmethod
    def start_celery_management_worker():
        global test_env_instance
        test_env_instance.start_management_worker()

    @staticmethod
    def _get_manager_root():
        init_file = __file__
        testenv_dir = dirname(init_file)
        tests_dir = dirname(testenv_dir)
        manager_dir = dirname(tests_dir)
        return manager_dir

    @staticmethod
    def riemann_workdir():
        global test_env_instance
        if test_env_instance and test_env_instance.celery_management_worker_process:
            return test_env_instance.celery_management_worker_process.riemann_config_dir
        return None

    @staticmethod
    def patch_source_urls(resources):
        with open(path.join(resources,
                            'cloudify', 'types', 'types.yaml')) as f:
            types_yaml = yaml.safe_load(f.read())
        for policy_type in types_yaml.get('policy_types', {}).values():
            in_path = '/cloudify/policies/'
            source = policy_type['source']
            if in_path in source:
                source = source[source.index(in_path) + 1:]
            policy_type['source'] = source
        for policy_trigger in types_yaml.get('policy_triggers', {}).values():
            in_path = '/cloudify/triggers/'
            source = policy_trigger['source']
            if in_path in source:
                source = source[source.index(in_path) + 1:]
            policy_trigger['source'] = source
        with open(path.join(resources,
                            'cloudify', 'types', 'types.yaml'), 'w') as f:
            f.write(yaml.safe_dump(types_yaml))


def start_events_and_logs_polling():
    """
    Fetches events and logs from RabbitMQ.
    """
    if not RABBITMQ_POLLING_ENABLED:
        return

    setup_default_logger('pika', logging.INFO)
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()
    queues = ['cloudify-events', 'cloudify-logs']
    for q in queues:
        channel.queue_declare(queue=q, auto_delete=True, durable=True,
                              exclusive=False)

    def callback(ch, method, properties, body):
        try:
            output = json.loads(body)
            if RABBITMQ_VERBOSE_MESSAGES_ENABLED:
                output = '\n{0}'.format(json.dumps(output, indent=4))
            else:
                output = _create_event_message(output)
            logger.info(output)
        except Exception as e:
            logger.error('event/log format error - output: {0} [message={1}]'
                         .format(body, e.message))
            s_traceback = StringIO.StringIO()
            traceback.print_exc(file=s_traceback)
            logger.error(s_traceback.getvalue())

    def consume():
        channel.basic_consume(callback, queue=queues[0], no_ack=True)
        channel.basic_consume(callback, queue=queues[1], no_ack=True)
        channel.start_consuming()

    logger.info("Starting RabbitMQ events/logs polling - queues={0}".format(
        queues))

    polling_thread = threading.Thread(target=consume)
    polling_thread.daemon = True
    polling_thread.start()


# TODO - This is a duplication from the CLI.
# TODO - What can we do?
def _create_event_message(event):
    context = event['context']
    deployment_id = context['deployment_id']
    node_info = ''
    operation = ''
    if 'node_id' in context and context['node_id'] is not None:
        node_id = context['node_id']
        if 'operation' in context and context['operation'] is not None:
            operation = '.{0}'.format(context['operation'].split('.')[-1])
        node_info = '[{0}{1}] '.format(node_id, operation)
    level = 'CFY'
    message = event['message']['text'].encode('utf-8')
    if 'cloudify_log' in event['type']:
        level = 'LOG'
        message = '{0}: {1}'.format(event['level'].upper(), message)
    timestamp_ = event['timestamp'].split('.')[0]

    return '{0} {1} <{2}> {3}{4}'.format(timestamp_,
                                         level,
                                         deployment_id,
                                         node_info,
                                         message)
