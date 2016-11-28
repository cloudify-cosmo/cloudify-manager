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
import zipfile
import platform
import tempfile

from wagon import wagon

from cloudify.workflows import ctx
from cloudify.utils import ManagerVersion
from cloudify.manager import get_rest_client
from cloudify.exceptions import NonRecoverableError

from cloudify_system_workflows import plugins
from cloudify_system_workflows.deployment_environment import \
    generate_create_dep_tasks_graph

from . import utils
from .agents import Agents
from .influxdb import InfluxDB
from .postgres import Postgres
from .credentials import Credentials
from .es_snapshot import ElasticSearch
from .constants import METADATA_FILENAME, M_VERSION


class SnapshotRestore(object):
    _4_0_0_VERSION = ManagerVersion('4.0.0')

    def __init__(self,
                 config,
                 snapshot_id,
                 recreate_deployments_envs,
                 force,
                 timeout):
        self._config = utils.DictToAttributes(config)
        self._snapshot_id = snapshot_id
        self._recreate_deployments_envs = recreate_deployments_envs
        self._force = force
        self._timeout = timeout

        self._tempdir = None
        self._client = get_rest_client()

    def restore(self):
        self._assert_empty_db()
        self._tempdir = tempfile.mkdtemp('-snapshot-data')
        snapshot_path = self._get_snapshot_path()
        try:
            metadata = self._extract_snapshot_archive(snapshot_path)
            snapshot_version = self._get_snapshot_version(metadata)
            existing_plugins = self._get_existing_plugin_names()
            existing_dep_envs = self._get_existing_dep_envs()
            es = utils.get_es_client(self._config)

            with Postgres(self._config) as postgres:
                self._restore_files_to_manager()
                self._restore_db(es, postgres, snapshot_version)
                self._restore_events(es, metadata)
                self._restore_plugins(existing_plugins)
                self._restore_influxdb()
                self._restore_credentials(postgres)
                self._restore_agents()
                self._restore_deployment_envs(existing_dep_envs)
        finally:
            ctx.logger.debug('Removing temp dir: {0}'.format(self._tempdir))
            shutil.rmtree(self._tempdir)

    def _restore_files_to_manager(self):
        ctx.logger.info('Restoring config from the archive to the manager')
        utils.copy_files_between_manager_and_snapshot(
            self._tempdir,
            self._config,
            to_archive=False
        )

    def _restore_db(self, es, postgres, snapshot_version):
        ctx.logger.info('Restoring database')
        if snapshot_version >= self._4_0_0_VERSION:
            postgres.restore(self._tempdir)
        else:
            postgres.create_clean_db()
            ElasticSearch.restore_db_from_pre_4_version(self._tempdir)
            es.indices.flush()

    def _extract_snapshot_archive(self, snapshot_path):
        """Extract the snapshot archive to a temp folder

        :param snapshot_path: Path to the snapshot archive
        :return: A dict representing the metadata json file
        """
        ctx.logger.debug('Extracting snapshot: {0}'.format(snapshot_path))
        with zipfile.ZipFile(snapshot_path, 'r') as zipf:
            zipf.extractall(self._tempdir)
        with open(os.path.join(self._tempdir, METADATA_FILENAME), 'r') as f:
            metadata = json.load(f)
        return metadata

    def _assert_empty_db(self):
        """Make sure no blueprints exist on the manager (no blueprints implies
        no deployments/executions corresponding to deployments)
        If there are blueprints then log a warning if `force` was passed in the
        restore command, or raise an error if not
        """
        if self._client.blueprints.list().items:
            if self._force:
                ctx.logger.warning(
                    "Forcing snapshot restoration on a dirty manager.")
            else:
                raise NonRecoverableError(
                    "Snapshot restoration on a dirty manager is not permitted."
                )

    def _get_snapshot_path(self):
        """Calculate the snapshot path from the config + snapshot ID
        """
        file_server_root = self._config.file_server_root
        snapshots_dir = os.path.join(
            file_server_root,
            self._config.file_server_snapshots_folder
        )
        return os.path.join(
            snapshots_dir,
            self._snapshot_id,
            '{0}.zip'.format(self._snapshot_id)
        )

    def _get_snapshot_version(self, metadata):
        """Get the snapshot version, and assert that it isn't newer than the
        manager version (raise an error if not)

        :param metadata: The metadata dict
        :return: The snapshot version
        """
        manager_version = utils.get_manager_version(self._client)
        snapshot_version = ManagerVersion(metadata[M_VERSION])
        ctx.logger.info('Manager version = {0}, snapshot version = {1}'.format(
            str(manager_version), str(snapshot_version)))
        if snapshot_version > manager_version:
            raise NonRecoverableError(
                'Cannot restore a newer manager\'s snapshot on this manager '
                '[{0} > {1}]'.format(str(snapshot_version),
                                     str(manager_version)))
        return snapshot_version

    @staticmethod
    def _version_at_least(version_a, version_b):
        return version_a.equals(ManagerVersion(version_b)) \
               or version_a.greater_than(ManagerVersion(version_b))

    def _get_existing_plugin_names(self):
        ctx.logger.debug('Collecting existing plugins')
        existing_plugins = self._client.plugins.list()
        return set(p.archive_name for p in existing_plugins)

    def _get_existing_dep_envs(self):
        return [dep.id for dep in self._client.deployments.list()]

    def _get_plugins_to_install(self, existing_plugins):
        """Return a list of plugins that need to be installed (meaning, they
        weren't installed on the manager before the restore and they *can* be
        installed on the manager)

        :param existing_plugins: Names of already installed plugins
        """
        def should_install(plugin):
            return plugin.archive_name not in existing_plugins \
                   and self._plugin_installable_on_current_platform(plugin)

        ctx.logger.debug('Looking for plugins to install')
        all_plugins = self._client.plugins.list()
        plugins_to_install = [p for p in all_plugins if should_install(p)]
        ctx.logger.debug('Found {0} plugins to install'
                         .format(len(plugins_to_install)))
        return plugins_to_install

    def _restore_plugins(self, existing_plugins):
        """Install any plugins that weren't installed prior to the restore

        :param existing_plugins: Names of already installed plugins
        """
        ctx.logger.info('Restoring plugins')
        plugins_to_install = self._get_plugins_to_install(existing_plugins)
        for plugin in plugins_to_install:
            plugins.install(ctx=ctx, plugin={
                'name': plugin['package_name'],
                'package_name': plugin['package_name'],
                'package_version': plugin['package_version']
            })

    @staticmethod
    def _plugin_installable_on_current_platform(plugin):
        dist, _, release = platform.linux_distribution(
            full_distribution_name=False)
        dist, release = dist.lower(), release.lower()
        return (plugin['supported_platform'] == 'any' or all([
            plugin['supported_platform'] == wagon.utils.get_platform(),
            plugin['distribution'] == dist,
            plugin['distribution_release'] == release
        ]))

    def _restore_events(self, es, metadata):
        ctx.logger.info('Restoring ElasticSearch data '
                        '[timeout={0} sec]'.format(self._timeout))
        ElasticSearch().restore_logs_and_events(
            es,
            self._tempdir,
            metadata,
            bulk_read_timeout=self._timeout
        )

    def _restore_influxdb(self):
        ctx.logger.info('Restoring InfluxDB metrics')
        InfluxDB.restore(self._tempdir)

    def _restore_credentials(self, postgres):
        ctx.logger.info('Restoring credentials')
        Credentials().restore(self._tempdir, postgres)

    def _restore_agents(self):
        ctx.logger.info('Restoring cloudify agent data')
        Agents().restore(self._tempdir, self._client)

    def _restore_deployment_envs(self, existing_dep_envs):
        """Restore any deployment environments on the manager that didn't
        exist before restoring the snapshot

        :param existing_dep_envs: A list of deployment ID of environments that
        existed prior to the restore
        """
        ctx.logger.info('Restoring deployment environments')
        for deployment_id, dep_ctx in ctx.deployments_contexts.iteritems():
            if deployment_id in existing_dep_envs:
                continue
            with dep_ctx:
                dep = self._client.deployments.get(deployment_id)
                blueprint = self._client.blueprints.get(dep_ctx.blueprint.id)
                tasks_graph = self._get_tasks_graph(dep_ctx, blueprint, dep)
                tasks_graph.execute()
                ctx.logger.debug('Successfully created deployment environment '
                                 'for deployment {0}'.format(deployment_id))

    @staticmethod
    def _get_tasks_graph(dep_ctx, blueprint, deployment):
        """Create a deployment creation tasks graph
        """
        blueprint_plan = blueprint['plan']
        return generate_create_dep_tasks_graph(
            dep_ctx,
            deployment_plugins_to_install=blueprint_plan[
                'deployment_plugins_to_install'],
            workflow_plugins_to_install=blueprint_plan[
                'workflow_plugins_to_install'],
            policy_configuration={
                'policy_types': deployment['policy_types'],
                'policy_triggers': deployment['policy_triggers'],
                'groups': deployment['groups']
            }
        )
