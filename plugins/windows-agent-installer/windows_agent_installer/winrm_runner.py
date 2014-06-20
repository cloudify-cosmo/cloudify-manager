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
import logging
import sys

__author__ = 'elip'

import winrm

DEFAULT_WINRM_PORT = '5985'
DEFAULT_WINRM_URI = 'wsman'
DEFAULT_WINRM_PROTOCOL = 'http'

def setup_default_logger():
    root = logging.getLogger()
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter(fmt='%(asctime)s [%(levelname)s] '
                                      '[%(name)s] %(message)s', datefmt='%H:%M:%S')
    ch.setFormatter(formatter)
    # clear all other handlers
    for handler in root.handlers:
        root.removeHandler(handler)
    root.addHandler(ch)
    logger = logging.getLogger('WinRMExecutor')
    logger.setLevel(logging.DEBUG)
    return logger

def defaults(session_config):

    if 'protocol' not in session_config:
        session_config['protocol'] = DEFAULT_WINRM_PROTOCOL
    if 'uri' not in session_config:
        session_config['uri'] = DEFAULT_WINRM_URI
    if 'port' not in session_config:
        session_config['port'] = DEFAULT_WINRM_PORT


def validate(session_config):

    if 'host' not in session_config:
        raise ValueError('Missing host in session_config')
    if 'user' not in session_config:
        raise ValueError('Missing user in session_config')
    if 'password' not in session_config:
        raise ValueError('Missing password in session_config')


class WinRMRunner(object):

    def __init__(self, session_config, logger=setup_default_logger()):

        # Validations - [host, user, password]
        validate(session_config)

        # Defaults - [protocol, uri, port]
        defaults(session_config)# Validations - [host, user, password]

        self.session_config = session_config
        self.session = self._create_session()
        self.logger = logger


    def _create_session(self):

        winrm_url = '{0}://{1}:{2}/{3}'.format(
            self.session_config['protocol'],
            self.session_config['host'],
            self.session_config['port'],
            self.session_config['uri'])
        return winrm.Session(winrm_url, auth=(self.session_config['user'],
                                              self.session_config['password']))

    def run(self, command, exit_on_failure=True):

        def _chk(res):
            if res.status_code == 0:
                self.logger.debug('[{0}] out: {1}'.format(self.session_config['host'], res.std_out))
            else:
                error = WinRMExecutionException(
                    command=command,
                    code=res.status_code,
                    message=res.std_err)
                self.logger.error(error)
                if exit_on_failure:
                    raise error

        self.logger.debug('[{0}] run: {1}'.format(self.session_config['host'], command))
        response = self.session.run_cmd(command)
        _chk(response)
        return response

    def download(self, url, output_path):
        self.logger.debug('Downloading {0}...'.format(url))
        return self.run(
            '''@powershell -Command "(new-object System.Net.WebClient).Downloadfile('{0}','{1}')"'''  # NOQA
            .format(url, output_path))


class WinRMExecutionException(Exception):

    """
    Indicates a failure to execute a command over WinRM

    'command' - The command that was executed
    'code' - The error code from the execution.
    'message' - The error from the execution

    """

    def __init__(self, command, message, code):
        self.command = command
        self.message = message
        self.code = code
        Exception.__init__(self, self.__str__())

    def __str__(self):
        return "Failed executing command: {0}\nError code: {1}\nError message: {2}"\
               .format(self.command, self.code, self.message)

