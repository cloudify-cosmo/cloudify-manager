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

import os
import re
import subprocess
import threading
import time
import requests

from os import path
from testenv.constants import MANAGER_REST_PORT
from testenv.utils import get_resource
from cloudify.utils import setup_default_logger


logger = setup_default_logger('riemann_process')


class RiemannProcess(object):
    """
    Manages a riemann server process lifecycle.
    """

    def __init__(self, config_path, libs_path):
        self._config_path = config_path
        self._libs_path = libs_path
        self.pid = None
        self._process = None
        self._detector = None
        self._event = None
        self._riemann_logs = list()

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
        logger.info('Starting riemann server...')
        self.pid = self._find_existing_riemann_process()
        if self.pid:
            logger.info('Riemann server is already running [pid={0}]'
                        .format(self.pid))
            return

        env = os.environ.copy()
        env['LANGOHR_JAR'] = self._langohr_jar_path()
        env['MANAGEMENT_IP'] = '127.0.0.1'
        env['MANAGER_REST_PORT'] = str(MANAGER_REST_PORT)

        command = [
            get_resource(path.join('riemann', 'riemann.sh')),
            self._config_path
        ]
        self._process = subprocess.Popen(command,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT,
                                         env=env)
        self._event = threading.Event()
        self._detector = threading.Thread(target=self._start_detector,
                                          kwargs={'process': self._process})
        self._detector.daemon = True
        self._detector.start()
        timeout = 60
        if not self._event.wait(timeout):
            raise RuntimeError(
                'Unable to start riemann process:\n{0} (timed out after '
                '{1} seconds)'.format('\n'.join(self._riemann_logs), timeout))
        logger.info('Riemann server started [pid={0}]'.format(self.pid))

    def close(self):
        if self.pid:
            logger.info('Shutting down riemann server [pid={0}]'
                        .format(self.pid))
            os.system('kill {0}'.format(self.pid))

    def restart(self):
        self.close()
        while self._find_existing_riemann_process():
            time.sleep(0.1)
        self.start()

    @staticmethod
    def _find_existing_riemann_process():
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

    def _langohr_jar_path(self):
        lib_url = 'https://s3-eu-west-1.amazonaws.com' \
                  '/gigaspaces-repository-eu/langohr/2.11.0/langohr.jar'
        lib_name = 'langohr'
        version = '2.11.0'
        lib_dir = os.path.join(self._libs_path, lib_name, version)
        lib_path = os.path.join(lib_dir, 'langohr.jar')
        if not os.path.isdir(lib_dir):
            logger.info("Downloading langohr jar. This should only happen"
                        " once so don't worry about it too much")
            os.makedirs(lib_dir)
            self.download_file(url=lib_url, target=lib_path)
        return lib_path

    @staticmethod
    def download_file(url, target):
        r = requests.get(url, stream=True)
        with open(target, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
                    f.flush()
