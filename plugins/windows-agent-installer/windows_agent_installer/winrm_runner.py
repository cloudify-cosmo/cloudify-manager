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
    if session_config['host'] == '':
        raise ValueError('host is empty in session_config')
    if 'user' not in session_config:
        raise ValueError('Missing user in session_config')
    if 'password' not in session_config:
        raise ValueError('Missing password in session_config')


class WinRMRunner(object):

    def __init__(self,
                 session_config,
                 logger=None):

        logger = logger or setup_default_logger('WinRMRunner')

        # Validations - [host, user, password]
        validate(session_config)

        # Defaults - [protocol, uri, port]
        defaults(session_config)

        self.session_config = session_config
        self.session = self._create_session()
        self.logger = logger

    def _create_session(self):

        winrm_url = '{0}://{1}:{2}/{3}'.format(
            self.session_config['protocol'],
            self.session_config['host'],
            self.session_config['port'],
            self.session_config['uri'])
        return winrm.Session(url=winrm_url,
                             auth=(self.session_config['user'],
                                   self.session_config['password']))

    def run(self, command, raise_on_failure=True, quiet=False):

        """
        :param command: The command to execute.
        :param raise_on_failure:

            By default, this will raise an exception
            if the command fails.
            You can use raise_on_failure=False to
            just log the error and not raise an exception.

        :rtype WinRMCommandExecutionResponse.
        :raise WinRMCommandExecutionException.
        """

        def _chk(res):
            if res.status_code == 0:
                if not quiet:
                    self.logger.info(
                        '[{0}] out: {1}'.format(
                            self.session_config['host'],
                            res.std_out))
            else:
                error = WinRMCommandExecutionException(
                    command=command,
                    code=res.status_code,
                    error=res.std_err,
                    output=res.std_out)
                if raise_on_failure:
                    raise error
                self.logger.error(error)

        self.logger.info(
            '[{0}] run: {1}'.format(
                self.session_config['host'],
                command))
        response = self.session.run_cmd(command)
        _chk(response)
        return WinRMCommandExecutionResponse(
            command=command,
            std_err=response.std_err,
            std_out=response.std_out,
            return_code=response.status_code)

    def ping(self):

        """
        Tests that the winrm connection is working.

        :rtype WinRMCommandExecutionResponse.
        :raise WinRMCommandExecutionException.
        """

        return self.run('echo')

    def download(self, url, output_path):

        """
        :param url: URL to the resource to download.
        :param output_path: Local path the resource will be saved as.

        :rtype WinRMCommandExecutionResponse.
        :raise WinRMCommandExecutionException.
        """

        return self.run(
            '''@powershell -Command "(new-object System.Net.WebClient).Downloadfile('{0}','{1}')"'''  # NOQA
            .format(url, output_path))

    def move(self, src, dst):

        """
        Moves item at <src> to <dst>.

        :param src: Path to the source item.
        :param dst: Path to the destination item.

        :rtype WinRMCommandExecutionResponse.
        :raise WinRMCommandExecutionException.
        """

        return self.run(
            '''@powershell -Command "Move-Item {0} {1}"'''  # NOQA
            .format(src, dst))

    def copy(self, src, dst, force=False):

        """
        Copies item at <src> to <dst>.

        :param src: Path to the source item.
        :param dst: Path to the destination item.
        :param force: Creates missing path if needed.

        :rtype WinRMCommandExecutionResponse.
        :raise WinRMCommandExecutionException.
        """

        if force:
            return self.run(
                '''@powershell -Command "Copy-Item -Recurse -Force {0} {1}"'''  # NOQA
                .format(src, dst))
        return self.run(
            '''@powershell -Command "Copy-Item -Recurse {0} {1}"'''  # NOQA
            .format(src, dst))

    def exists(self, path):

        """
        Test if the given path exists.

        :param path: The path to tests.

        :rtype boolean
        :raise WinRMCommandExecutionException
        """

        response = self.run(
            '''@powershell -Command "Test-Path {0}"'''  # NOQA
            .format(path))
        return response.std_out == 'True\r\n'

    def delete(self, path, ignore_missing=False):

        """
        Deletes the resource in the given path.

        :param path:

           The path do delete.
           Can be either a file or a folder.

        :rtype WinRMCommandExecutionResponse.
        :raise WinRMCommandExecutionException.
        """

        return self.run(
            '''@powershell -Command "Remove-Item -Recurse -Force {0}"'''  # NOQA
            .format(path), raise_on_failure=not ignore_missing)

    def new_dir(self, path):

        """
        Creates the path as a new directory.

        :param path: The directory path to create.

        :rtype WinRMCommandExecutionResponse.
        :raise WinRMCommandExecutionException.
        """

        return self.run(
            '''@powershell -Command "New-Item {0} -type directory"'''  # NOQA
            .format(path))

    def new_file(self, path):

        """
        Creates the path as a new file.

        :param path: The file path to create.

        :rtype WinRMCommandExecutionResponse.
        :raise WinRMCommandExecutionException.
        """

        return self.run(
            '''@powershell -Command "New-Item {0} -type file"'''  # NOQA
            .format(path))

    def service_state(self, service_name):

        """
        Queries the state of the given service.

        :param service_name: The service name to query.

        :return

            The state of the service.
                - 'Running'
                - 'Stopped'
                - 'Start Pending'
                - 'Continue Pending'
                - 'Pause Pending'
                - 'Paused'
                - 'Unknown'

        :rtype string.
        :raise WinRMCommandExecutionException.
        """

        response = self.run(
            '''@powershell -Command "(Get-Service -Name {0}).Status"'''  # NOQA
            .format(service_name))
        return response.std_out.strip()

    def put(self, contents, path):

        """
        Writes the contents to a file in the given path.

        :param contents: The contents to write. string based.
        :param path:

            Path to a file.
            The file must be inside an existing directory.

        :rtype WinRMCommandExecutionResponse.
        :raise WinRMCommandExecutionException.
        """

        return self.run(
            '''@powershell -Command "Add-Content {0} '{1}'"'''  # NOQA
            .format(path, contents))

    def get(self, path):

        """
        Reads the contents of the file in the given path.

        :param path: Path to a file.

        :rtype string.
        :raise WinRMCommandExecutionException.
        """

        return self.run(
            '''@powershell -Command "Get-Content {0}"'''  # NOQA
            .format(path)).std_out


class WinRMCommandExecutionException(CommandExecutionException):

    """
    Indicates a failure to execute a command over WinRM.

    """


class WinRMCommandExecutionResponse(CommandExecutionResponse):

    """
    Wrapper for indicating the command was originated from a winrm session.
    """
