#########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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
import json
import logging
import os
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib

from cloudify import ctx
from cloudify.state import ctx_parameters


def get_cloudify_agent():
    return ctx_parameters['cloudify_agent']


def _shlex_split(command):
    lex = shlex.shlex(command, posix=True)
    lex.whitespace_split = True
    lex.escape = ''
    return list(lex)


class CommandRunner(object):

    def __init__(self, logger):
        self.logger = logger

    def run(self, command, execution_env=None):
        self.logger.debug('run: {0}'.format(command))
        command_env = os.environ.copy()
        command_env.update(execution_env or {})
        p = subprocess.Popen(_shlex_split(command),
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             env=command_env)
        out, err = p.communicate()
        if p.returncode != 0:
            if out:
                out = out.rstrip()
            if err:
                err = err.rstrip()
            self.logger.error('Command {0} failed.'.format(command))
            self.logger.error('Stdout:')
            self.logger.error(out)
            self.logger.error('Stderr:')
            self.logger.error(err)
            raise Exception()

    def download(self, url, destination=None):
        self.logger.debug('Retrieving file from {0}'.format(url))
        if destination is None:
            fh_num, destination = tempfile.mkstemp()
            os.close(fh_num)
        urllib.urlretrieve(url, destination)
        return destination

    def rm_dir(self, directory):
        shutil.rmtree(directory)

    def extract(self, archive, destination, strip=1):
        raise NotImplementedError('subclass responsibility')

    def env_command(self, env_path, command):
        raise NotImplementedError('subclass responsibility')

    def archive_name(self):
        raise NotImplementedError('subclass responsibility')


class LinuxRunner(CommandRunner):

    def archive_name(self):
        return 'package.tar.gz'

    def extract(self, archive, destination):
        return self.run('tar xzvf {0} --strip=2 -C {1}'
                        .format(archive, destination))

    def env_command(self, env_path, command):
        return '{0}/bin/python {0}/bin/{1}'.format(env_path, command)


class WindowsRunner(CommandRunner):

    def archive_name(self):
        return 'package.exe'

    def extract(self, archive, destination, strip=1):
        cmd = ('{0} /SILENT /VERYSILENT'
               ' /SUPPRESSMSGBOXES /DIR={1}').format(archive, destination)
        return self.run(cmd)

    def env_command(self, env_path, command):
        return '{0}\Scripts\python {0}\Scripts\{1}.exe'.format(
            env_path,
            command)


def _prepare_runner(logger):
    if os.name == 'nt':
        return WindowsRunner(logger)
    else:
        return LinuxRunner(logger)


class Installer(object):

    def __init__(self, logger, runner, cloudify_agent):
        self.logger = logger
        self.runner = runner
        self.cloudify_agent = cloudify_agent

    def install(self):
        path = tempfile.mkdtemp()
        try:
            package_path = os.path.join(path, self.runner.archive_name())
            self.runner.download(
                url=self.cloudify_agent['package_url'],
                destination=package_path)
            self.runner.extract(package_path, path)
            agent_config_path = os.path.join(path, 'agent.json')
            agent_output_path = os.path.join(path, 'output.json')
            with open(agent_config_path, 'w') as agent_file:
                agent_file.write(json.dumps(self.cloudify_agent))
            agent_cmd = self.runner.env_command(path, 'cfy-agent')
            command = ('{0} install-local'
                       ' --agent-file {1}'
                       ' --output-agent-file {2}').format(
                           agent_cmd,
                           agent_config_path,
                           agent_output_path)
            self.runner.run(command)
            with open(agent_output_path) as agent_file:
                return json.load(agent_file)
        finally:
            self.runner.rm_dir(path)


def _set_package_url(agent):
    file_server = agent['manager_file_server_url']
    if agent['windows']:
        agent_file = 'cloudify-windows-agent.exe'
    else:
        distro, _, distro_codename = platform.dist()
        agent['distro'] = distro.lower()
        agent['distro_codename'] = distro_codename.lower()
        agent_file = '{0}-{1}-agent.tar.gz'.format(
            agent['distro'],
            agent['distro_codename'])
    agent['package_url'] = '{0}/packages/agents/{1}'.format(
        file_server,
        agent_file)


def prepare_cloudify_agent():
    agent = get_cloudify_agent()
    agent['windows'] = os.name == 'nt'
    if 'package_url' not in agent:
        _set_package_url(agent)
    return agent


def _setup_logger(name):
    logger_format = '%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
    logger = logging.getLogger(name)
    formatter = logging.Formatter(fmt=logger_format,
                                  datefmt='%H:%M:%S')
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    return logger


def _return(value, old_agent_version):
    ctx.returns(value)
    # Due to bug in celery:
    # https://github.com/celery/celery/issues/897
    if os.name == 'nt' and old_agent_version.startswith('3.2'):
        from celery import current_task
        from cloudify.celery import celery
        celery.backend.mark_as_done(current_task.request.id, value)


def _main(args):
    cloudify_agent = prepare_cloudify_agent()
    logger = _setup_logger('installer')
    runner = _prepare_runner(logger)
    installer = Installer(logger, runner, cloudify_agent)
    result = installer.install()
    _return(result, cloudify_agent['old_agent_version'])


if __name__ == '__main__':
    _main(sys.argv)
