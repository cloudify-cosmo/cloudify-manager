#########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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


import os
import tempfile
from StringIO import StringIO

import fabric.network
from fabric.api import run, put, get, local, sudo
from fabric.context_managers import settings
from fabric.contrib.files import exists

from cloudify import context
from cloudify.exceptions import NonRecoverableError


def is_on_management_worker(ctx):
    """
    Gets whether agent installation was invoked for a deployment.
    """
    return ctx.type == context.DEPLOYMENT


def download_resource_on_host(logger, runner, url, destination_path):
    """downloads a resource from the fileserver on the agent's host

    Will try to get the resource. If it fails, will try to curl.
    If both fail, will return the state of the last fabric action.
    """
    logger.debug('attempting to download {0} to {1}'.format(
        url, destination_path))
    logger.debug('checking whether wget exists on the host machine')
    r = runner.run('which wget')
    if type(r) is str or r.succeeded:
        logger.debug('wget-ing {0} to {1}'.format(url, destination_path))
        return runner.run('wget -T 30 {0} -O {1}'.format(
            url, destination_path))
    logger.debug('checking whether curl exists on the host machine')
    r = runner.run('which curl')
    if type(r) is str or r.succeeded:
        logger.debug('curl-ing {0} to {1}'.format(url, destination_path))
        return runner.run('curl {0} -O {1}'.format(
            url, destination_path))
    raise NonRecoverableError(
        'could not download resource ({0} (with code {1}) )'.format(
            r.stderr, r.status_code))


class FabricRunner(object):

    def __init__(self, ctx, agent_config=None):
        self.ctx = ctx
        config = agent_config or {}
        self.local = is_on_management_worker(ctx)
        if not self.local:
            self.host_string = '%(user)s@%(host)s:%(port)s' % config
            self.key_filename = config.get('key', '')
            self.password = config.get('password', '')

    def ping(self):
        self.run('echo "ping!"')

    def run(self, command, shell_escape=None):
        self.ctx.logger.debug('Running command: {0}'.format(command))
        if self.local:
            try:
                with settings(warn_only=True):
                    r = local(command, capture=True)
                    if r.return_code != 0:
                        raise FabricRunnerException(command,
                                                    r.return_code,
                                                    r.stderr)
                    return r.stdout
            except Exception as e:
                raise FabricRunnerException(command, -1, str(e))
        out = StringIO()
        with settings(host_string=self.host_string,
                      key_filename=self.key_filename,
                      password=self.password,
                      disable_known_hosts=True):
            try:
                return run(command, stdout=out, stderr=out,
                           shell_escape=shell_escape)
            except SystemExit, e:
                raise FabricRunnerException(command, e.code, out.getvalue())

    def exists(self, file_path):
        if self.local:
            return os.path.exists(file_path)
        with settings(host_string=self.host_string,
                      key_filename=self.key_filename,
                      password=self.password,
                      disable_known_hosts=True):
            return exists(file_path)

    def put(self, file_path, content, use_sudo=False):
        self.ctx.logger.debug(
            'Putting file: {0} [use_sudo={1}]'.format(file_path, use_sudo))
        directory = "/".join(file_path.split("/")[:-1])
        if self.local:
            if os.path.exists(file_path):
                raise NonRecoverableError('Cannot put file, file already '
                                          'exists: {0}'.format(file_path))
            if use_sudo:
                # we need to write a string to a file locally with sudo
                # use echo for now
                if not os.path.exists(directory):
                    self.run("sudo mkdir -p {0}".format(directory))
                temp_file = tempfile.mktemp()
                with open(temp_file, 'w') as f:
                    f.write(content)
                self.run('sudo cp {0} {1}'.format(temp_file, file_path))
                self.run('sudo rm {0}'.format(temp_file))
            else:
                # no sudo needed. just use python for this
                if not os.path.exists(directory):
                    os.makedirs(directory)
                with open(file_path, 'w') as f:
                    f.write(content)
        else:
            with settings(host_string=self.host_string,
                          key_filename=self.key_filename,
                          password=self.password,
                          disable_known_hosts=True):
                if exists(file_path):
                    raise NonRecoverableError('Cannot put file, file already '
                                              'exists: {0}'.format(file_path))
                mkdir_command = 'mkdir -p {0}'.format(directory)
                sudo(mkdir_command) if use_sudo else run(mkdir_command)
                put(StringIO(content), file_path, use_sudo=use_sudo)

    def get(self, file_path):
        if self.local:
            return self.run('sudo cat {0}'.format(file_path))
        else:
            output = StringIO()
            with settings(host_string=self.host_string,
                          key_filename=self.key_filename,
                          password=self.password,
                          disable_known_hosts=True):
                get(file_path, output)
                return output.getvalue()

    def close(self):
        if self.local:
            return
        fabric.network.disconnect_all()


class FabricRunnerException(Exception):
    """
    Describes an error caused in a fabric command execution.

    The exception contains the command, return code and error message.
    """

    def __init__(self, command, code, message):
        self.command = command
        self.message = message
        self.code = code
        Exception.__init__(self, self.__str__())

    def __str__(self):
        return "Command '{0}' exited with code {1}: {2}".format(
            self.command, self.code, self.message)
