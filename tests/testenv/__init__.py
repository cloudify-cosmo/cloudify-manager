########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

__author__ = 'ran'

import shutil
import distutils.core
import tempfile
import shlex
import subprocess
import logging
import os
import sys
import threading
import re
import uuid
import time
import unittest
from os import path
from functools import wraps
from multiprocessing import Process
from os.path import dirname, abspath

import yaml
import pika
import json
import elasticsearch
from celery import Celery
from cloudify.constants import MANAGEMENT_NODE_ID
from cosmo_manager_rest_client.cosmo_manager_rest_client \
    import CosmoManagerRestClient
from cloudify_rest_client import CloudifyClient

import plugins
import mock_workflows


CLOUDIFY_MANAGEMENT_QUEUE = MANAGEMENT_NODE_ID
CLOUDIFY_WORKFLOWS_QUEUE = 'cloudify.workflows'
CELERY_QUEUES_LIST = [MANAGEMENT_NODE_ID]
CELERY_WORKFLOWS_QUEUE_LIST = [CLOUDIFY_WORKFLOWS_QUEUE]

STORAGE_INDEX_NAME = 'cloudify_storage'
FILE_SERVER_PORT = 53229
MANAGER_REST_PORT = 8100
FILE_SERVER_BLUEPRINTS_FOLDER = 'blueprints'
FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER = 'uploaded-blueprints'
FILE_SERVER_RESOURCES_URI = '/resources'

root = logging.getLogger()
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter(fmt='%(asctime)s [%(levelname)s] '
                                  '[%(name)s] %(message)s',
                              datefmt='%H:%M:%S')
ch.setFormatter(formatter)

# clear all other handlers
for handler in root.handlers:
    root.removeHandler(handler)

root.addHandler(ch)
logger = logging.getLogger("TESTENV")
logger.setLevel(logging.DEBUG)

RABBITMQ_POLLING_KEY = 'RABBITMQ_POLLING'

RABBITMQ_POLLING_ENABLED = RABBITMQ_POLLING_KEY not in os.environ \
    or os.environ[RABBITMQ_POLLING_KEY].lower() != 'false'

RABBITMQ_VERBOSE_MESSAGES_KEY = 'RABBITMQ_VERBOSE_MESSAGES'

RABBITMQ_VERBOSE_MESSAGES_ENABLED = os.environ.get(
    RABBITMQ_VERBOSE_MESSAGES_KEY, 'false').lower() == 'true'

celery = Celery(broker='amqp://',
                backend='amqp://')

celery.conf.update(
    CELERY_TASK_SERIALIZER="json"
)


class ManagerRestProcess(object):

    def __init__(self,
                 port,
                 file_server_dir,
                 file_server_base_uri,
                 workflow_service_base_uri,
                 file_server_blueprints_folder,
                 file_server_uploaded_blueprints_folder,
                 file_server_resources_uri,
                 tempdir):
        self.process = None
        self.port = port
        self.file_server_dir = file_server_dir
        self.file_server_base_uri = file_server_base_uri
        self.workflow_service_base_uri = workflow_service_base_uri
        self.file_server_blueprints_folder = file_server_blueprints_folder
        self.file_server_uploaded_blueprints_folder = \
            file_server_uploaded_blueprints_folder
        self.file_server_resources_uri = file_server_resources_uri
        self.client = CosmoManagerRestClient('localhost',
                                             port=port)
        self.tempdir = tempdir

    def start(self, timeout=10):
        endtime = time.time() + timeout

        configuration = {
            'file_server_root': self.file_server_dir,
            'file_server_base_uri': self.file_server_base_uri,
            'workflow_service_base_uri': self.workflow_service_base_uri,
            'file_server_uploaded_blueprints_folder':
                self.file_server_uploaded_blueprints_folder,
            'file_server_resources_uri': self.file_server_resources_uri,
            'file_server_blueprints_folder': self.file_server_blueprints_folder
        }

        config_path = os.path.join(self.tempdir, 'manager_config.json')
        with open(config_path, 'w') as f:
            f.write(yaml.dump(configuration))

        env = os.environ.copy()
        env['MANAGER_REST_CONFIG_PATH'] = config_path
        env['CLOUDIFY_WORKFLOWS_QUEUE'] = CLOUDIFY_WORKFLOWS_QUEUE

        python_path = sys.executable

        manager_rest_command = [
            '{0}/gunicorn'.format(dirname(python_path)),
            '-w', '2',
            '-b', '0.0.0.0:{0}'.format(self.port),
            '--timeout', '300',
            'server:app'
        ]

        logger.info('Starting manager-rest with: {0}'.format(
            manager_rest_command))

        self.process = subprocess.Popen(manager_rest_command,
                                        env=env,
                                        cwd=self.locate_manager_rest_dir())
        started = False
        attempt = 1
        while not started and time.time() < endtime:
            time.sleep(1)
            logger.info('Testing connection to manager rest service. '
                        '(Attempt: {0}/{1})'.format(attempt, timeout))
            attempt += 1
            started = self.started()
        if not started:
            raise RuntimeError('Failed opening connection to manager rest '
                               'service')

    def started(self):
        try:
            self.client.list_blueprints()
            return True
        except BaseException:
            return False

    def close(self):
        if self.process is not None:
            self.process.terminate()

    def locate_manager_rest_dir(self):
        # start with current location
        manager_rest_location = path.abspath(__file__)
        # get to cosmo-manager
        for i in range(3):
            manager_rest_location = path.dirname(manager_rest_location)
        # build way into manager_rest
        return path.join(manager_rest_location,
                         'rest-service/manager_rest')


class CeleryWorkerProcess(object):
    _process = None

    def __init__(self,
                 tempdir,
                 plugins_tempdir,
                 manager_rest_port,
                 name,
                 queues,
                 includes,
                 hostname,
                 concurrency=1):
        self._name = name
        self._celery_pid_file = path.join(tempdir, "celery-{}.pid".format(
            name))
        self._celery_log_file = path.join(tempdir, "celery-{}.log".format(
            name))
        self._tempdir = tempdir
        self._plugins_tempdir = plugins_tempdir
        self._manager_rest_port = manager_rest_port
        self._includes = includes
        self._queues = ','.join(queues)
        self._hostname = hostname
        self._concurrency = concurrency

    def start(self):
        python_path = sys.executable
        celery_command = [
            "{0}/celery".format(dirname(python_path)),
            "worker",
            "--events",
            "--loglevel=debug",
            "--hostname=celery.{}".format(self._hostname),
            "--purge",
            "--app=cloudify",
            "--logfile={0}".format(self._celery_log_file),
            "--pidfile={0}".format(self._celery_pid_file),
            "--queues={0}".format(self._queues),
            "--concurrency={0}".format(self._concurrency),
            "--include={0}".format(','.join(self._includes))
        ]

        prevdir = os.getcwd()
        os.chdir(os.path.join(self._tempdir, "plugins"))

        environment = os.environ.copy()
        environment['CELERY_QUEUES'] = self._queues
        environment['TEMP_DIR'] = self._plugins_tempdir
        environment['MANAGER_REST_PORT'] = str(self._manager_rest_port)
        environment['MANAGEMENT_IP'] = 'localhost'
        environment['MANAGER_FILE_SERVER_BLUEPRINTS_ROOT_URL'] = \
            'http://localhost:{0}/{1}'.format(FILE_SERVER_PORT,
                                              FILE_SERVER_BLUEPRINTS_FOLDER)
        environment['MANAGER_FILE_SERVER_URL'] = 'http://localhost:{0}' \
            .format(FILE_SERVER_PORT)

        environment['AGENT_IP'] = 'localhost'
        environment['VIRTUALENV'] = dirname(dirname(python_path))

        logger.info("Starting celery worker with command {0}".format(
            celery_command))
        self._process = subprocess.Popen(celery_command, env=environment)

        timeout = 60
        deadline = time.time() + timeout
        while not path.exists(self._celery_pid_file) and \
                (time.time() < deadline):
            time.sleep(1)

        if not path.exists(self._celery_pid_file):
            celery_log = self.try_read_logfile()
            if celery_log is not None:
                logger.error("{0} content:\n{1}".format(
                    self._celery_log_file, celery_log))
            raise RuntimeError(
                "Failed to start celery {0} worker: {1} - process did not "
                "start after {2} seconds".format(self._name,
                                                 self._process.returncode,
                                                 timeout))

        os.chdir(prevdir)
        logger.info("Celery worker started [pid=%s]", self._process.pid)

    def close(self):
        if self._process:
            logger.info("Shutting down celery {} worker [pid={}]".format(
                self._name, self._process.pid))
            self._process.kill()

    def _get_celery_process_ids(self):
        from subprocess import CalledProcessError
        try:
            grep = "ps aux | grep 'celery.*{0}' | grep -v grep".format(
                self._celery_pid_file)
            grep += " | awk '{print $2}'"
            output = subprocess.check_output(grep, shell=True)
            ids = filter(lambda x: len(x) > 0, output.split(os.linesep))
            return ids
        except CalledProcessError:
            return []

    def restart(self):
        """
        Restarts the celery worker process.
        Celery's child processes will have a different PID.
        """
        process_ids = self._get_celery_process_ids()
        for pid in process_ids:
            # kill celery child processes
            if pid != str(self._process.pid):
                logger.info(
                    "Killing celery {} worker [pid={}]".format(
                        self._name, pid))
                os.system('kill -9 {0}'.format(pid))
        timeout = time.time() + 30
        # wait until celery master creates a new child
        while len(self._get_celery_process_ids()) != 1+self._concurrency:
            time.sleep(1)
            if time.time() > timeout:
                raise RuntimeError(
                    'Celery {} worker restart timeout '
                    '[current_ids={}, previous_ids={}'.format(
                        self._name, self._get_celery_process_ids(),
                        process_ids))

    def try_read_logfile(self):
        if path.exists(self._celery_log_file):
            with open(self._celery_log_file, "r") as f:
                return f.read()
        return None

    @staticmethod
    def _build_includes():
        includes = []
        # adding the mock workflow plugin for workers installation
        includes.append("system_workflows.workers_installation")

        # iterate over the mock plugins directory and include all of them
        mock_plugins_path = os.path \
            .join(dirname(dirname(abspath(__file__))), "plugins")

        for plugin_dir_name in os.walk(mock_plugins_path).next()[1]:
            tasks_path = os.path \
                .join(mock_plugins_path, plugin_dir_name, "tasks.py")
            if os.path.exists(tasks_path):
                includes.append("{0}.tasks".format(plugin_dir_name))
            else:
                logger.warning(
                    "Could not find tasks.py file under plugin {0}. This "
                    "plugin will not be loaded!".format(plugin_dir_name))
        return includes


class CeleryWorkflowsWorkerProcess(CeleryWorkerProcess):

    def __init__(self, tempdir, plugins_tempdir,
                 manager_rest_port, use_mock_workers_installation=True):
        includes = ["workflows.default", "plugin_installer.tasks"]
        if use_mock_workers_installation:
            includes.append("mock_workflows.workflows")
        super(CeleryWorkflowsWorkerProcess, self).__init__(
            tempdir, plugins_tempdir, manager_rest_port,
            name='workflows',
            queues=CELERY_WORKFLOWS_QUEUE_LIST,
            includes=includes,
            hostname='cloudify.workflows')


class CeleryOperationsWorkerProcess(CeleryWorkerProcess):

    def __init__(self, tempdir, plugins_tempdir,
                 manager_rest_port, concurrency=1):
        super(CeleryOperationsWorkerProcess, self).__init__(
            tempdir, plugins_tempdir, manager_rest_port,
            name='operations',
            queues=CELERY_QUEUES_LIST,
            includes=self._build_includes(),
            hostname='cloudify.management',
            concurrency=concurrency)


class CeleryTestWorkerProcess(CeleryWorkerProcess):

    def __init__(self, tempdir, plugins_tempdir,
                 manager_rest_port, queue):
        super(CeleryTestWorkerProcess, self).__init__(
            tempdir, plugins_tempdir, manager_rest_port,
            name=queue,
            queues=[queue],
            includes=self._build_includes(),
            hostname=queue)


class RiemannProcess(object):
    """
    Manages a riemann server process lifecycle.
    """
    pid = None
    _config_path = None
    _process = None
    _detector = None
    _event = None
    _riemann_logs = list()

    def __init__(self, config_path):
        self._config_path = config_path

    def _start_detector(self, process):
        pid_pattern = ".*PID\s(\d*)"
        started_pattern = ".*Hyperspace core online"
        while True:
            line = process.stdout.readline().rstrip()
            if line != '':
                self._riemann_logs.append(line)
                if not self.pid:
                    match = re.match(pid_pattern, line)
                    if match:
                        self.pid = int(match.group(1))
                else:
                    match = re.match(started_pattern, line)
                    if match:
                        self._event.set()
                        break

    def start(self):
        logger.info("Starting riemann server...")
        self.pid = self._find_existing_riemann_process()
        if self.pid:
            logger.info("Riemann server is already running [pid={0}]".format(
                self.pid))
            return

        command = [
            'riemann',
            self._config_path
        ]
        self._process = subprocess.Popen(command,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT)
        self._event = threading.Event()
        self._detector = threading.Thread(target=self._start_detector,
                                          kwargs={'process': self._process})
        self._detector.daemon = True
        self._detector.start()
        timeout = 60
        if not self._event.wait(timeout):
            raise RuntimeError(
                "Unable to start riemann process:\n{0} (timed out after "
                "{1} seconds)".format('\n'.join(self._riemann_logs), timeout))
        logger.info("Riemann server started [pid={0}]".format(self.pid))

    def close(self):
        if self.pid:
            logger.info("Shutting down riemann server [pid={0}]".format(
                self.pid))
            os.system("kill {0}".format(self.pid))

    def _find_existing_riemann_process(self):
        from subprocess import CalledProcessError
        pattern = "\w*\s*(\d*).*"
        try:
            output = subprocess.check_output(
                "ps aux | grep 'riemann.jar' | grep -v grep", shell=True)
            match = re.match(pattern, output)
            if match:
                return int(match.group(1))
        except CalledProcessError:
            pass
        return None


class ElasticSearchProcess(object):
    """
    Manages an ElasticSearch server process lifecycle.
    """

    def __init__(self):
        self._pid = None
        self._process = None

    def _verify_service_responsiveness(self, timeout=120):
        import urllib2
        service_url = "http://localhost:9200"
        up = False
        deadline = time.time() + timeout
        res = None
        while time.time() < deadline:
            try:
                res = urllib2.urlopen(service_url)
                up = res.code == 200
                break
            except BaseException:
                pass
            time.sleep(1)
        if not up:
            raise RuntimeError("Elasticsearch service is not responding @ {"
                               "0} (response: {1})".format(service_url, res))

    def _verify_service_started(self, timeout=60):
        deadline = time.time() + timeout
        while time.time() < deadline:
            self._pid = self._get_service_pid()
            if self._pid is not None:
                break
            time.sleep(1)
        if self._pid is None:
            raise RuntimeError("Failed to start elasticsearch service within "
                               "a {0} seconds timeout".format(timeout))

    def _verify_service_ended(self, timeout=10):
        pid = self._pid
        deadline = time.time() + timeout
        while time.time() < deadline:
            pid = self._get_service_pid()
            if pid is None:
                break
            time.sleep(1)
        if pid is not None:
            raise RuntimeError("Failed to stop elasticsearch service within "
                               "a {0} seconds timeout".format(timeout))

    def _get_service_pid(self):
        from subprocess import CalledProcessError
        pattern = "\w*\s*(\d*).*"
        try:
            output = subprocess.check_output(
                "ps -ef | grep elasticsearch | grep -v grep", shell=True)
            match = re.match(pattern, output)
            if match:
                return int(match.group(1))
        except CalledProcessError:
            pass
        return None

    def start(self):
        command = 'elasticsearch'
        logger.info(
            "Starting elasticsearchservice with command {0}".format(command))
        self._process = subprocess.Popen(shlex.split(command))
        self._verify_service_started()
        self._verify_service_responsiveness()
        logger.info("Elasticsearch service started [pid=%s]", self._pid)
        self._remove_index_if_exists()
        self._create_schema()

    def close(self):
        if self._process:
            self._process.kill()
        if self._pid:
            logger.info("Shutting down elasticsearch service [pid=%s]",
                        self._pid)
            os.system("kill {0}".format(self._pid))
            self._verify_service_ended()

    def _remove_index_if_exists(self):
        es = elasticsearch.Elasticsearch()
        from elasticsearch.client import IndicesClient
        es_index = IndicesClient(es)
        if es_index.exists(STORAGE_INDEX_NAME):
            logger.info(
                "Elasticsearch index '{0}' already exists and "
                "will be deleted".format(STORAGE_INDEX_NAME))
            try:
                es_index.delete(STORAGE_INDEX_NAME)
                logger.info("Verifying Elasticsearch index was deleted...")
                deadline = time.time() + 45
                while es_index.exists(STORAGE_INDEX_NAME):
                    if time.time() > deadline:
                        raise RuntimeError(
                            'Elasticsearch index was not deleted after '
                            '30 seconds')
                    time.sleep(1)
            except BaseException as e:
                logger.warn('Ignoring caught exception on Elasticsearch delete'
                            ' index - {0}: {1}'.format(e.__class__, e.message))

    def reset_data(self):
        """
        Empties the storage index.
        """
        try:
            es = elasticsearch.Elasticsearch()
            es.delete_by_query(index=STORAGE_INDEX_NAME, q='*')
            deadline = time.time() + 45
            while es.count(index=STORAGE_INDEX_NAME, q='*')['count'] != 0:
                if time.time() > deadline:
                    raise RuntimeError(
                        'Elasticsearch data was not deleted after 30 seconds')
                time.sleep(1)
        except Exception as e:
            logger.warn(
                'Elasticsearch reset data failed: {0}'.format(e.message))

    def _create_schema(self):
        creator_script_path = path.join(path.dirname(__file__),
                                        'es_schema_creator.py')
        cmd = '{0} {1}'.format(sys.executable, creator_script_path)
        status = os.system(cmd)
        if status != 0:
            raise RuntimeError(
                'Elasticsearch create schema exited with {0}'.format(status))
        logger.info("Elasticsearch schema created successfully")


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
            raise AttributeError("Unknown test environment scope: " +
                                 str(scope))


def start_events_and_logs_polling():
    """
    Fetches events and logs from RabbitMQ.
    """
    if not RABBITMQ_POLLING_ENABLED:
        return

    pika_logger = logging.getLogger('pika')
    pika_logger.setLevel(logging.INFO)

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
                if 'context' in output and 'node_id' in output['context']:
                    output = '[{0}] {1}'.format(
                        output['context']['node_id'],
                        output['message']['text'])
                else:
                    output = output['message']['text']
            logger.info(output)
        except Exception as e:
            logger.info(
                "event/log format error - output: {0} [message={1}]".format(
                    body, e.message))

    def consume():
        channel.basic_consume(callback, queue=queues[0], no_ack=True)
        channel.basic_consume(callback, queue=queues[1], no_ack=True)
        channel.start_consuming()

    logger.info("Starting RabbitMQ events/logs polling - queues={0}".format(
        queues))

    polling_thread = threading.Thread(target=consume)
    polling_thread.daemon = True
    polling_thread.start()


class TestCase(unittest.TestCase):
    """
    A test case for cosmo tests.
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
        self.client = create_new_rest_client()
        TestEnvironment.clean_plugins_tempdir()

    def tearDown(self):
        TestEnvironment.restart_celery_operations_worker()
        TestEnvironment.restart_celery_workflows_worker()
        TestEnvironment.reset_elasticsearch_data()

    @staticmethod
    def do_assertions(assertions_func, timeout=10, *args, **kwargs):
        return do_retries(assertions_func, timeout, AssertionError, **kwargs)


class TestEnvironment(object):
    """
    Creates the cosmo test environment:
        - Riemann server.
        - Elasticsearch server.
        - Celery worker.
        - Ruote service.
        - Prepares celery app dir with plugins from cosmo module and official
          riemann configurer and plugin installer.
    """
    _instance = None
    _celery_operations_worker_process = None
    _celery_workflows_worker_process = None
    _riemann_process = None
    _elasticsearch_process = None
    _manager_rest_process = None
    _tempdir = None
    _plugins_tempdir = None
    _scope = None
    _file_server_process = None

    def __init__(self, scope, use_mock_workers_installation=True):
        try:
            TestEnvironmentScope.validate(scope)

            logger.info("Setting up test environment... [scope={0}]".format(
                scope))
            self._scope = scope

            # temp directory
            self._tempdir = tempfile.mkdtemp(suffix="test", prefix="cloudify")
            self._plugins_tempdir = path.join(self._tempdir, "cosmo-work")
            logger.info("Test environment will be stored in: %s",
                        self._tempdir)
            if not path.exists(self._plugins_tempdir):
                os.makedirs(self._plugins_tempdir)

            # events/logs polling
            start_events_and_logs_polling()

            # riemann
            riemann_config_path = path.join(self._tempdir, "riemann.config")
            self._generate_riemann_config(riemann_config_path)
            self._riemann_process = RiemannProcess(riemann_config_path)
            self._riemann_process.start()

            # elasticsearch
            self._elasticsearch_process = ElasticSearchProcess()
            self._elasticsearch_process.start()

            # copy all plugins to app path
            try:
                import workflows
                # workflows/__init__.py(c)
                workflow_plugin_path = path.abspath(workflows.__file__)
                # workflows/
                workflow_plugin_path = path.dirname(workflow_plugin_path)
                # package / egg folder
                workflow_plugin_path = path.dirname(workflow_plugin_path)
            except ImportError:
                # cloudify-manager/tests/plugins/__init__.py(c)
                workflow_plugin_path = path.abspath(plugins.__file__)
                # cloudify-manager/tests/plugins
                workflow_plugin_path = path.dirname(workflow_plugin_path)
                # cloudify-manager/tests
                workflow_plugin_path = path.dirname(workflow_plugin_path)
                # cloudify-manager
                workflow_plugin_path = path.dirname(workflow_plugin_path)
                # cloudify-manager/workflows
                workflow_plugin_path = path.join(workflow_plugin_path,
                                                 'workflows')

            plugins_path = path.dirname(path.realpath(plugins.__file__))
            mock_workflow_plugins = path.dirname(path.realpath(
                mock_workflows.__file__))

            app_path = path.join(self._tempdir, "plugins")
            # copying plugins
            if not use_mock_workers_installation:
                for plugin_path in [plugins_path, workflow_plugin_path]:
                    logger.info("Copying %s to %s", plugin_path, app_path)
                    distutils.dir_util.copy_tree(plugin_path, app_path)
            else:
                # copying plugins and mock workflows
                for plugin_path in [plugins_path, mock_workflow_plugins]:
                    logger.info("Copying %s to %s", plugin_path, app_path)
                    distutils.dir_util.copy_tree(plugin_path, app_path)
                # copying the actual default install/uninstall workflow
                # plugin manually
                workflow_plugin_workflows_path = path.join(
                    workflow_plugin_path, 'workflows')
                app_workflows_path = path.join(app_path, 'workflows')
                logger.info("Copying %s to %s",
                            workflow_plugin_workflows_path,
                            app_workflows_path)
                distutils.dir_util.copy_tree(
                    workflow_plugin_workflows_path, app_workflows_path)

            # celery operations worker
            # if using real worker installation workflow then 2 workers are
            # needed on the management queue
            num_of_management_workers = \
                1 if use_mock_workers_installation else 2
            self._celery_operations_worker_process = \
                CeleryOperationsWorkerProcess(
                    self._tempdir,
                    self._plugins_tempdir,
                    MANAGER_REST_PORT,
                    num_of_management_workers)
            self._celery_operations_worker_process.start()

            # celery workflows worker
            self._celery_workflows_worker_process = \
                CeleryWorkflowsWorkerProcess(
                    self._tempdir,
                    self._plugins_tempdir,
                    MANAGER_REST_PORT,
                    use_mock_workers_installation)
            self._celery_workflows_worker_process.start()

            # workaround to update path
            manager_rest_path = \
                path.dirname(path.dirname(path.dirname(__file__)))
            manager_rest_path = path.join(manager_rest_path, 'rest-service')
            sys.path.append(manager_rest_path)

            # file server
            fileserver_dir = path.join(self._tempdir, 'fileserver')
            os.mkdir(fileserver_dir)
            from manager_rest.file_server import FileServer
            from manager_rest.file_server import PORT as FS_PORT
            from manager_rest.util import copy_resources
            self._file_server_process = FileServer(fileserver_dir)
            self._file_server_process.start()

            # copy resources (base yaml/radials etc)
            resources_path = path.abspath(__file__)
            resources_path = path.dirname(resources_path)
            resources_path = path.dirname(resources_path)
            resources_path = path.dirname(resources_path)
            resources_path = path.join(resources_path, 'resources')
            copy_resources(fileserver_dir, resources_path)

            # manager rest
            file_server_base_uri = 'http://localhost:{0}'.format(FS_PORT)
            worker_service_base_uri = 'http://localhost:8101'
            self._manager_rest_process = ManagerRestProcess(
                MANAGER_REST_PORT,
                fileserver_dir,
                file_server_base_uri,
                worker_service_base_uri,
                FILE_SERVER_BLUEPRINTS_FOLDER,
                FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
                FILE_SERVER_RESOURCES_URI,
                self._tempdir)
            self._manager_rest_process.start()

        except BaseException as error:
            logger.error("Error in test environment setup: %s", error)
            self._destroy()
            raise

    def _destroy(self):
        logger.info("Destroying test environment... [scope={0}]".format(
            self._scope))
        if self._riemann_process:
            self._riemann_process.close()
        if self._elasticsearch_process:
            self._elasticsearch_process.close()
        if self._celery_operations_worker_process:
            self._celery_operations_worker_process.close()
        if self._celery_workflows_worker_process:
            self._celery_workflows_worker_process.close()
        if self._manager_rest_process:
            self._manager_rest_process.close()
        if self._file_server_process:
            self._file_server_process.stop()
        if self._tempdir:
            logger.info("Deleting test environment from: %s", self._tempdir)
            # shutil.rmtree(self._tempdir, ignore_errors=True)

    def _create_celery_worker(self, queue):
        return CeleryTestWorkerProcess(
            self._tempdir,
            self._plugins_tempdir,
            MANAGER_REST_PORT,
            queue)

    @staticmethod
    def create(scope=TestEnvironmentScope.PACKAGE,
               use_mock_workers_installation=True):
        """
        Creates the test environment if not already created.
        :param scope: The scope the test environment is created at.
        """
        if not TestEnvironment._instance:
            TestEnvironment._instance = TestEnvironment(
                scope,
                use_mock_workers_installation)
        return TestEnvironment._instance

    @staticmethod
    def destroy(scope=TestEnvironmentScope.PACKAGE):
        """
        Destroys the test environment if the provided scope matches the scope
        the environment was created with.
        :param scope: The scope this method is invoked from.
        """
        if TestEnvironment._instance and \
                (TestEnvironment._instance._scope == scope):
            TestEnvironment._instance._destroy()

    @staticmethod
    def clean_plugins_tempdir():
        """
        Removes and creates a new plugins temporary directory.
        """
        if TestEnvironment._instance:
            plugins_tempdir = TestEnvironment._instance._plugins_tempdir
            if path.exists(plugins_tempdir):
                shutil.rmtree(plugins_tempdir)
                os.makedirs(plugins_tempdir)

    @staticmethod
    def create_celery_worker(queue):
        if TestEnvironment._instance:
            return TestEnvironment._instance._create_celery_worker(queue)

    @staticmethod
    def restart_celery_operations_worker():
        if TestEnvironment._instance and \
                (TestEnvironment._instance._celery_operations_worker_process):
            TestEnvironment._instance._celery_operations_worker_process \
                .restart()

    @staticmethod
    def restart_celery_workflows_worker():
        if TestEnvironment._instance and \
                (TestEnvironment._instance._celery_workflows_worker_process):
            TestEnvironment._instance._celery_workflows_worker_process \
                .restart()

    @staticmethod
    def reset_elasticsearch_data():
        if TestEnvironment._instance and \
                TestEnvironment._instance._elasticsearch_process:
            TestEnvironment._instance._elasticsearch_process.reset_data()

    @classmethod
    def _generate_riemann_config(cls, riemann_config_path):
        source_path = get_resource('riemann/riemann.config')
        shutil.copy(source_path, riemann_config_path)


def create_rest_client():
    return CosmoManagerRestClient('localhost', port=MANAGER_REST_PORT)


def create_new_rest_client():
    return CloudifyClient('localhost', port=MANAGER_REST_PORT)


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


def run_search(query):
    client = create_rest_client()
    return client.run_search(query)


def wait_for_execution_to_end(execution, timeout=240):
    client = create_new_rest_client()
    deadline = time.time() + timeout
    while execution.status not in ['terminated', 'failed']:
        time.sleep(1)
        execution = client.executions.get(execution.id)
        if time.time() > deadline:
            raise TimeoutException()
    if execution.status == 'failed':
        raise RuntimeError(
            'Workflow execution failed: {0} [{1}]'.format(execution.error,
                                                          execution.status))
    return execution


def deploy_application(dsl_path,
                       timeout=240,
                       blueprint_id=None,
                       deployment_id=None,
                       wait_for_execution=True):
    """
    A blocking method which deploys an application from the provided dsl path.
    """
    client = create_new_rest_client()
    if not blueprint_id:
        blueprint_id = str(uuid.uuid4())
    blueprint = client.blueprints.upload(dsl_path, blueprint_id)
    if deployment_id is None:
        deployment_id = str(uuid.uuid4())
    deployment = client.deployments.create(blueprint.id, deployment_id)

    do_retries(verify_workers_installation_complete, 30,
               deployment_id=deployment_id)

    execution = client.deployments.execute(deployment_id, 'install')

    if wait_for_execution:
        execution = wait_for_execution_to_end(execution, timeout=timeout)
        return deployment, execution.id

    return deployment, execution.id


def verify_workers_installation_complete(deployment_id):
    # a workaround for waiting for the workers installation to complete
    client = create_new_rest_client()
    execs = client.deployments.list_executions(deployment_id)
    if not execs \
        or execs[0].status != 'terminated' \
            or execs[0].workflow_id != 'workers_installation':
        raise RuntimeError(
            "Expected a single execution for workflow "
            "'workers_installation' with status 'terminated'; "
            "Found these executions instead: {0}".format(execs))


def undeploy_application(deployment_id, timeout=240):
    """
    A blocking method which undeploys an application from the provided dsl
    path.
    """
    client = create_new_rest_client()
    execution = client.deployments.execute(deployment_id,
                                           'uninstall')
    wait_for_execution_to_end(execution, timeout=timeout)

    if execution.error and execution.error != 'None':
        raise RuntimeError(
            'Workflow execution failed: {0}'.format(execution.error))


def post_provider_context(name, provider_context):
    client = create_rest_client()
    return client.post_provider_context(name, provider_context)


def get_provider_context():
    client = create_rest_client()
    return client.get_provider_context()


def is_node_started(node_id):
    client = create_new_rest_client()
    node_instance = client.node_instances.get(node_id)
    return node_instance['state'] == 'started'


class TimeoutException(Exception):
    def __init__(self, *args):
        Exception.__init__(self, args)


def do_retries(func, timeout=10, exception_class=BaseException, **kwargs):
    deadline = time.time() + timeout
    while True:
        try:
            func(**kwargs)
            break
        except exception_class:
            if time.time() > deadline:
                raise
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


def send_task(task, args=None, queue=CLOUDIFY_MANAGEMENT_QUEUE):
    task_name = task.name.replace("plugins.", "")
    return celery.send_task(
        name=task_name,
        args=args,
        queue=queue)
