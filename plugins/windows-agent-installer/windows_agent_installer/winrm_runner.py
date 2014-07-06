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

__author__ = 'elip'

import winrm
from cloudify.exceptions import CommandExecutionException
from cloudify.utils import CommandExecutionResponse
from cloudify.utils import setup_default_logger

DEFAULT_WINRM_PORT = '5985'
DEFAULT_WINRM_URI = 'wsman'
DEFAULT_WINRM_PROTOCOL = 'http'

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

    def __init__(self, session_config, logger=setup_default_logger('WinRMRunner')):

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
                    error=res.std_err,
                    output=res.std_out)
                self.logger.error(error)
                if exit_on_failure:
                    raise error


        self.logger.info('[{0}] run: {1}'.format(self.session_config['host'], command))
        response = self.session.run_cmd(command)
        _chk(response)
        return CommandExecutionResponse(command=command,
                                        std_err=response.std_err,
                                        std_out=response.std_out,
                                        return_code=response.status_code)

    def ping(self):
        return self.run('echo Testing Session')

    def download(self, url, output_path):
        return self.run(
            '''@powershell -Command "(new-object System.Net.WebClient).Downloadfile('{0}','{1}')"'''  # NOQA
            .format(url, output_path))

    def move(self, src, dest, create_missing_directories=False):

        '''
        Moves item at <src> to <dest>. Does not create missing directories.

        :param src: Path to the source item.
        :param dest: Path to the destination item.
        :return: An execution 'response' instance.
        '''

        return self.run(
            '''@powershell -Command "Move-Item {0} {1}"'''  # NOQA
            .format(src, dest))

    def copy(self, src, dest, create_missing_directories=False):

        '''
        Copies item at <src> to <dest>. Does not create missing directories.

        :param src: Path to the source item.
        :param dest: Path to the destination item.
        :param create_missing_directories: True to create any missing directories in the destination path.
        :return: An execution 'response' instance.
        '''

        if create_missing_directories:
            return self.run(
                '''@powershell -Command "Copy-Item -Recurse -Force {0} {1}"'''  # NOQA
                .format(src, dest))
        return self.run(
            '''@powershell -Command "Copy-Item -Recurse {0} {1}"'''  # NOQA
            .format(src, dest))

    def exists(self, path):
        response = self.run(
            '''@powershell -Command "Test-Path {0}"'''  # NOQA
            .format(path))
        return response.std_out == 'True\r\n'

    def delete(self, path):
        return self.run(
            '''@powershell -Command "Remove-Item -Recurse -Force {0}"'''  # NOQA
            .format(path))

    def new_dir(self, path):
        return self.run(
            '''@powershell -Command "New-Item {0} -type directory"'''  # NOQA
            .format(path))

    def new_file(self, path):
        return self.run(
            '''@powershell -Command "New-Item {0} -type file"'''  # NOQA
            .format(path))

    def service_state(self, service_name):
        response = self.run(
            '''@powershell -Command "(Get-Service -Name {0}).Status"'''  # NOQA
            .format(service_name))
        return response.std_out.strip()



class WinRMExecutionException(CommandExecutionException):

    """
    Indicates a failure to execute a command over WinRM.

    """