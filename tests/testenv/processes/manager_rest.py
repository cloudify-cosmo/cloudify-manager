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
import subprocess
import sys
import time
import yaml

from cloudify.utils import setup_default_logger
from os.path import dirname
from os import path
from cloudify_rest_client import CloudifyClient
from testenv.constants import MANAGER_REST_PORT


logger = setup_default_logger('manager_rest_process')


class ManagerRestProcess(object):

    def __init__(self,
                 port,
                 file_server_dir,
                 file_server_base_uri,
                 file_server_blueprints_folder,
                 file_server_uploaded_blueprints_folder,
                 file_server_resources_uri,
                 tempdir):
        self.process = None
        self.port = port or MANAGER_REST_PORT
        self.file_server_dir = file_server_dir
        self.file_server_base_uri = file_server_base_uri
        self.file_server_blueprints_folder = file_server_blueprints_folder
        self.file_server_uploaded_blueprints_folder = \
            file_server_uploaded_blueprints_folder
        self.file_server_resources_uri = file_server_resources_uri
        self.client = CloudifyClient('localhost', port=port)
        self.tempdir = tempdir

    def start(self, timeout=10):
        end_time = time.time() + timeout

        configuration = {
            'file_server_root': self.file_server_dir,
            'file_server_base_uri': self.file_server_base_uri,
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
        while not started and time.time() < end_time:
            time.sleep(0.5)
            logger.info('Testing connection to manager rest service. '
                        '(Attempt: {0}/{1})'.format(attempt, timeout))
            attempt += 1
            started = self.started()
        if not started:
            raise RuntimeError('Failed opening connection to manager rest '
                               'service')

    def started(self):
        try:
            self.client.manager.get_status()
            return True
        except BaseException as e:
            if e.message:
                logger.warning(e.message)
            return False

    def close(self):
        if self.process is not None:
            logger.info('Shutting down manager-rest service [pid=%s]',
                        self.process.pid)
            self.process.terminate()

    @staticmethod
    def locate_manager_rest_dir():
        # start with current location
        manager_rest_location = path.abspath(__file__)
        # get to cosmo-manager
        for i in range(4):
            manager_rest_location = path.dirname(manager_rest_location)
        # build way into manager_rest
        return path.join(manager_rest_location,
                         'rest-service/manager_rest')
