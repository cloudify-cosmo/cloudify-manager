import os
import json
import shutil
import tempfile

from cloudify.workflows import ctx
from cloudify.manager import get_rest_client
from cloudify.constants import FILE_SERVER_SNAPSHOTS_FOLDER
from cloudify.zip_utils import make_zip64_archive

from . import constants, networks, utils
from .agents import Agents
from .postgres import Postgres
from .credentials import Credentials


class LegacySnapshotCreate(object):
    def __init__(self,
                 snapshot_id,
                 config,
                 include_credentials,
                 include_logs,
                 include_events,
                 tempdir_path=None):
        self._snapshot_id = snapshot_id
        self._config = utils.DictToAttributes(config)
        self._include_credentials = include_credentials
        self._include_logs = include_logs
        self._include_events = include_events
        self._tempdir_path = tempdir_path
        self._tempdir = None
        self._client = get_rest_client()

    def create(self):
        ctx.logger.debug('Using `legacy` snapshot format')
        self._tempdir = tempfile.mkdtemp('-snapshot-data',
                                         dir=self._tempdir_path)
        metadata = dict()
        try:
            manager_version = utils.get_manager_version(self._client)
            schema_revision = utils.db_schema_get_current_revision(
                config=self._config)
            stage_schema_revision = \
                utils.stage_db_schema_get_current_revision()
            composer_schema_revision = \
                utils.composer_db_schema_get_current_revision()

            utils.sudo(constants.ALLOW_DB_CLIENT_CERTS_SCRIPT)
            self._dump_files()
            utils.sudo(constants.DENY_DB_CLIENT_CERTS_SCRIPT)
            self._dump_postgres()
            self._dump_networks()
            self._dump_credentials(manager_version)
            self._dump_metadata(metadata,
                                manager_version,
                                schema_revision,
                                stage_schema_revision,
                                composer_schema_revision)
            self._dump_agents(manager_version)

            self._create_archive()
            self._update_snapshot_status(self._config.created_status)
            ctx.logger.info('Snapshot created successfully')
        except BaseException as e:
            self._update_snapshot_status(self._config.failed_status, str(e))
            ctx.logger.error('Snapshot creation failed: {0}'.format(str(e)))
            raise
        finally:
            ctx.logger.debug('Removing temp dir: {0}'.format(self._tempdir))
            shutil.rmtree(self._tempdir)

    def _update_snapshot_status(self, status, error=None):
        self._client.snapshots.update_status(
            self._snapshot_id,
            status=status,
            error=error
        )

    def _dump_networks(self):
        ctx.logger.info('Dumping network data')
        networks.dump_networks(self._tempdir, self._client)

    def _dump_files(self):
        ctx.logger.info('Dumping files to the archive from the manager')
        utils.copy_files_between_manager_and_snapshot(
            self._tempdir,
            self._config,
            to_archive=True
        )
        utils.copy_stage_files(self._tempdir)
        utils.copy_composer_files(self._tempdir)

    def _dump_postgres(self):
        ctx.logger.info('Dumping Postgres data')
        with Postgres(self._config) as postgres:
            postgres.dump(self._tempdir,
                          self._include_logs,
                          self._include_events)
            postgres.dump_stage(self._tempdir)
            postgres.dump_composer(self._tempdir)

    def _dump_credentials(self, manager_version):
        ctx.logger.info('Dumping credentials data')
        if self._include_credentials:
            Credentials().dump(self._tempdir, manager_version)

    def _dump_metadata(self,
                       metadata,
                       manager_version,
                       schema_revision,
                       stage_schema_revision,
                       composer_schema_revision):
        ctx.logger.info('Dumping metadata')
        metadata[constants.M_VERSION] = str(manager_version)
        metadata[constants.M_SCHEMA_REVISION] = schema_revision
        if stage_schema_revision:
            metadata[constants.M_STAGE_SCHEMA_REVISION] = stage_schema_revision
        if composer_schema_revision:
            metadata[constants.M_COMPOSER_SCHEMA_REVISION] = \
                composer_schema_revision
        metadata_filename = os.path.join(
            self._tempdir,
            constants.METADATA_FILENAME
        )
        with open(metadata_filename, 'w') as f:
            json.dump(metadata, f)

    def _dump_agents(self, manager_version):
        ctx.logger.info('Dumping agents data')
        Agents().dump(self._tempdir, manager_version)

    def _create_archive(self):
        snapshot_archive_name = self._get_snapshot_archive_name()
        ctx.logger.info(
            'Creating snapshot archive: {0}'.format(snapshot_archive_name))
        make_zip64_archive(snapshot_archive_name, self._tempdir)

    def _get_snapshot_archive_name(self):
        """Return the base name for the snapshot archive
        """
        snapshots_dir = self._get_and_create_snapshots_dir()
        snapshot_dir = os.path.join(snapshots_dir, self._snapshot_id)
        os.makedirs(snapshot_dir)
        return os.path.join(snapshot_dir, '{}.zip'.format(self._snapshot_id))

    def _get_and_create_snapshots_dir(self):
        """Create (if necessary) and return the snapshots directory
        """
        snapshots_dir = os.path.join(
            self._config.file_server_root,
            FILE_SERVER_SNAPSHOTS_FOLDER
        )
        if not os.path.exists(snapshots_dir):
            os.makedirs(snapshots_dir)
        return snapshots_dir
