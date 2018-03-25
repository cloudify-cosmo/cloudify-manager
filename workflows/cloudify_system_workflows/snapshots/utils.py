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
import json
import shlex
import shutil
import zipfile
import subprocess
import contextlib

from cloudify.workflows import ctx
from cloudify import constants, manager
from . import constants as snapshot_constants
from .constants import SECURITY_FILE_LOCATION, SECURITY_FILENAME
from cloudify.utils import ManagerVersion, get_local_rest_certificate
from cloudify.utils import get_tenant_name, internal as internal_utils

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
        except Exception:
            return self._dict


def copy_files_between_manager_and_snapshot(archive_root,
                                            config,
                                            to_archive=True,
                                            tenant_name=None):
    """
    Copy files/dirs between snapshot/manager and manager/snapshot.

    :param archive_root: Path to the snapshot archive root.
    :param config: Config of manager.
    :param to_archive: If True then copying is from manager to snapshot,
        otherwise from snapshot to manager.
    :param tenant_name: If passed, will restore files to this tenant name.
        Expected to be used only for 3.x upgrades.
    """
    ctx.logger.info('Copying files/directories...')

    data_to_copy = [
        constants.FILE_SERVER_BLUEPRINTS_FOLDER,
        constants.FILE_SERVER_DEPLOYMENTS_FOLDER,
        constants.FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
        constants.FILE_SERVER_PLUGINS_FOLDER,
    ]

    # To work with cert dir logic for archiving
    if tenant_name:
        # This is a 3.x install, files go in tenant folders
        data_to_copy = [
            (
                # The root path to copy the files to in the manager for each
                # type of restored file
                # e.g. blueprints/<tenant_name>/
                os.path.join(path, tenant_name)
                # Plugins are an exception as they are all stored in one path
                # under UUIDs without tenant names
                if path != constants.FILE_SERVER_PLUGINS_FOLDER else path,
                # The path of the file type in the snapshot
                path,
            ) for path in data_to_copy
        ]
    else:
        # This is a 4.x+ install, files go where they went.
        data_to_copy = [(path, path) for path in data_to_copy]

    local_cert_dir = os.path.dirname(get_local_rest_certificate())
    if to_archive:
        data_to_copy.append((local_cert_dir,
                             snapshot_constants.ARCHIVE_CERT_DIR))
        data_to_copy.append((SECURITY_FILE_LOCATION, SECURITY_FILENAME))

    ctx.logger.info(str(data_to_copy))
    for p1, p2 in data_to_copy:
        # first expand relative paths
        if p1[0] != '/':
            p1 = os.path.join(config.file_server_root, p1)
        if p2[0] != '/':
            p2 = os.path.join(archive_root, p2)

        # make p1 to always point to source and p2 to target of copying
        if not to_archive:
            p1, p2 = p2, p1

        copy_snapshot_path(p1, p2)


def copy_stage_files(archive_root):
    """Copy Cloudify Stage files into the snapshot"""
    stage_data = [
        snapshot_constants.STAGE_CONFIG_FOLDER,
        snapshot_constants.STAGE_USERDATA_FOLDER
    ]
    for folder in stage_data:
        copy_snapshot_path(
            os.path.join(snapshot_constants.STAGE_BASE_FOLDER, folder),
            os.path.join(archive_root, 'stage', folder))


def restore_stage_files(archive_root, override=False):
    """Copy Cloudify Stage files from the snapshot archive to stage folder.

    Note that only the stage user can write into the stage directory,
    so we use sudo to run a script (created during bootstrap) that copies
    the restored files.
    """
    stage_archive = os.path.join(archive_root, 'stage')
    if not os.path.exists(stage_archive):
        # no stage files in the snapshot archive - nothing to do
        # (perhaps the snapshot was made before stage was included in it?)
        return
    # let's not give everyone full read access to the snapshot, instead,
    # copy only the stage-related parts and give the stage user read access
    # to those
    stage_tempdir = '{0}_stage'.format(archive_root)
    shutil.copytree(stage_archive, stage_tempdir)
    run(['/bin/chmod', 'a+r', '-R', stage_tempdir])
    try:
        sudo(
            [
                snapshot_constants.MANAGER_PYTHON,
                snapshot_constants.STAGE_TOKEN_SCRIPT
            ],
            user=snapshot_constants.STAGE_USER,
        )
        restore_command = [snapshot_constants.STAGE_RESTORE_SCRIPT,
                           stage_tempdir]
        if override:
            restore_command.append('--override-existing')
        sudo(restore_command,
             user=snapshot_constants.STAGE_USER)
    finally:
        shutil.rmtree(stage_tempdir)

    sudo(['/usr/bin/systemctl', 'restart', 'cloudify-stage'],
         ignore_failures=True)


def copy_composer_files(archive_root):
    """Copy Cloudify Composer files into the snapshot"""
    composer_data = [
        snapshot_constants.COMPOSER_CONFIG_FOLDER,
        snapshot_constants.COMPOSER_BLUEPRINTS_FOLDER,
    ]
    for folder in composer_data:
        copy_snapshot_path(
            os.path.join(snapshot_constants.COMPOSER_BASE_FOLDER, folder),
            os.path.join(archive_root, 'composer', folder))


def restore_composer_files(archive_root):
    """Copy Composer files from the snapshot archive to Composer folder.
    """
    composer_archive = os.path.join(archive_root, 'composer')
    if not os.path.exists(composer_archive):
        # no composer files in the snapshot archive - nothing to do
        # (perhaps the snapshot was made before composer was included in it?)
        return
    composer_data = [
        snapshot_constants.COMPOSER_CONFIG_FOLDER,
        snapshot_constants.COMPOSER_BLUEPRINTS_FOLDER,
    ]
    for folder in composer_data:
        dest_path = os.path.join(snapshot_constants.COMPOSER_BASE_FOLDER,
                                 folder)
        copied = copy_snapshot_path(
            os.path.join(archive_root, 'composer', folder),
            dest_path)
        if copied:
            run(['/bin/chmod', '-R', 'g+w', dest_path])


def copy_snapshot_path(source, destination):
    # source doesn't need to exist, then ignore
    if not os.path.exists(source):
        ctx.logger.warning('Source not found: {0}. Skipping...'.format(source))
        return False
    ctx.logger.debug(
        'Copying from dump: {0} to: {1}..'.format(source, destination))
    # copy data
    if os.path.isfile(source):
        shutil.copy(source, destination)
    else:
        if os.path.exists(destination):
            shutil.rmtree(destination)
        shutil.copytree(source, destination)
    return True


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


def sudo(command, user=None, ignore_failures=False):
    if isinstance(command, str):
        command = shlex.split(command)
    if user is not None:
        command = ['sudo', '-u', user] + command
    else:
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


def get_tenants_list():
    client = manager.get_rest_client(snapshot_constants.DEFAULT_TENANT_NAME)
    version = client.manager.get_version()
    if version['edition'] != 'premium':
        return [snapshot_constants.DEFAULT_TENANT_NAME]
    tenants = client.tenants.list(_include=['name'], _get_all_results=True)
    return [tenant.name for tenant in tenants]


def get_dep_contexts(version):
    deps = {}
    tenants = [get_tenant_name()] if version < snapshot_constants.V_4_0_0 \
        else get_tenants_list()
    for tenant_name in tenants:
        # Temporarily assign the context a different tenant name so that
        # we can retrieve that tenant's deployment contexts
        with internal_utils._change_tenant(ctx, tenant_name):
            # We have to zero this out each time or the cached version for
            # the previous tenant will be used
            ctx._dep_contexts = None

            # Get deployment contexts for this tenant
            deps[tenant_name] = ctx.deployments_contexts
    return deps.items()


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


@contextlib.contextmanager
def db_schema(revision, config=None):
    """Downgrade schema to desired revision to perform operation and upgrade.

    Used when restoring a snapshot to make sure the restore operation happens
    whith the same version of the schema that was used when the snapshot was
    created.

    :param revision: Revision to downgrade to before performing any operation.
    :type revision: str

    """
    db_schema_downgrade(revision, config=config)
    yield
    db_schema_upgrade(config=config)


def db_schema_downgrade(revision='-1', config=None):
    """Downgrade database schema.

    Used before restoring a snapshot to make sure that the schema matches the
    one that was used when the snapshot was created.

    :param revision: Revision to downgrade to.
    :type revision: str

    """
    _schema(config, ['downgrade', revision])


def db_schema_upgrade(revision='head', config=None):
    """Upgrade database schema.

    Used after restoring snapshot to get an up-to-date schema.

    :param revision: Revision to upgrade to.
    :type revision: str

    """
    _schema(config, ['upgrade', revision])


def db_schema_get_current_revision(config=None):
    """Get database schema revision.

    :returns: Current revision
    :rtype: str

    """
    output = _schema(config, ['current'])
    revision = output.split(' ', 1)[0]
    return revision


def _schema(config, command):
    full_command = [PYTHON_MANAGER_ENV, SCHEMA_SCRIPT]
    if config:
        for arg, value in [
            ('--postgresql-host', config.postgresql_host),
            ('--postgresql-username', config.postgresql_username),
            ('--postgresql-password', config.postgresql_password),
            ('--postgresql-db-name', config.postgresql_db_name),
        ]:
            if value:
                full_command += [arg, value]
    full_command += command
    return subprocess.check_output(full_command)


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


def composer_db_schema_get_current_revision():
    """Get composer database schema revision.

    :returns: Current revision
    :rtype: str

    """
    client = manager.get_rest_client()
    version = client.manager.get_version()
    if version['edition'] != 'premium':
        return None
    output = subprocess.check_output([
        '/opt/nodejs/bin/npm',
        'run',
        '--prefix', snapshot_constants.COMPOSER_BASE_FOLDER,
        'db-migrate-current'
    ])
    # the revision is in the last line of the output
    # (it's actually -2, because -1 is just an empty line)
    revision = output.split('\n')[-2].strip()
    return revision
