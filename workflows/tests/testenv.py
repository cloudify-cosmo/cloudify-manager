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

__author__ = 'idanmo'

import unittest
import shutil
import tempfile
from os import path
import subprocess
import logging
import os
import sys
import cosmo
import time
import threading
import re
import requests

root = logging.getLogger()
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter(fmt='%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
ch.setFormatter(formatter)
root.addHandler(ch)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ManagerRestProcess(object):

    def __init__(self, port, workflow_service_base_uri, events_path):
        self.process = None
        self.port = port
        self.workflow_service_base_uri = workflow_service_base_uri
        self.events_path = events_path

    def start(self, timeout=10):
        endtime = time.time() + timeout

        manager_rest_command = [
            sys.executable,
            self.locate_manager_rest(),
            '--port', self.port,
            '--workflow_service_base_uri', self.workflow_service_base_uri,
            '--events_files_path', self.events_path
        ]

        logger.info('Starting manager-rest with: {0}'.format(manager_rest_command))

        self.process = subprocess.Popen(manager_rest_command)
        started = False
        attempt = 1
        while not started and time.time() < endtime:
            time.sleep(1)
            logger.info('Testing connection to manager rest service. (Attempt: {0}/{1})'.format(attempt, timeout))
            attempt += 1
            started = self.started()
        if not started:
            raise RuntimeError('Failed opening connection to manager rest service')

    def started(self):
        try:
            requests.get('http://localhost:8100/blueprints')
            return True
        except BaseException:
            return False

    def close(self):
        if not self.process is None:
            self.process.terminate()

    def locate_manager_rest(self):
        # start with current location
        manager_rest_location = path.abspath(__file__)
        # get to cosmo-manager
        for i in range(3):
            manager_rest_location = path.dirname(manager_rest_location)
        # build way into manager_rest
        return path.join(manager_rest_location, 'manager-rest/manager_rest/server.py')


class RuoteServiceProcess(object):

    JRUBY_VERSION = '1.7.3'

    def __init__(self, port=8101, events_path=None):
        self._pid = None
        self._port = port
        self._use_rvm = self._verify_ruby_environment()
        self._events_path = events_path
        self._process = None

    def _get_installed_ruby_packages(self):
        pass

    def _verify_ruby_environment(self):
        """ Verifies there's a valid JRuby environment.
        RuntimeError is raised if not, otherwise returns a boolean value which indicates
        whether RVM should be used for changing the current ruby environment before starting the service.
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

        raise RuntimeError("Invalid ruby environment [required -> JRuby {0}]".format(self.JRUBY_VERSION))

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
            raise RuntimeError("Ruote service is not responding @ {0} (response: {1})".format(service_url, res))

    def _verify_service_started(self, timeout=30):
        deadline = time.time() + timeout
        while time.time() < deadline:
            self._pid = self._get_serice_pid()
            if self._pid is not None:
                break
            time.sleep(1)
        if self._pid is None:
            raise RuntimeError("Failed to start ruote service within a {0} seconds timeout".format(timeout))

    def _verify_service_ended(self, timeout=10):
        pid = self._pid
        deadline = time.time() + timeout
        while time.time() < deadline:
            pid = self._get_serice_pid()
            if pid is None:
                break
            time.sleep(1)
        if pid is not None:
            raise RuntimeError("Failed to stop ruote service within a {0} seconds timeout".format(timeout))

    def _get_serice_pid(self):
        from subprocess import CalledProcessError
        pattern = "\w*\s*(\d*).*"
        try:
            output = subprocess.check_output("ps aux | grep 'rackup' | grep -v grep", shell=True)
            match = re.match(pattern, output)
            if match:
                return int(match.group(1))
        except CalledProcessError:
            pass
        return None

    def start(self):
        startup_script_path = path.realpath(path.join(path.dirname(__file__), '..'))
        script = path.join(startup_script_path, 'run_ruote_service.sh')
        command = [script, str(self._use_rvm).lower(), str(self._port)]
        env = os.environ.copy()
        if self._events_path is not None:
            env['WF_SERVICE_LOGS_PATH'] = self._events_path
        logger.info("Starting Ruote service")
        self._process = subprocess.Popen(command, cwd=startup_script_path, env=env)
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

    def __init__(self, tempdir, plugins_tempdir, cosmo_path, cosmo_jar_path, riemann_config_path,
                 riemann_template_path, riemann_pid, manager_rest_port):
        self._celery_pid_file = path.join(tempdir, "celery.pid")
        self._cosmo_path = cosmo_path
        self._app_path = path.join(tempdir, "cosmo")
        self._tempdir = tempdir
        self._plugins_tempdir = plugins_tempdir
        self._cosmo_plugins = path.join(self._app_path, "cloudify/plugins")
        self._cosmo_jar_path = cosmo_jar_path
        self._riemann_config_path = riemann_config_path
        self._riemann_template_path = riemann_template_path
        self._riemann_pid = riemann_pid
        self._manager_rest_port = manager_rest_port

    def _copy_cosmo_plugins(self):
        import riemann_config_loader
        import plugin_installer
        self._copy_plugin(riemann_config_loader)
        self._copy_plugin(plugin_installer)

    def _copy_plugin(self, plugin):
        installed_plugin_path = path.dirname(plugin.__file__)
        self._create_python_module_path(self._cosmo_plugins)
        shutil.copytree(installed_plugin_path, path.join(self._cosmo_plugins, plugin.__name__))

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
        self._copy_cosmo_plugins()
        celery_log_file = path.join(self._tempdir, "celery.log")
        celery_command = [
            "celery",
            "worker",
            "--events",
            "--loglevel=debug",
            "--app=cosmo",
            "--hostname=celery.cloudify.management",
            "--purge",
            "--logfile={0}".format(celery_log_file),
            "--pidfile={0}".format(self._celery_pid_file),
            "--queues=cloudify.management",
            "--concurrency=1"
        ]

        os.chdir(self._tempdir)

        environment = os.environ.copy()
        environment['TEMP_DIR'] = self._plugins_tempdir
        environment['COSMO_JAR'] = self._cosmo_jar_path
        environment['RIEMANN_PID'] = str(self._riemann_pid)
        environment['RIEMANN_CONFIG'] = self._riemann_config_path
        environment['RIEMANN_CONFIG_TEMPLATE'] = self._riemann_template_path
        environment['MANAGER_REST_PORT'] = self._manager_rest_port

        logger.info("Starting celery worker...")
        self._process = subprocess.Popen(celery_command, env=environment)

        timeout = 30
        deadline = time.time() + timeout
        while not path.exists(self._celery_pid_file) and time.time() < deadline:
            time.sleep(1)

        if not path.exists(self._celery_pid_file):
            if path.exists(celery_log_file):
                with open(celery_log_file, "r") as f:
                    celery_log = f.read()
                    logger.info("{0} content:\n{1}".format(celery_log_file, celery_log))
            raise RuntimeError("Failed to start celery worker: {0} - process did not start after {1} seconds".format(
                self._process.returncode,
                timeout))

        logger.info("Celery worker started [pid=%s]", self._process.pid)

    def close(self):
        if self._process:
            logger.info("Shutting down celery worker [pid=%s]", self._process.pid)
            self._process.kill()

    def restart(self):
        """
        Restarts the single celery worker process.
        Does not change the pid of celery itself
        """
        from cosmo.celery import celery
        celery.control.broadcast('pool_shrink', arguments={'N': 0})
        celery.control.broadcast('pool_grow', arguments={'N': 1})


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
            logger.info("Riemann server is already running [pid={0}]".format(self.pid))
            return
        command = [
            'riemann',
            self._config_path
        ]
        self._process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self._event = threading.Event()
        self._detector = threading.Thread(target=self._start_detector, kwargs={'process': self._process})
        self._detector.daemon = True
        self._detector.start()
        timeout = 30
        if not self._event.wait(timeout):
            raise RuntimeError("Unable to start riemann process:\n{0} (timed out after {1} seconds)".format('\n'.join(
                self._riemann_logs), timeout))
        logger.info("Riemann server started [pid={0}]".format(self.pid))

    def close(self):
        if self.pid:
            logger.info("Shutting down riemann server [pid={0}]".format(self.pid))
            os.system("kill {0}".format(self.pid))

    def _find_existing_riemann_process(self):
        from subprocess import CalledProcessError
        pattern = "\w*\s*(\d*).*"
        try:
            output = subprocess.check_output("ps aux | grep 'riemann.jar' | grep -v grep", shell=True)
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
            raise AttributeError("Unknown test environment scope: " + str(scope))


class TestEnvironment(object):
    """
    Creates the cosmo test environment:
        - Riemann server.
        - Celery worker.
        - Ruote service (created for each test because of StateCache state).
        - Prepares celery app dir with plugins from cosmo module and official riemann configurer and plugin installer.
    """
    _instance = None
    _celery_worker_process = None
    _riemann_process = None
    _manager_rest_process = None
    _tempdir = None
    _plugins_tempdir = None
    _scope = None

    def __init__(self, scope):
        try:
            TestEnvironmentScope.validate(scope)

            logger.info("Setting up test environment... [scope={0}]".format(scope))
            self._scope = scope

            # temp directory
            self._tempdir = tempfile.mkdtemp(suffix="test", prefix="cloudify")
            self._plugins_tempdir = path.join(self._tempdir, "cosmo-work")
            logger.info("Test environment will be stored in: %s", self._tempdir)
            cosmo_jar_path = self._get_cosmo_jar_path()
            if not path.exists(self._plugins_tempdir):
                os.makedirs(self._plugins_tempdir)

            # riemann
            riemann_config_path = path.join(self._tempdir, "riemann.config")
            riemann_template_path = path.join(self._tempdir, "riemann.config.template")
            self._generate_riemann_config(riemann_config_path, riemann_template_path)
            self._riemann_process = RiemannProcess(riemann_config_path)
            self._riemann_process.start()

            manager_rest_port = '8100'

            # celery
            cosmo_path = path.dirname(path.realpath(cosmo.__file__))
            self._celery_worker_process = CeleryWorkerProcess(self._tempdir, self._plugins_tempdir, cosmo_path,
                                                              cosmo_jar_path,
                                                              riemann_config_path, riemann_template_path,
                                                              self._riemann_process.pid,
                                                              manager_rest_port)
            self._celery_worker_process.start()

            # set events path (wf_service -> write, manager_rest -> read)
            self.events_path = path.join(self._tempdir, 'events')

            # manager rest
            worker_service_base_uri = 'http://localhost:8101'
            self._manager_rest_process = ManagerRestProcess(manager_rest_port,
                                                            worker_service_base_uri,
                                                            self.events_path)
            self._manager_rest_process.start()

        except BaseException as error:
            logger.error("Error in test environment setup: %s", error)
            self._destroy()
            raise error

    def _destroy(self):
        logger.info("Destroying test environment... [scope={0}]".format(self._scope))
        if self._riemann_process:
            self._riemann_process.close()
        if self._celery_worker_process:
            self._celery_worker_process.close()
        if self._manager_rest_process:
            self._manager_rest_process.close()
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
        Destroys the test environment if the provided scope matches the scope the environment was created with.
        :param scope: The scope this method is invoked from.
        """
        if TestEnvironment._instance and TestEnvironment._instance._scope == scope:
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
            if path.exists(TestEnvironment._instance.events_path):
                shutil.rmtree(TestEnvironment._instance.events_path)

    @staticmethod
    def restart_celery_worker():
        if TestEnvironment._instance and TestEnvironment._instance._celery_worker_process:
            TestEnvironment._instance._celery_worker_process.restart()

    @staticmethod
    def kill_cosmo_process():
        """
        Kills 'cosmo.jar' process if it exists.
        """
        pattern = "\w*\s*(\d*).*"
        try:
            output = subprocess.check_output("ps aux | grep 'cosmo.jar' | grep -v grep", shell=True)
            match = re.match(pattern, output)
            if match:
                pid = match.group(1)
                logger.info("'cosmo.jar' process is still running [pid={0}] - terminating...".format(pid))
                os.system("kill {0}".format(pid))
        except BaseException:
            pass

    @classmethod
    def _get_cosmo_jar_path(cls):
        cosmo_jar_path = path.realpath(path.join(path.dirname(__file__), '../../orchestrator/target/cosmo.jar'))
        if not path.exists(cosmo_jar_path):
            raise RuntimeError("cosmo.jar not found in: {0}".format(cosmo_jar_path))
        return cosmo_jar_path

    @classmethod
    def _generate_riemann_config(cls, riemann_config_path, riemann_template_path):
        source_path = get_resource('riemann/riemann.config')
        shutil.copy(source_path, riemann_config_path)
        source_path = get_resource('riemann/riemann.config.template')
        shutil.copy(source_path, riemann_template_path)


class TestCase(unittest.TestCase):
    """
    A test case for cosmo workflow tests.
    """

    _ruote_service = None

    @classmethod
    def setUpClass(cls):
        TestEnvironment.create(TestEnvironmentScope.CLASS)

    @classmethod
    def tearDownClass(cls):
        TestEnvironment.destroy(TestEnvironmentScope.CLASS)

    def setUp(self):
        TestEnvironment.clean_plugins_tempdir()
        self._ruote_service = RuoteServiceProcess(events_path=TestEnvironment._instance.events_path)
        self._ruote_service.start()

    def tearDown(self):
        if self._ruote_service:
            self._ruote_service.close()
        TestEnvironment.restart_celery_worker()


def get_resource(resource):
    """
    Gets the path for the provided resource.
    :param resource: resource name relative to /resources.
    """
    import resources
    resources_path = path.dirname(resources.__file__)
    resource_path = path.join(resources_path, resource)
    if not path.exists(resource_path):
        raise RuntimeError("Resource '{0}' not found in: {1}".format(resource, resource_path))
    return resource_path


def deploy_application(dsl_path, timeout=240):
    """
    A blocking method which deploys an application from the provided dsl path.
    """

    end = time.time() + timeout

    from cosmo.appdeployer.tasks import submit_and_execute_workflow, get_execution_status
    execution = submit_and_execute_workflow.delay(dsl_path)
    blueprint, execution_response = execution.get(timeout=60, propagate=True)
    r = {'status': 'pending'}
    while r['status'] != 'terminated' and r['status'] != 'failed':
        if end < time.time():
            raise TimeoutException('Timeout deploying {0}'.format(dsl_path))
        time.sleep(1)
        r = get_execution_status.delay(execution_response['id']).get(timeout=60, propagate=True)
    if r['status'] != 'terminated':
        raise RuntimeError('Application deployment failed. (status response: {0})'.format(r))

    return blueprint['id']


def undeploy_application(deployment_id, timeout=240):
    """
    A blocking method which undeploys an application from the provided dsl path.
    """
    end = time.time() + timeout
    from cosmo.appdeployer.tasks import uninstall_deployment, get_execution_status
    execution = uninstall_deployment.delay(deployment_id)
    execution_response = execution.get(timeout=60, propagate=True)
    r = {'status': 'pending'}
    while r['status'] != 'terminated' and r['status'] != 'failed':
        if end < time.time():
            raise TimeoutException('Timeout undeploying {0}'.format(deployment_id))
        time.sleep(1)
        r = get_execution_status.delay(execution_response['id']).get(timeout=60, propagate=True)
    if r['status'] != 'terminated':
        raise RuntimeError('Application undeployment failed. (status response: {0})'.format(r))


def validate_dsl(dsl_path, timeout=240):
    """
    A blocking method which validates a dsl from the provided dsl path.
    """
    from cosmo.appdeployer.tasks import submit_and_validate_blueprint
    result = submit_and_validate_blueprint.delay(dsl_path)
    response = result.get(timeout=60, propagate=True)
    if response['status'] != 'valid':
        raise RuntimeError('Blueprint {0} is not valid'.format(dsl_path))


def get_deployment_events(deployment_id, first_event=0, events_count=500):
    from cosmo.appdeployer.tasks import get_deployment_events as get_events
    result = get_events.delay(deployment_id, first_event, events_count)
    return result.get(timeout=10)


def get_deployment_nodes(deployment_id=None):
    from cosmo.appdeployer.tasks import get_deployment_nodes as get_nodes
    result = get_nodes.delay(deployment_id)
    return result.get(timeout=10)


def get_node(node_id):
    from cosmo.appdeployer.tasks import get_node as get_node_info
    result = get_node_info.delay(node_id)
    return result.get(timeout=10)


class TimeoutException(Exception):
    def __init__(self, *args):
        Exception.__init__(self, args)
