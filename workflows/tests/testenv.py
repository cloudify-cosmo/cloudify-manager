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


root = logging.getLogger()
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter(fmt='%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
ch.setFormatter(formatter)
root.addHandler(ch)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class CeleryWorkerProcess(object):
    _process = None

    def __init__(self, tempdir, plugins_tempdir, cosmo_path, cosmo_jar_path, riemann_config_path,
                 riemann_template_path, riemann_pid):
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
            "--queues=cloudify.management"
        ]

        os.chdir(self._tempdir)

        environment = os.environ.copy()
        environment['TEMP_DIR'] = self._plugins_tempdir
        environment['COSMO_JAR'] = self._cosmo_jar_path
        environment['RIEMANN_PID'] = str(self._riemann_pid)
        environment['RIEMANN_CONFIG'] = self._riemann_config_path
        environment['RIEMANN_CONFIG_TEMPLATE'] = self._riemann_template_path

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
        - Prepares celery app dir with plugins from cosmo module and official riemann configurer and plugin installer.
    """
    _instance = None
    _celery_worker_process = None
    _riemann_process = None
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

            # celery
            cosmo_path = path.dirname(path.realpath(cosmo.__file__))
            self._celery_worker_process = CeleryWorkerProcess(self._tempdir, self._plugins_tempdir, cosmo_path,
                                                              cosmo_jar_path,
                                                              riemann_config_path, riemann_template_path,
                                                              self._riemann_process.pid)
            self._celery_worker_process.start()
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

    @classmethod
    def setUpClass(cls):
        TestEnvironment.create(TestEnvironmentScope.CLASS)

    @classmethod
    def tearDownClass(cls):
        TestEnvironment.destroy(TestEnvironmentScope.CLASS)

    def setUp(self):
        TestEnvironment.clean_plugins_tempdir()

    def tearDown(self):
        TestEnvironment.kill_cosmo_process()


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


def deploy_application(dsl_path, timeout=120):
    """
    A blocking method which deploys an application from the provided dsl path.
    """
    from cosmo.appdeployer.tasks import deploy
    result = deploy.delay(dsl_path)
    result.get(timeout=timeout)

