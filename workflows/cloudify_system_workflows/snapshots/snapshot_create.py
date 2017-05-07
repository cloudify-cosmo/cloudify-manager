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
import shutil
import tempfile

from cloudify.workflows import ctx
from cloudify.manager import get_rest_client
from cloudify.constants import FILE_SERVER_SNAPSHOTS_FOLDER

from . import utils
from . import constants
from .agents import Agents
from .influxdb import InfluxDB
from .postgres import Postgres
from .credentials import Credentials


class SnapshotCreate(object):
    def __init__(self,
                 snapshot_id,
                 config,
                 include_metrics,
                 include_credentials):
        self._snapshot_id = snapshot_id
        self._config = utils.DictToAttributes(config)
        self._include_metrics = include_metrics
        self._include_credentials = include_credentials

        self._tempdir = None
        self._client = get_rest_client()

    def create(self):
        self._tempdir = tempfile.mkdtemp('-snapshot-data')
        metadata = dict()
        try:
            manager_version = utils.get_manager_version(self._client)
            schema_revision = utils.db_schema_get_current_revision()
            stage_schema_revision = \
                utils.stage_db_schema_get_current_revision()

            self._dump_files()
            self._dump_postgres()
            self._dump_influxdb()
            self._dump_credentials()
            self._dump_metadata(metadata,
                                manager_version,
                                schema_revision,
                                stage_schema_revision)
            self._dump_agents(manager_version)

            self._create_archive()
            self._update_snapshot_status(self._config.created_status)
            ctx.logger.info('Snapshot created successfully')
        except BaseException, e:
            self._update_snapshot_status(self._config.failed_status, str(e))
            ctx.logger.error('Snapshot creation failed: {0}'.format(str(e)))
        finally:
            ctx.logger.debug('Removing temp dir: {0}'.format(self._tempdir))
            shutil.rmtree(self._tempdir)

    def _update_snapshot_status(self, status, error=None):
        self._client.snapshots.update_status(
            self._snapshot_id,
            status=status,
            error=error
        )

    def _dump_files(self):
        ctx.logger.info('Dumping files to the archive from the manager')
        utils.copy_files_between_manager_and_snapshot(
            self._tempdir,
            self._config,
            to_archive=True
        )

    def _dump_postgres(self):
        ctx.logger.info('Dumping Postgres data')
        with Postgres(self._config) as postgres:
            postgres.dump(self._tempdir)
            postgres.dump_stage(self._tempdir)

    def _dump_influxdb(self):
        ctx.logger.info('Dumping InfluxDB data')
        if self._include_metrics:
            InfluxDB.dump(self._tempdir)

    def _dump_credentials(self):
        ctx.logger.info('Dumping credentials data')
        if self._include_credentials:
            Credentials().dump(self._tempdir)

    def _dump_metadata(self,
                       metadata,
                       manager_version,
                       schema_revision,
                       stage_schema_revision):
        ctx.logger.info('Dumping metadata')
        metadata[constants.M_VERSION] = str(manager_version)
        metadata[constants.M_SCHEMA_REVISION] = schema_revision
        if stage_schema_revision:
            metadata[constants.M_STAGE_SCHEMA_REVISION] = stage_schema_revision
        metadata_filename = os.path.join(
            self._tempdir,
            constants.METADATA_FILENAME
        )
        with open(metadata_filename, 'w') as f:
            json.dump(metadata, f)

    def _dump_agents(self, manager_version):
        ctx.logger.info('Dumping agents data')
        Agents().dump(self._tempdir, self._client, manager_version)

    def _create_archive(self):
        snapshot_archive_name = self._get_snapshot_archive_name()
        ctx.logger.info(
            'Creating snapshot archive: {0}'.format(snapshot_archive_name))
        utils.make_zip64_archive(snapshot_archive_name, self._tempdir)

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
