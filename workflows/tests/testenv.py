__author__ = 'idanm'

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
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
root.addHandler(ch)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class CeleryWorkerProcess(object):
    _process = None

    def __init__(self, tempdir, cosmo_path, cosmo_jar_path, riemann_config_path, riemann_pid):
        self._celery_pid_file = path.join(tempdir, "celery.pid")
        self._cosmo_path = cosmo_path
        self._app_path = path.join(tempdir, "cosmo")
        self._tempdir = tempdir
        self._cosmo_jar_path = cosmo_jar_path
        self._riemann_config_path = riemann_config_path
        self._riemann_pid = riemann_pid

    def start(self):
        logger.info("Copying %s to %s", self._cosmo_path, self._app_path)
        shutil.copytree(self._cosmo_path, self._app_path)
        celery_command = [
            "celery",
            "worker",
            "--events",
            "--loglevel=debug",
            "--app=cosmo",
            "--hostname=cloudify.management",
            "--purge",
            "--logfile={0}".format(path.join(self._tempdir, "celery.log")),
            "--pidfile={0}".format(self._celery_pid_file),
            "--queues=cloudify.management"
        ]

        os.chdir(self._tempdir)

        environment = os.environ.copy()
        environment['COSMO_JAR'] = self._cosmo_jar_path
        environment['RIEMANN_CONFIG'] = self._riemann_config_path
        environment['RIEMANN_PID'] = str(self._riemann_pid)

        logger.info("Starting celery worker...")
        self._process = subprocess.Popen(celery_command, env=environment)

        deadline = time.time() + 10
        while not path.exists(self._celery_pid_file) and time.time() < deadline:
            time.sleep(1)

        if not path.exists(self._celery_pid_file):
            raise RuntimeError("Failed to start celery worker: {0}".format(self._process.returncode))

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
            self._riemann_logs.append(line)
            if line != '':
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
            logger.info("Riemann server already running [pid={0}]".format(self.pid))
            return
        command = [
            'riemann',
            self._config_path
        ]
        self._process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self._event = threading.Event()
        self._detector = threading.Thread(target=self._start_detector, kwargs={'process': self._process})
        self._detector.start()
        if not self._event.wait(10):
            raise RuntimeError("Unable to start riemann process:\n{0}".format('\n'.join(self._riemann_logs)))
        logger.info("Riemann server started [pid={0}]".format(self.pid))

    def close(self):
        if self.pid:
            logger.info("Shutting down riemann server [pid={0}]".format(self.pid))
            os.system("kill {0}".format(self.pid))

    def _find_existing_riemann_process(self):
        from subprocess import CalledProcessError
        pattern = "(\d*)\s.*"
        try:
            output = subprocess.check_output("ps a | grep 'riemann.jar' | grep -v grep", shell=True)
            match = re.match(pattern, output)
            if match:
                return int(match.group(1))
        except CalledProcessError:
            pass
        return None


# class MyTest(unittest.TestCase):
#     def test(self):
#         p = RiemannProcess('/home/idanm/temp/riemann.config')
#         p.start()
#         p.close()


class TestCase(unittest.TestCase):

    _celery_worker_process = None
    _riemann_process = None
    _tempdir = None

    @classmethod
    def setUpClass(cls):
        try:
            logger.info("Setting up test environment...")

            # temp directory
            cls._tempdir = tempfile.mkdtemp(suffix="test", prefix="cloudify")
            logger.info("Test environment will be stored in: %s", cls._tempdir)
            cosmo_jar_path = cls._get_cosmo_jar_path()

            # riemann
            riemann_config_path = path.join(cls._tempdir, "riemann.config")
            cls._generate_riemann_config(riemann_config_path)
            cls._riemann_process = RiemannProcess(riemann_config_path)
            cls._riemann_process.start()

            # celery
            cosmo_path = path.dirname(path.realpath(cosmo.__file__))
            cls._celery_worker_process = CeleryWorkerProcess(cls._tempdir, cosmo_path, cosmo_jar_path,
                                                             riemann_config_path, cls._riemann_process.pid)
            cls._celery_worker_process.start()
            logger.info("Running [%s] tests", cls.__name__)
        except BaseException as error:
            logger.error("Error in test environment setup: %s", error)
            cls.tearDownClass()
            raise error

    @classmethod
    def tearDownClass(cls):
        logger.info("Test teardown...")
        if cls._riemann_process:
            cls._riemann_process.close()
        if cls._celery_worker_process:
            cls._celery_worker_process.close()
        if cls._tempdir:
            logger.info("Deleting test environment from: %s", cls._tempdir)
            shutil.rmtree(cls._tempdir, ignore_errors=True)

    @classmethod
    def _get_cosmo_jar_path(cls):
        cosmo_jar_path = path.realpath(path.join(path.dirname(__file__), '../../orchestrator/target/cosmo.jar'))
        if not path.exists(cosmo_jar_path):
            raise RuntimeError("cosmo.jar not found in: {0}".format(cosmo_jar_path))
        return cosmo_jar_path

    @classmethod
    def _generate_riemann_config(cls, target_path):
        source_path = get_resource('riemann/riemann.config')
        shutil.copy(source_path, target_path)


def get_resource(resource):
    import resources
    resources_path = path.dirname(resources.__file__)
    resource_path = path.join(resources_path, resource)
    if not path.exists(resource_path):
        raise RuntimeError("Resource '{0}' not found in: {1}".format(resource, resource_path))
    return resource_path


