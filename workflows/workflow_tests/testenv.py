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
from os.path import dirname, abspath
import unittest

__author__ = 'idanmo'

import yaml
import shutil
import tempfile
from os import path
import subprocess
import logging
import os
import sys
import plugins
import time
import threading
import re
import pika
import json
from cosmo_manager_rest_client.cosmo_manager_rest_client \
    import CosmoManagerRestClient
from celery import Celery
from cloudify.constants import MANAGEMENT_NODE_ID

CLOUDIFY_MANAGEMENT_QUEUE = MANAGEMENT_NODE_ID

STORAGE_FILE_PATH = '/tmp/manager-rest-tests-storage.json'

root = logging.getLogger()
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter(fmt='%(asctime)s [%(levelname)s] %(message)s',
                              datefmt='%H:%M:%S')
ch.setFormatter(formatter)
root.addHandler(ch)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

RABBITMQ_POLLING_KEY = 'RABBITMQ_POLLING'

RABBITMQ_POLLING_ENABLED = RABBITMQ_POLLING_KEY not in os.environ\
    or os.environ[RABBITMQ_POLLING_KEY].lower() != 'false'

celery = Celery(broker='amqp://',
                backend='amqp://')

# set the client celery to send tasks to the worker queue.
celery.conf.update(
    CELERY_TASK_SERIALIZER="json"
)


class ManagerRestProcess(object):

    def __init__(self,
                 port,
                 file_server_dir,
                 file_server_base_uri,
                 workflow_service_base_uri,
                 storage_file_path):
        self.process = None
        self.port = port
        self.file_server_dir = file_server_dir
        self.file_server_base_uri = file_server_base_uri
        self.workflow_service_base_uri = workflow_service_base_uri
        self.storage_file_path = storage_file_path
        self.client = CosmoManagerRestClient('localhost')

    def start(self, timeout=10):
        endtime = time.time() + timeout

        configuration = {
            'file_server_root': self.file_server_dir,
            'file_server_base_uri': self.file_server_base_uri,
            'workflow_service_base_uri': self.workflow_service_base_uri
        }

        config_path = tempfile.mktemp()
        with open(config_path, 'w') as f:
            f.write(yaml.dump(configuration))

        env = os.environ.copy()
        env['MANAGER_REST_CONFIG_PATH'] = config_path

        python_path = sys.executable

        manager_rest_command = [
            '{0}/gunicorn'.format(dirname(python_path)),
            '-w', '1',
            '-b', '0.0.0.0:{0}'.format(self.port),
            '--timeout', '300',
            'server:app'
        ]

        logger.info('Starting manager-rest with: {0}'
                    .format(manager_rest_command))

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
            self.reset_data()
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
        if not self.process is None:
            self.process.terminate()

    def reset_data(self):
        if os.path.isfile(self.storage_file_path):
            os.remove(self.storage_file_path)

    def locate_manager_rest_dir(self):
        # start with current location
        manager_rest_location = path.abspath(__file__)
        # get to cosmo-manager
        for i in range(3):
            manager_rest_location = path.dirname(manager_rest_location)
        # build way into manager_rest
        return path.join(manager_rest_location,
                         'manager-rest/manager_rest')


class RuoteServiceProcess(object):

    JRUBY_VERSION = '1.7.3'

    def __init__(self, port=8101):
        self._pid = None
        self._port = port
        self._use_rvm = self._verify_ruby_environment()
        self._process = None

    def _get_installed_ruby_packages(self):
        pass

    def _verify_ruby_environment(self):
        """ Verifies there's a valid JRuby environment.
        RuntimeError is raised if not, otherwise returns a boolean
        value which indicates whether RVM should be used for changing the
         current ruby environment before starting the service.
        """
        command = ['ruby', '--version']
        try:
            if self.JRUBY_VERSION in subprocess.check_output(command):
                return False
        except subprocess.CalledProcessError:
            pass

        command = ['rvm', 'list']
        jruby_version = "jruby-{0}".format(self.JRUBY_VERSION)
        try:
            if jruby_version in subprocess.check_output(command):
                return True
        except subprocess.CalledProcessError:
            pass

        raise RuntimeError("Invalid ruby environment [required -> JRuby {0}]"
                           .format(self.JRUBY_VERSION))

    def _verify_service_responsiveness(self, timeout=120):
        import urllib2
        service_url = "http://localhost:{0}".format(self._port)
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
            raise RuntimeError("Ruote service is not responding @ {0} "
                               "(response: {1})".format(service_url, res))

    def _verify_service_started(self, timeout=30):
        deadline = time.time() + timeout
        while time.time() < deadline:
            self._pid = self._get_serice_pid()
            if self._pid is not None:
                break
            time.sleep(1)
        if self._pid is None:
            raise RuntimeError("Failed to start ruote service within a {0} "
                               "seconds timeout".format(timeout))

    def _verify_service_ended(self, timeout=10):
        pid = self._pid
        deadline = time.time() + timeout
        while time.time() < deadline:
            pid = self._get_serice_pid()
            if pid is None:
                break
            time.sleep(1)
        if pid is not None:
            raise RuntimeError("Failed to stop ruote service within a {0} "
                               "seconds timeout".format(timeout))

    def _get_serice_pid(self):
        from subprocess import CalledProcessError
        pattern = "\w*\s*(\d*).*"
        try:
            output = subprocess.check_output(
                "ps aux | grep 'rackup' | grep -v grep", shell=True)
            match = re.match(pattern, output)
            if match:
                return int(match.group(1))
        except CalledProcessError:
            pass
        return None

    def start(self):
        startup_script_path = path.realpath(path.join(path.dirname(__file__),
                                                      '..'))
        script = path.join(startup_script_path, 'run_ruote_service.sh')
        command = [script, str(self._use_rvm).lower(), str(self._port)]
        env = os.environ.copy()
        logger.info("Starting Ruote service with command {0}".format(command))
        self._process = subprocess.Popen(command,
                                         cwd=startup_script_path,
                                         env=env)
        self._verify_service_started(timeout=30)
        self._verify_service_responsiveness()
        logger.info("Ruote service started [pid=%s]", self._pid)

    def close(self):
        if self._process:
            self._process.kill()
        if self._pid:
            logger.info("Shutting down Ruote service [pid=%s]", self._pid)
            os.system("kill {0}".format(self._pid))
            self._verify_service_ended()


class CeleryWorkerProcess(object):
    _process = None

    def __init__(self, tempdir, plugins_tempdir, cosmo_path,
                 riemann_config_path, riemann_template_path, riemann_pid,
                 manager_rest_port):
        self._celery_pid_file = path.join(tempdir, "celery.pid")
        self._cosmo_path = cosmo_path
        self._app_path = path.join(tempdir, "plugins")
        self._tempdir = tempdir
        self._plugins_tempdir = plugins_tempdir
        self._cosmo_plugins = self._app_path
        self._riemann_config_path = riemann_config_path
        self._riemann_template_path = riemann_template_path
        self._riemann_pid = riemann_pid
        self._manager_rest_port = manager_rest_port

    def _build_includes(self):

        # mandatory REAL plugins for the tests framework
        includes = ['plugin_installer.tasks']

        # iterate over the mock plugins directory and include all of them
        mock_plugins_path = os.path\
            .join(dirname(dirname(abspath(__file__))), "plugins")

        for plugin_dir_name in os.walk(mock_plugins_path).next()[1]:
            tasks_path = os.path\
                .join(mock_plugins_path, plugin_dir_name, "tasks.py")
            if os.path.exists(tasks_path):
                includes.append("{0}.tasks".format(plugin_dir_name))
            else:
                logger.warning("Could not find tasks.py file under plugin {0}."
                               " This plugin will not be loaded!"
                               .format(plugin_dir_name))

        return includes

    def _copy_cosmo_plugins(self):
        import plugin_installer
        self._copy_plugin(plugin_installer)

    def _copy_plugin(self, plugin):
        installed_plugin_path = path.dirname(plugin.__file__)
        self._create_python_module_path(self._cosmo_plugins)
        target = path.join(self._cosmo_plugins, plugin.__name__)
        shutil.copytree(installed_plugin_path, target)
        self._remove_test_dir_if_exists(target)

    def _remove_test_dir_if_exists(self, plugin_path):
        tests_dir = path.join(plugin_path, 'tests')
        if path.isdir(tests_dir):
            shutil.rmtree(tests_dir)

    def _create_python_module_path(self, module_path):
        if not path.exists(module_path):
            os.makedirs(module_path)
        while not path.exists(path.join(module_path, "__init__.py")):
            with open(path.join(module_path, "__init__.py"), "w") as f:
                f.write("")
            module_path = path.realpath(path.join(module_path, ".."))

    def start(self):
        logger.info("Copying %s to %s", self._cosmo_path, self._app_path)
        shutil.copytree(self._cosmo_path, self._app_path)
        logger.info("Copying cosmo plugins")
        self._copy_cosmo_plugins()
        celery_log_file = path.join(self._tempdir, "celery.log")
        python_path = sys.executable
        logger.info("Building includes list for celery worker")
        includes = self._build_includes()
        celery_command = [
            "{0}/celery".format(dirname(python_path)),
            "worker",
            "--events",
            "--loglevel=debug",
            "--hostname=celery.{0}".format(MANAGEMENT_NODE_ID),
            "--purge",
            "--app=cloudify",
            "--logfile={0}".format(celery_log_file),
            "--pidfile={0}".format(self._celery_pid_file),
            "--queues={0}".format(CLOUDIFY_MANAGEMENT_QUEUE),
            "--concurrency=1",
            "--include={0}".format(','.join(includes))
        ]

        os.chdir(os.path.join(self._tempdir, "plugins"))

        environment = os.environ.copy()
        environment['TEMP_DIR'] = self._plugins_tempdir
        environment['RIEMANN_PID'] = str(self._riemann_pid)
        environment['RIEMANN_CONFIG'] = self._riemann_config_path
        environment['RIEMANN_CONFIG_TEMPLATE'] = self._riemann_template_path
        environment['MANAGER_REST_PORT'] = self._manager_rest_port
        environment['MANAGEMENT_IP'] = 'localhost'
        environment['AGENT_IP'] = 'localhost'
        environment['VIRTUALENV'] = dirname(dirname(python_path))

        logger.info("Starting celery worker with command {0}"
                    .format(celery_command))
        self._process = subprocess.Popen(celery_command, env=environment)

        timeout = 30
        deadline = time.time() + timeout
        while not path.exists(self._celery_pid_file) and \
                (time.time() < deadline):
            time.sleep(1)

        if not path.exists(self._celery_pid_file):
            if path.exists(celery_log_file):
                with open(celery_log_file, "r") as f:
                    celery_log = f.read()
                    logger.info("{0} content:\n{1}".format(celery_log_file,
                                                           celery_log))
            raise RuntimeError("Failed to start celery worker: {0} - process "
                               "did not start after {1} seconds"
                               .format(self._process.returncode, timeout))

        logger.info("Celery worker started [pid=%s]", self._process.pid)

    def close(self):
        if self._process:
            logger.info("Shutting down celery worker [pid=%s]",
                        self._process.pid)
            self._process.kill()

    @staticmethod
    def _get_celery_process_ids():
        from subprocess import CalledProcessError
        try:
            output = subprocess.check_output(
                "ps aux | grep 'celery' | grep -v grep | awk '{print $2}'",
                shell=True)
            ids = filter(lambda x: len(x) > 0, output.split(os.linesep))
            return ids
        except CalledProcessError:
            return []

    def restart(self):
        """
        Restarts the single celery worker process.
        Celery's child process will have a different PID.
        """
        process_ids = self._get_celery_process_ids()
        celery.control.broadcast('pool_shrink', arguments={'N': 0})
        celery.control.broadcast('pool_grow', arguments={'N': 1})
        timeout = time.time() + 30
        while self._get_celery_process_ids() == process_ids:
            time.sleep(1)
            if time.time() > timeout:
                raise RuntimeError(
                    'Celery worker restart timeout '
                    '[current_ids={0}, previous_ids={1}'.format(
                        self._get_celery_process_ids(), process_ids))


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
            logger.info("Riemann server is already running [pid={0}]"
                        .format(self.pid))
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
        timeout = 30
        if not self._event.wait(timeout):
            raise RuntimeError("Unable to start riemann process:\n{0} "
                               "(timed out after {1} seconds)"
                               .format('\n'.join(self._riemann_logs), timeout))
        logger.info("Riemann server started [pid={0}]".format(self.pid))

    def close(self):
        if self.pid:
            logger.info("Shutting down riemann server [pid={0}]"
                        .format(self.pid))
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
            output = json.dumps(output, indent=4)
            logger.info("\n{0}".format(output))
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


class TestEnvironment(object):
    """
    Creates the cosmo test environment:
        - Riemann server.
        - Celery worker.
        - Ruote service.
        - Prepares celery app dir with plugins from cosmo module and official
          riemann configurer and plugin installer.
    """
    _instance = None
    _celery_worker_process = None
    _riemann_process = None
    _manager_rest_process = None
    _tempdir = None
    _plugins_tempdir = None
    _scope = None
    _ruote_service = None
    _file_server_process = None

    def __init__(self, scope):
        try:
            TestEnvironmentScope.validate(scope)

            logger.info("Setting up test environment... [scope={0}]"
                        .format(scope))
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
            riemann_template_path = path.join(self._tempdir,
                                              "riemann.config.template")
            self._generate_riemann_config(riemann_config_path,
                                          riemann_template_path)
            self._riemann_process = RiemannProcess(riemann_config_path)
            self._riemann_process.start()

            manager_rest_port = '8100'

            # celery
            plugins_path = path.dirname(path.realpath(plugins.__file__))
            self._celery_worker_process = CeleryWorkerProcess(
                self._tempdir, self._plugins_tempdir, plugins_path,
                riemann_config_path, riemann_template_path,
                self._riemann_process.pid,
                manager_rest_port)
            self._celery_worker_process.start()
            self.storage_file_path = STORAGE_FILE_PATH

            # workaround to update path
            manager_rest_path = \
                path.dirname(path.dirname(path.dirname(__file__)))
            manager_rest_path = path.join(manager_rest_path, 'manager-rest')
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
            orchestrator_location = path.abspath(__file__)
            for i in range(3):
                orchestrator_location = path.dirname(orchestrator_location)
            orchestrator_location = path.join(orchestrator_location,
                                              'orchestrator')
            copy_resources(fileserver_dir, orchestrator_location)

            # manager rest
            file_server_base_uri = 'http://localhost:{0}'.format(FS_PORT)
            worker_service_base_uri = 'http://localhost:8101'
            self._manager_rest_process = ManagerRestProcess(
                manager_rest_port,
                fileserver_dir,
                file_server_base_uri,
                worker_service_base_uri,
                self.storage_file_path)
            self._manager_rest_process.start()

            # ruote service
            self._ruote_service = RuoteServiceProcess()

            self._ruote_service.start()

        except BaseException as error:
            logger.error("Error in test environment setup: %s", error)
            self._destroy()
            raise error

    def _destroy(self):
        logger.info("Destroying test environment... [scope={0}]"
                    .format(self._scope))
        if self._riemann_process:
            self._riemann_process.close()
        if self._celery_worker_process:
            self._celery_worker_process.close()
        if self._manager_rest_process:
            self._manager_rest_process.close()
        if self._ruote_service:
            self._ruote_service.close()
        if self._file_server_process:
            self._file_server_process.stop()
        if self._tempdir:
            logger.info("Deleting test environment from: %s", self._tempdir)
            shutil.rmtree(self._tempdir, ignore_errors=True)

    @staticmethod
    def create(scope=TestEnvironmentScope.PACKAGE):
        """
        Creates the test environment if not already created.
        :param scope: The scope the test environment is created at.
        """
        if not TestEnvironment._instance:
            TestEnvironment._instance = TestEnvironment(scope)
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
    def restart_celery_worker():
        if TestEnvironment._instance and \
           (TestEnvironment._instance._celery_worker_process):
            TestEnvironment._instance._celery_worker_process.restart()

    @staticmethod
    def reset_rest_manager_data():
        if TestEnvironment._instance and \
           TestEnvironment._instance._manager_rest_process:
            TestEnvironment._instance._manager_rest_process.reset_data()

    @classmethod
    def _generate_riemann_config(cls, riemann_config_path,
                                 riemann_template_path):
        source_path = get_resource('riemann/riemann.config')
        shutil.copy(source_path, riemann_config_path)
        source_path = get_resource('riemann/riemann.config.template')
        shutil.copy(source_path, riemann_template_path)


class TestCase(unittest.TestCase):
    """
    A test case for cosmo workflow tests.
    """

    @classmethod
    def setUpClass(cls):
        TestEnvironment.create(TestEnvironmentScope.CLASS)

    @classmethod
    def tearDownClass(cls):
        TestEnvironment.destroy(TestEnvironmentScope.CLASS)

    def setUp(self):
        TestEnvironment.clean_plugins_tempdir()

    def tearDown(self):
        TestEnvironment.restart_celery_worker()
        TestEnvironment.reset_rest_manager_data()

    def send_task(self, task, args=None):
        task_name = task.name.replace("plugins.", "")
        return celery.send_task(
            name=task_name,
            args=args,
            queue=CLOUDIFY_MANAGEMENT_QUEUE)


def get_resource(resource):
    """
    Gets the path for the provided resource.
    :param resource: resource name relative to /resources.
    """
    import resources
    resources_path = path.dirname(resources.__file__)
    resource_path = path.join(resources_path, resource)
    if not path.exists(resource_path):
        raise RuntimeError("Resource '{0}' not found in: {1}"
                           .format(resource, resource_path))
    return resource_path


def deploy_application(dsl_path, timeout=240):
    """
    A blocking method which deploys an application from the provided dsl path.
    """
    client = CosmoManagerRestClient('localhost')
    blueprint_id = client.publish_blueprint(dsl_path).id
    deployment = client.create_deployment(blueprint_id)
    client.execute_deployment(deployment.id, 'install', timeout=timeout)
    return deployment


def undeploy_application(deployment_id, timeout=240):
    """
    A blocking method which undeploys an application from the provided dsl
    path.
    """
    client = CosmoManagerRestClient('localhost')
    client.execute_deployment(deployment_id, 'uninstall', timeout=timeout)


def validate_dsl(blueprint_id, timeout=240):
    """
    A blocking method which validates a dsl from the provided dsl path.
    """
    client = CosmoManagerRestClient('localhost')
    response = client.validate_blueprint(blueprint_id)
    if response.status != 'valid':
        raise RuntimeError('Blueprint {0} is not valid (status: {1})'
                           .format(blueprint_id, response.status))


def get_deployment_workflows(deployment_id):
    client = CosmoManagerRestClient('localhost')
    return client.list_workflows(deployment_id)


def get_nodes():
    client = CosmoManagerRestClient('localhost')
    nodes = client.list_nodes()['nodes']
    return nodes


def get_deployment_nodes(deployment_id, get_reachable_state=False):
    client = CosmoManagerRestClient('localhost')
    deployment_nodes = client.list_deployment_nodes(
        deployment_id, get_reachable_state)
    return deployment_nodes


def get_node_state(node_id, get_reachable_state=False, get_runtime_state=True):
    client = CosmoManagerRestClient('localhost')
    state = client.get_node_state(node_id,
                                  get_reachable_state=get_reachable_state,
                                  get_runtime_state=get_runtime_state)
    return state['runtimeInfo']


def is_node_reachable(node_id):
    client = CosmoManagerRestClient('localhost')
    state = client.get_node_state(node_id, get_reachable_state=True,
                                  get_runtime_state=False)
    return state['reachable'] is True


class TimeoutException(Exception):
    def __init__(self, *args):
        Exception.__init__(self, args)
