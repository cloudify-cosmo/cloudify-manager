########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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
import shlex
import shutil
import subprocess

from cloudify.workflows import ctx


class DictToAttributes(object):
    def __init__(self, dic):
        self._dict = dic

    def __getattr__(self, name):
        return self._dict[name]


def copy_data(archive_root, config, to_archive=True):
    """
    Copy files/dirs between snapshot/manager and manager/snapshot.

    :param archive_root: Path to the snapshot archive root.
    :param config: Config of manager.
    :param to_archive: If True then copying is from manager to snapshot,
        otherwise from snapshot to manager.
    """
    ctx.logger.info('Copying data..')

    # Files/dirs with constant relative/absolute paths,
    # where first path is path in manager, second is path in snapshot.
    # If paths are relative then should be relative to file server (path
    # in manager) and snapshot archive (path in snapshot). If paths are
    # absolute then should point to proper data in manager/snapshot archive
    data_to_copy = [
        (config.file_server_blueprints_folder, 'blueprints'),
        (config.file_server_deployments_folder, 'deployments'),
        (config.file_server_uploaded_blueprints_folder, 'uploaded-blueprints'),
        (config.file_server_uploaded_plugins_folder, 'plugins')
    ]

    for (p1, p2) in data_to_copy:
        # first expand relative paths
        if p1[0] != '/':
            p1 = os.path.join(config.file_server_root, p1)
        if p2[0] != '/':
            p2 = os.path.join(archive_root, p2)

        # make p1 to always point to source and p2 to target of copying
        if not to_archive:
            p1, p2 = p2, p1

        # source doesn't need to exist, then ignore
        if not os.path.exists(p1):
            continue

        ctx.logger.debug('Copying from dump: {0} to: {1}..'.format(p1, p2))

        # copy data
        if os.path.isfile(p1):
            shutil.copy(p1, p2)
        else:
            if not os.path.exists(p2):
                os.makedirs(p2)

            for item in os.listdir(p1):
                s = os.path.join(p1, item)
                d = os.path.join(p2, item)
                # The only case when it is possible that `d` exists is when
                # restoring snapshot with plugins on the same manager this
                # snapshot was created on. It means it is the same plugin so
                # we are ok with not copying it.
                if not os.path.exists(d):
                    if os.path.isdir(s):
                        shutil.copytree(s, d)
                    else:
                        shutil.copy2(s, d)


def copy(source, destination):
    ctx.logger.debug('Copying {0} to {1}..'.format(source,
                                                   destination))
    destination_dir = os.path.dirname(destination)
    if not os.path.exists(destination_dir):
        ctx.logger.debug(
            'Path does not exist: {0}. Creating it...'.format(
                destination_dir))
        sudo(['mkdir', '-p', destination_dir])
    sudo(['cp', '-rp', source, destination])


def sudo(command, ignore_failures=False):
    if isinstance(command, str):
        command = shlex.split(command)
    command.insert(0, 'sudo')
    return run(command=command, ignore_failures=ignore_failures)


def run(command, ignore_failures=False, redirect_output_path=None):
    if isinstance(command, str):
        command = shlex.split(command)
    ctx.logger.debug('Running command: {0}'.format(' '.join(command)))
    stderr = subprocess.PIPE
    stdout = subprocess.PIPE
    if redirect_output_path:
        ctx.logger.debug('Command: {0} Redirect output to: {1}'.
                         format(' '.join(command), redirect_output_path))
        with open(redirect_output_path, 'a') as output:
            proc = subprocess.Popen(command, stdout=output, stderr=stderr)
            proc.aggr_stdout, proc.aggr_stderr = proc.communicate()
    else:
        proc = subprocess.Popen(command, stdout=stdout, stderr=stderr)
        proc.aggr_stdout, proc.aggr_stderr = proc.communicate()
    if proc and proc.returncode != 0:
        command_str = ' '.join(command)
        if not ignore_failures:
            msg = 'Failed running command: {0} ({1}).'.format(
                command_str, proc.aggr_stderr)
            raise RuntimeError(msg)
    return proc
