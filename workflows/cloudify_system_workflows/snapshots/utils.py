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

import contextlib
import os
import json
import shlex
import shutil
import subprocess
import zipfile

from cloudify import constants, manager
from cloudify.workflows import ctx
from .constants import ARCHIVE_CERT_DIR
from cloudify.utils import ManagerVersion, get_local_rest_certificate

# Path to python binary in the manager environment
PYTHON_MANAGER_ENV = '/opt/manager/env/bin/python'
# Path to database migration script
SCHEMA_SCRIPT = '/opt/manager/resources/cloudify/migrations/schema.py'


class DictToAttributes(object):
    def __init__(self, dic):
        self._dict = dic

    def __getattr__(self, name):
        return self._dict[name]

    def __str__(self):
        try:
            # try to convert to json,
            # may fail on UTF-8 and stuff, don't sweat on it..
            return json.dumps(self._dict)
        except:
            return self._dict


def copy_files_between_manager_and_snapshot(archive_root,
                                            config,
                                            to_archive=True,
                                            new_tenant=''):
    """
    Copy files/dirs between snapshot/manager and manager/snapshot.

    :param archive_root: Path to the snapshot archive root.
    :param config: Config of manager.
    :param to_archive: If True then copying is from manager to snapshot,
        otherwise from snapshot to manager.
    :param new_tenant: a tenant to which the snapshot is restored.
        Relevant only in the case of restoring a snapshot from a manager
        of a version older than 4.0.0
    """
    ctx.logger.info('Copying files/directories...')

    # Files/dirs with constant relative/absolute paths,
    # where first path is path in manager, second is path in snapshot.
    # If paths are relative then should be relative to file server (path
    # in manager) and snapshot archive (path in snapshot). If paths are
    # absolute then should point to proper data in manager/snapshot archive
    data_to_copy = [
        (os.path.join(
            constants.FILE_SERVER_BLUEPRINTS_FOLDER, new_tenant),
         constants.FILE_SERVER_BLUEPRINTS_FOLDER),
        (os.path.join(
            constants.FILE_SERVER_DEPLOYMENTS_FOLDER, new_tenant),
         constants.FILE_SERVER_DEPLOYMENTS_FOLDER),
        (os.path.join(
            constants.FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER, new_tenant),
         constants.FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER),
        (constants.FILE_SERVER_PLUGINS_FOLDER,
         constants.FILE_SERVER_PLUGINS_FOLDER)
    ]

    local_cert_dir = os.path.dirname(get_local_rest_certificate())
    if to_archive:
        data_to_copy.append((local_cert_dir, ARCHIVE_CERT_DIR))

    for (p1, p2) in data_to_copy:
        # first expand relative paths
        if p1[0] != '/':
            p1 = os.path.join(config.file_server_root, p1)
        if p2[0] != '/':
            p2 = os.path.join(archive_root, p2)

        # make p1 to always point to source and p2 to target of copying
        if not to_archive:
            p1, p2 = p2, p1

        copy_snapshot_path(p1, p2)


def copy_snapshot_path(source, destination):
        # source doesn't need to exist, then ignore
        if not os.path.exists(source):
            return
        ctx.logger.debug(
            'Copying from dump: {0} to: {1}..'.format(source, destination))
        # copy data
        if os.path.isfile(source):
            shutil.copy(source, destination)
        else:
            if os.path.exists(destination):
                shutil.rmtree(destination)
            shutil.copytree(source, destination)


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


def run(command, ignore_failures=False, redirect_output_path=None, cwd=None):
    if isinstance(command, str):
        command = shlex.split(command)
    command_str = ' '.join(command)

    ctx.logger.debug('Running command: {0}'.format(command_str))
    stderr = subprocess.PIPE
    stdout = subprocess.PIPE
    if redirect_output_path:
        ctx.logger.debug('Command: {0} Redirect output to: {1}'.
                         format(' '.join(command), redirect_output_path))
        with open(redirect_output_path, 'a') as output:
            proc = subprocess.Popen(command, stdout=output, stderr=stderr,
                                    cwd=cwd)
    else:
        proc = subprocess.Popen(command, stdout=stdout, stderr=stderr, cwd=cwd)

    proc.aggr_stdout, proc.aggr_stderr = proc.communicate()
    if proc and proc.returncode != 0:
        if not ignore_failures:
            msg = 'Failed running command: {0} ({1}).'.format(
                command_str, proc.aggr_stderr)
            raise RuntimeError(msg)
    return proc


def get_manager_version(client):
    return ManagerVersion(client.manager.get_version()['version'])


def is_compute(node):
    return constants.COMPUTE_NODE_TYPE in node.type_hierarchy


def make_zip64_archive(zip_filename, directory):
    """Create zip64 archive that contains all files in a directory.

    zip64 is a set of extensions on top of the zip file format that allows to
    have files larger than 2GB. This is important in snapshots where the amount
    of data to backup might be huge.

    Note that `shutil` provides a method to register new formats based on the
    extension of the target file, since a `.zip` extension is still desired,
    using such an extension mechanism is not an option to avoid patching the
    already registered zip format.

    In any case, this function is heavily inspired in stdlib's
    `shutil._make_zipfile`.

    :param zip_filename: Path to the zip file to be created
    :type zip_filename: str
    :path directory: Path to directory where all files to compress are located
    :type directory: str

    """
    zip_context_manager = zipfile.ZipFile(
        zip_filename,
        'w',
        compression=zipfile.ZIP_DEFLATED,
        allowZip64=True,
    )

    with zip_context_manager as zip_file:
        path = os.path.normpath(directory)
        ctx.logger.debug('Creating zip archive of: {0}'.format(path))
        base_dir = path
        for dirpath, dirnames, filenames in os.walk(directory):
            for dirname in sorted(dirnames):
                path = os.path.normpath(os.path.join(dirpath, dirname))
                zip_file.write(path, os.path.relpath(path, base_dir))
            for filename in filenames:
                path = os.path.normpath(os.path.join(dirpath, filename))
                # Not sure why this check is needed,
                # but it's in the original stdlib's implementation
                if os.path.isfile(path):
                    zip_file.write(path, os.path.relpath(path, base_dir))


def compare_cert_metadata(path1, path2):
    metadata_filename = 'certificate_metadata'
    path1 = os.path.join(path1, metadata_filename)
    path2 = os.path.join(path2, metadata_filename)
    if not os.path.exists(path1) or not os.path.exists(path2):
        return False
    with open(path1) as f:
        content1 = f.read()
    with open(path2) as f:
        content2 = f.read()
    return content1 == content2


@contextlib.contextmanager
def db_schema(revision):
    """Downgrade schema to desired revision to perform operation and upgrade.

    Used when restoring a snapshot to make sure the restore operation happens
    whith the same version of the schema that was used when the snapshot was
    created.

    :param revision: Revision to downgrade to before performing any operation.
    :type revision: str

    """
    db_schema_downgrade(revision)
    yield
    db_schema_upgrade()


def db_schema_downgrade(revision='-1'):
    """Downgrade database schema.

    Used before restoring a snapshot to make sure that the schema matches the
    one that was used when the snapshot was created.

    :param revision: Revision to downgrade to.
    :type revision: str

    """
    subprocess.check_call([
        PYTHON_MANAGER_ENV,
        SCHEMA_SCRIPT,
        'downgrade',
        revision,
    ])


def db_schema_upgrade(revision='head'):
    """Upgrade database schema.

    Used after restoring snapshot to get an up-to-date schema.

    :param revision: Revision to upgrade to.
    :type revision: str

    """
    subprocess.check_call([
        PYTHON_MANAGER_ENV,
        SCHEMA_SCRIPT,
        'upgrade',
        revision,
    ])


def db_schema_get_current_revision():
    """Get database schema revision.

    :returns: Current revision
    :rtype: str

    """
    output = subprocess.check_output([
        PYTHON_MANAGER_ENV,
        SCHEMA_SCRIPT,
        'current',
    ])
    revision = output.split(' ', 1)[0]
    return revision


def stage_db_schema_get_current_revision():
    """Get stage database schema revision.

    :returns: Current revision
    :rtype: str

    """
    client = manager.get_rest_client()
    version = client.manager.get_version()
    if version['edition'] != 'premium':
        return None
    output = subprocess.check_output([
        '/opt/nodejs/bin/node',
        '/opt/cloudify-stage/backend/migration.js',
        'current',
    ])
    revision = output.strip()
    return revision
