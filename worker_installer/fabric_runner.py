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


__author__ = 'idanmo'


import os
import time
from functools import wraps
from StringIO import StringIO
from fabric.api import run, put, local, get
from fabric.context_managers import settings
from fabric.contrib.files import exists


def retry(timeout=60):
    def decorator(func):
        def wrapper(*args, **kwargs):
            deadline = time.time() + timeout
            while time.time() < deadline:
                try:
                    return func(*args, **kwargs)
                except BaseException:
                    time.sleep(5)
            else:
                return func(*args, **kwargs)
        return wraps(func)(wrapper)
    return decorator


class FabricRunner(object):

    def __init__(self, worker_config=None):
        config = worker_config or {}
        self.local = 'host' not in config
        if not self.local:
            self.host_string = '%(user)s@%(host)s:%(port)s' % config
            self.key_filename = config['key']

    @retry(timeout=120)
    def ping(self):
        self.run('echo "ping!"')

    def run(self, command):
        out = StringIO()
        if self.local:
            try:
                from subprocess import check_output
                from subprocess import CalledProcessError
                from subprocess import STDOUT
                return check_output(command.split(' '), stderr=STDOUT)
            except CalledProcessError as e:
                raise FabricRunnerException(command, e.returncode, e.output)
            except OSError as e:
                raise FabricRunnerException(command, -1, str(e))

        with settings(host_string=self.host_string,
                      key_filename=self.key_filename,
                      disable_known_hosts=True):

            try:
                return run(command, stdout=out, stderr=out)
            except SystemExit, e:
                raise FabricRunnerException(command, e.code, out.getvalue())

    def exists(self, file_path):
        if self.local:
            return os.path.exists(file_path)
        with settings(host_string=self.host_string,
                      key_filename=self.key_filename,
                      disable_known_hosts=True):
            return exists(file_path)

    def put(self, file_path, content, use_sudo=False):
        if self.local:
            if os.path.exists(file_path):
                raise IOError('Cannot put file, file already '
                              'exists: {0}'.format(file_path))
            directory = "/".join(file_path.split("/")[:-1])
            if use_sudo:
                # we need to write a string to a file locally with sudo
                # use echo for now
                if not os.path.exists(directory):
                    local("sudo mkdir -p {0}".format(directory))
                local("echo '{0}'".format(content) +
                      " | sudo tee -a {0}".format(file_path))
            else:
                # no sudo needed. just use python for this
                if not os.path.exists(directory):
                    os.makedirs(directory)
                with open(file_path, "w") as f:
                    f.write(content)
        else:
            with settings(host_string=self.host_string,
                          key_filename=self.key_filename,
                          disable_known_hosts=True):
                if exists(file_path):
                    raise IOError('Cannot put file, file already '
                                  'exists: {0}'.format(file_path))
                directory = "/".join(file_path.split("/")[:-1])
                sudo_prefix = 'sudo ' if use_sudo else ''
                run('{0}mkdir -p {1}'.format(sudo_prefix, directory))
                put(StringIO(content), file_path, use_sudo=use_sudo)

    def get(self, file_path):
        if self.local:
            return run('sudo cat {0}'.format(file_path))
        else:
            output = StringIO()
            get(file_path, output)
            return output.getvalue()


class FabricRunnerException(SystemExit):

    def __init__(self, command, code, message):
        self.command = command
        self.message = message
        self.code = code

    def __str__(self):
        return "Command '{0}' exited with code {1}: {2}".format(
            self.command, self.code, self.message)


if __name__ == '__main__':
    worker_config = {
        'user': 'vagrant',
        'port': 2222,
        'host': '127.0.0.1',
        'key': '~/.vagrant.d/insecure_private_key'
    }
    runner = FabricRunner(worker_config)
    try:
        result = runner.ping()
        print "result is:", result
    except FabricRunnerException as e:
        print str(e)
    except BaseException as e:
        print "Exception is:", e.__class__
        print e