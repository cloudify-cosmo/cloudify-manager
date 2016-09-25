#!/usr/bin/env python
from time import sleep
import subprocess
import shlex
import os

from cloudify import ctx


WORKDIR = os.path.expanduser('~')
REPOS_DIR = os.path.join(WORKDIR, 'repos')

_CLOUDIFY_VENV_NAME = 'docl_env'
CLOUDIFY_VENV_PATH = os.path.join(WORKDIR, _CLOUDIFY_VENV_NAME)


def run(command, ignore_failures=False, workdir=None, out=False):
    if isinstance(command, str):
        command = shlex.split(command)
    ctx.logger.info('Running: {0}'.format(command))
    proc = subprocess.Popen(command,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            cwd=workdir)
    if out:
        stdout = ''
        stderr = ''
        while proc.poll() is None:
            for line in proc.stdout:
                stdout += line
                try:
                    ctx.logger.info(line.rstrip())
                except:
                    ctx.logger.debug('Failed printing stdout line')
            for line in proc.stderr:
                stderr += line
                try:
                    ctx.logger.info(line.rstrip())
                except:
                    ctx.logger.debug('Failed printing stderr line')
            sleep(0.1)
        ctx.logger.info(proc.stdout.read())
    else:
        stdout, stderr = proc.communicate()
    if proc.returncode != 0:
        command_str = ' '.join(command)
        if not ignore_failures:
            msg = 'Failed running command: {0} ({1}).'.format(
                   command_str, proc.stderr)
            raise RuntimeError(msg)
    return proc, stdout, stderr


def sudo(command, ignore_failures=False, out=False, workdir=None):
    if isinstance(command, str):
        command = shlex.split(command)
    command.insert(0, 'sudo')
    return run(command=command,
               ignore_failures=ignore_failures,
               out=out,
               workdir=workdir)


def install_sys_level(dependencies):
    dep_str = ' '.join(dependencies)
    sudo('apt-get install -y {0}'.format(dep_str))


def install_pip():
    sudo('pip install --upgrade pip')


def install_venv():
    sudo('pip install --upgrade virtualenv')


def clone(package_name, branch, org, clone_dir=REPOS_DIR):

    if not os.path.exists(clone_dir):
        run('mkdir {0}'.format(clone_dir))
    package_path = os.path.join(clone_dir, package_name)
    if not os.path.exists(package_path):
        clone_path = 'https://github.com/{0}/{1}.git'\
            .format(org, package_name)
        run('git clone {0} {1}'.format(clone_path, package_path))

    run('git checkout {0}'.format(branch), workdir=package_path)
    return package_path


def pip_install(package_name='',
                version=None,
                package_path='',
                venv_path=CLOUDIFY_VENV_PATH):
    pip_path = os.path.join(venv_path, 'bin', 'pip')
    if os.path.exists(package_path):
        run('{0} install --upgrade -e {1}'.format(pip_path, package_path))
    elif package_name:
        if version:
            full_package_name = '{0}=={1}'.format(package_name, version)
        run('{0} install {1}'.format(pip_path, full_package_name))
    else:
        raise RuntimeError('either package name or package path should be '
                           'provided.')


def pip_install_manager_deps(package_path, venv_path=CLOUDIFY_VENV_PATH):
    pip_install(package_path=os.path.join(package_path, 'rest-service'),
                venv_path=venv_path)
    pip_install(package_path=os.path.join(package_path, 'tests'),
                venv_path=venv_path)


def create_cloudify_venv():
    run('virtualenv {0}'.format(os.path.basename(CLOUDIFY_VENV_PATH)),
        workdir=os.path.dirname(CLOUDIFY_VENV_PATH))
    return CLOUDIFY_VENV_PATH
