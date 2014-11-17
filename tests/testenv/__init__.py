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

from cloudify.utils import setup_default_logger
from cloudify.logs import create_event_message_prefix

import mock_plugins
from testenv.constants import MANAGER_REST_PORT
from testenv.constants import RABBITMQ_VERBOSE_MESSAGES_ENABLED
from testenv.constants import RABBITMQ_POLLING_ENABLED
from testenv.constants import FILE_SERVER_RESOURCES_URI
from testenv.constants import FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER
from testenv.constants import FILE_SERVER_BLUEPRINTS_FOLDER
from testenv.processes.elastic import ElasticSearchProcess
from testenv.processes.manager_rest import ManagerRestProcess
from testenv.processes.riemann import RiemannProcess
from testenv.processes.celery import CeleryWorkerProcess
from testenv import utils

logger = setup_default_logger('TESTENV')
setup_default_logger('cloudify.rest_client', logging.INFO)
testenv_instance = None


class TestCase(unittest.TestCase):

    """
    A test case for cloudify integration tests.
    """

    def setUp(self):
        self.logger = setup_default_logger(self._testMethodName,
                                           logging.INFO)
        self.client = utils.create_rest_client()
        utils.restore_provider_context()
        TestEnvironment.start_celery_management_worker()

    def tearDown(self):
        TestEnvironment.reset_elasticsearch_data()
        TestEnvironment.stop_celery_management_worker()
        TestEnvironment.stop_all_celery_processes()

    def get_plugin_data(self,
                        plugin_name,
                        deployment_id):

        """
        Retrieve the plugin state for a certain deployment.

        :param deployment_id: the deployment id in question.
        :param plugin_name: the plugin in question.
        :return: plugin data relevant for the deployment.
        :rtype dict
        """

        return self._get_plugin_data(
            plugin_name=plugin_name,
            deployment_id=deployment_id
        )

    def clear_plugin_data(self, plugin_name):
        """
        Clears plugin state.

        :param plugin_name: the plugin in question.
        """
        return self._clear_plugin_data(
            plugin_name=plugin_name
        )

    def _get_plugin_data(self,
                         plugin_name,
                         deployment_id):
        storage_file_path = os.path.join(
            testenv_instance.plugins_storage_dir,
            '{0}.json'.format(plugin_name)
        )
        if not os.path.exists(storage_file_path):
            return {}
        with open(storage_file_path, 'r') as f:
            data = json.load(f)
            if deployment_id not in data:
                data[deployment_id] = {}
            return data.get(deployment_id)

    def _clear_plugin_data(self,
                           plugin_name):
        storage_file_path = os.path.join(
            testenv_instance.plugins_storage_dir,
            '{0}.json'.format(plugin_name)
        )
        if os.path.exists(storage_file_path):
            os.remove(storage_file_path)

    @staticmethod
    def do_assertions(assertions_func, timeout=10, **kwargs):
        return utils.do_retries(assertions_func,
                                timeout,
                                AssertionError,
                                **kwargs)

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
        routing_key = deployment_id
        utils.publish_event(queue,
                            routing_key,
                            event)


class ProcessModeTestCase(TestCase):

    def setUp(self):

        # can actually be any string
        # besides the empty one
        os.environ['PROCESS_MODE'] = 'True'
        super(ProcessModeTestCase, self).setUp()

    def tearDown(self):

        # empty string means false
        os.environ['PROCESS_MODE'] = ''
        super(ProcessModeTestCase, self).tearDown()


class TestEnvironment(object):

    manager_rest_process = None
    elasticsearch_process = None
    riemann_process = None
    file_server_process = None
    celery_management_worker_process = None

    def __init__(self, test_working_dir):
        super(TestEnvironment, self).__init__()
        self.test_working_dir = test_working_dir
        self.plugins_storage_dir = os.path.join(
            self.test_working_dir,
            'plugins-storage'
        )
        os.makedirs(self.plugins_storage_dir)
        self.fileserver_dir = path.join(self.test_working_dir, 'fileserver')

    def create(self):

        try:
            logger.info('Setting up test environment... workdir=[{0}]'
                        .format(self.test_working_dir))

            # events/logs polling
            start_events_and_logs_polling()

            self.start_elasticsearch()
            self.start_riemann()
            self.start_fileserver()
            self.start_manager_rest()
            self.create_management_worker()

        except BaseException as error:
            s_traceback = StringIO.StringIO()
            traceback.print_exc(file=s_traceback)
            logger.error("Error in test environment setup: %s", error)
            logger.error(s_traceback.getvalue())
            self.destroy()
            raise

    def create_management_worker(self):

        mock_plugins_path = os.path.dirname(mock_plugins.__file__)
        os.environ['MOCK_PLUGINS_PATH'] = mock_plugins_path

        self.celery_management_worker_process = CeleryWorkerProcess(
            queues=['cloudify.management'],
            test_working_dir=self.test_working_dir,

            # these plugins are already installed.
            # so we just need to append to the includes.
            # note that these are not mocks, but the actual production
            # code plugins.

            additional_includes=[
                'riemann_controller.tasks',
                'cloudify_system_workflows.deployment_environment',
                'cloudify.plugins.workflows',
                'diamond_agent.tasks',
                'script_runner.tasks'
            ],

            # we need higher concurrency since
            # 'deployment_environment.create' calls
            # 'plugin_installer.install' as a sub-task
            # and they are both executed inside
            # this worker
            concurrency=2
        )

        # copy plugins to worker env
        mock_plugins_path = os.path.dirname(mock_plugins.__file__)

        shutil.copytree(
            src=mock_plugins_path,
            dst=self.celery_management_worker_process.envdir,
            ignore=shutil.ignore_patterns('*.pyc')
        )

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

    def destroy(self):
        logger.info('Destroying test environment...')
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
    def reset_elasticsearch_data():
        global testenv_instance
        testenv_instance.elasticsearch_process.reset_data()

    @staticmethod
    def stop_celery_management_worker():
        global testenv_instance
        testenv_instance.celery_management_worker_process.stop()

    @classmethod
    def stop_all_celery_processes(cls):
        logger.info('Shutting down all celery processes')
        os.system('pkill -f celery')

    @staticmethod
    def start_celery_management_worker():
        global testenv_instance
        testenv_instance.celery_management_worker_process.start()

    @staticmethod
    def riemann_workdir():
        global testenv_instance
        return testenv_instance.\
            celery_management_worker_process.\
            riemann_config_dir

    @staticmethod
    def _get_manager_root():
        init_file = __file__
        testenv_dir = dirname(init_file)
        tests_dir = dirname(testenv_dir)
        manager_dir = dirname(tests_dir)
        return manager_dir

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
                output = create_event_message_prefix(output)
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
