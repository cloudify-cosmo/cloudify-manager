import argparse
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


def get_cloudify_agent():
    from cloudify.state import ctx_parameters
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

    @property
    def cfy_agent_path(self):
        return self.runner.env_command(
            self.cloudify_agent['envdir'],
            'cfy-agent')

    def run_agent_command(self, command, execution_env=None):
        command = '{0} {1}'.format(self.cfy_agent_path, command)
        self.runner.run(command, execution_env)

    def run_daemon_command(self, command):
        execution_env = {}
        # Because celery is very persistent and will always try to use this
        # env variable instead of using parameters it receives:
        execution_env['CELERY_BROKER_URL'] = str(
            self.cloudify_agent['broker_url'])
        execution_env['CLOUDIFY_DAEMON_USER'] = str(
            self.cloudify_agent['user'])
        return self.run_agent_command(command='daemons {0} --name={1}'
                                      .format(command,
                                              self.cloudify_agent['name']),
                                      execution_env=execution_env)

    def install(self):
        path = tempfile.mkdtemp()
        try:
            package_path = os.path.join(path, self.runner.archive_name())
            self.runner.download(
                url=self.cloudify_agent['package_url'],
                destination=package_path)
            self.runner.extract(package_path, path)
            agent_config_path = os.path.join(path, 'agent.json')
            with open(agent_config_path, 'w') as agent_file:
                agent_file.write(json.dumps(self.cloudify_agent))
            agent_cmd = self.runner.env_command(path, 'cfy-agent')
            command = ('{0} install_local'
                       ' --agent-file {1}').format(
                           agent_cmd,
                           agent_config_path)
            self.runner.run(command)
        finally:
            self.runner.rm_dir(path)

    def uninstall(self):
        self.run_daemon_command('stop')
        self.run_daemon_command('delete')
        self.delete_env()

    def delete_env(self):
        self.runner.rm_dir(self.cloudify_agent['agent_dir'])


def _parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--operation')
    parser.add_argument('--config')
    parser.add_argument('--dryrun', action='store_true', default=False)
    parser.add_argument('--ignore-result', action='store_true', default=False)
    return parser


def _parse_args(parser, args):
    # Unkown args mean we are running in script plugin task.
    # So we are not stopping execution.
    result, _ = parser.parse_known_args(args)
    if result.config is None:
        # Make sure that we are able to retrieve agent config.
        get_cloudify_agent()
    return result


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


def prepare_cloudify_agent(path):
    if path:
        with open(path) as f:
            agent = json.load(f)
    else:
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


def _perform_operation(operation, installer):
    if not operation:
        operation = 'install'
    operations = {
        'install': installer.install,
        'delete_env': installer.delete_env,
        'uninstall': installer.uninstall
    }
    if operation in operations:
        operations[operation]()
    else:
        installer.run_daemon_command(operation)


def _return(value, old_agent_version):
    from cloudify import ctx
    ctx.returns(value)
    # Due to bug in celery:
    if os.name == 'nt' and old_agent_version.startswith('3.2'):
        from celery import current_task
        from cloudify.celery import celery
        celery.backend.mark_as_done(current_task.request.id, value)


def _main(args):
    parser = _parser()
    command = _parse_args(parser, args[1:])
    cloudify_agent = prepare_cloudify_agent(command.config)
    logger = _setup_logger('installer')
    runner = _prepare_runner(logger)
    installer = Installer(logger, runner, cloudify_agent)
    if command.dryrun:
        logger.info('Options: {0}'.format(str(command)))
        logger.info('Agent:')
        logger.info(str(cloudify_agent))
    else:
        _perform_operation(command.operation, installer)
    if not command.ignore_result:
        _return(cloudify_agent, cloudify_agent['old_agent_version'])


if __name__ == '__main__':
    _main(sys.argv)
