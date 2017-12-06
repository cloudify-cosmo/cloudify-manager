#########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
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
import glob
import shlex
import tempfile
import subprocess

from ..config import config
from ..logger import get_logger
from ..exceptions import BootstrapError

logger = get_logger('utils')


def run(command, retries=0, stdin=b'', ignore_failures=False,
        globx=False, shell=False, env=None, stdout=None):
    # TODO: add ability to *log* output, instead of just printing to stdout
    if isinstance(command, str) and not shell:
        command = shlex.split(command)
    stderr = subprocess.PIPE
    stdout = stdout or subprocess.PIPE
    if globx:
        glob_command = []
        for arg in command:
            glob_command.append(glob.glob(arg))
        command = glob_command
    logger.debug('Running: {0}'.format(command))
    proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=stdout,
                            stderr=stderr, shell=shell, env=env)
    proc.aggr_stdout, proc.aggr_stderr = proc.communicate(input=stdin)
    if proc.returncode != 0:
        command_str = ' '.join(command)
        if retries:
            logger.warn('Failed running command: {0}. Retrying. '
                        '({1} left)'.format(command_str, retries))
            proc = run(command, retries - 1)
        elif not ignore_failures:
            msg = 'Failed running command: {0} ({1}).'.format(
                command_str, proc.aggr_stderr)
            raise BootstrapError(msg)
    return proc


def sudo(command, *args, **kwargs):
    if isinstance(command, str):
        command = shlex.split(command)
    if 'env' in kwargs:
        command = ['sudo', '-E'] + command
    else:
        command.insert(0, 'sudo')
    return run(command=command, *args, **kwargs)


def mkdir(folder, use_sudo=True):
    if os.path.isdir(folder):
        return
    logger.debug('Creating Directory: {0}'.format(folder))
    cmd = ['mkdir', '-p', folder]
    if use_sudo:
        sudo(cmd)
    else:
        run(cmd)


def chmod(mode, path, recursive=False):
    logger.debug('chmoding {0}: {1}'.format(path, mode))
    command = ['chmod']
    if recursive:
        command.append('-R')
    command += [mode, path]
    sudo(command)


def chown(user, group, path):
    logger.debug('chowning {0} by {1}:{2}...'.format(
        path, user, group))
    sudo(['chown', '-R', '{0}:{1}'.format(user, group), path])


def remove(path, ignore_failure=False):
    logger.debug('Removing {0}...'.format(path))
    sudo(['rm', '-rf', path], ignore_failures=ignore_failure)


def untar(source,
          destination=None,
          skip_old_files=False,
          unique_tmp_dir=False):
    if not destination:
        destination = tempfile.mkdtemp() if unique_tmp_dir else '/tmp'
        config.add_temp_path_to_clean(destination)
    logger.debug('Extracting {0} to {1}...'.format(
        source, destination))
    tar_command = ['tar', '-xvf', source, '-C', destination, '--strip=1']
    if skip_old_files:
        tar_command.append('--skip-old-files')
    sudo(tar_command)

    return destination


def copy(source, destination):
    destination_dir = os.path.dirname(destination)
    if not os.path.exists(destination_dir):
        logger.debug(
            'Path does not exist: {0}. Creating it...'.format(
                destination_dir))
        sudo(['mkdir', '-p', destination_dir])
    sudo(['cp', '-rp', source, destination])


# idempotent move operation
def move(source, destination, rename_only=False):
    if rename_only:
        sudo(['mv', '-T', source, destination])
    else:
        copy(source, destination)
        remove(source)
