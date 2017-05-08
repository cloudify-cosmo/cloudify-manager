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
from contextlib import contextmanager

from wagon import wagon

from cloudify.workflows import ctx
from cloudify.utils import ManagerVersion, get_local_rest_certificate
from cloudify.manager import get_rest_client
from cloudify.exceptions import NonRecoverableError
from cloudify.constants import FILE_SERVER_SNAPSHOTS_FOLDER

from cloudify_system_workflows import plugins
from cloudify_system_workflows.deployment_environment import \
    generate_create_dep_tasks_graph

from cloudify_rest_client.exceptions import CloudifyClientError

from . import utils
from .agents import Agents
from .influxdb import InfluxDB
from .postgres import Postgres
from .es_snapshot import ElasticSearch
from .credentials import restore as restore_credentials
from .constants import METADATA_FILENAME, M_VERSION, ARCHIVE_CERT_DIR


V_4_0_0 = ManagerVersion('4.0.0')


class SnapshotRestore(object):
    def __init__(self,
                 config,
                 snapshot_id,
                 recreate_deployments_envs,
                 force,
                 timeout,
                 tenant_name,
                 premium_enabled,
                 user_is_bootstrap_admin):
        self._config = utils.DictToAttributes(config)
        self._snapshot_id = snapshot_id
        self._recreate_deployments_envs = recreate_deployments_envs
        self._force = force
        self._timeout = timeout
        self._tenant_name = tenant_name
        self._premium_enabled = premium_enabled
        self._user_is_bootstrap_admin = user_is_bootstrap_admin

        self._tempdir = None
        self._snapshot_version = None
        self._client = get_rest_client()
        self._tenant_client = self._get_tenant_client()

    def restore(self):
        self._tempdir = tempfile.mkdtemp('-snapshot-data')
        snapshot_path = self._get_snapshot_path()
        ctx.logger.debug('Going to restore snapshot, '
                         'snapshot_path: {0}'.format(snapshot_path))
        try:
            metadata = self._extract_snapshot_archive(snapshot_path)
            self._snapshot_version = ManagerVersion(metadata[M_VERSION])
            self._validate_snapshot()

            existing_plugins = self._get_existing_plugin_names()
            existing_dep_envs = self._get_existing_dep_envs()

            self._restore_certificate()
            with Postgres(self._config) as postgres:
                self._restore_db(postgres)
                self._restore_files_to_manager()
                self._restore_plugins(existing_plugins)
                self._restore_influxdb()
                self._restore_credentials(postgres)
                self._restore_agents()
                self._restore_deployment_envs(existing_dep_envs)
        finally:
            ctx.logger.debug('Removing temp dir: {0}'.format(self._tempdir))
            shutil.rmtree(self._tempdir)

    def _restore_certificate(self):
        local_cert_dir = os.path.dirname(get_local_rest_certificate())
        archive_cert_dir = os.path.join(self._tempdir, ARCHIVE_CERT_DIR)
        if utils.compare_cert_metadata(local_cert_dir, archive_cert_dir):
            utils.copy_snapshot_path(archive_cert_dir,
                                     local_cert_dir + '_from_snapshot')

    def _validate_snapshot(self):
        manager_version = utils.get_manager_version(self._client)
        validator = SnapshotRestoreValidator(
            self._snapshot_version,
            manager_version,
            self._premium_enabled,
            self._user_is_bootstrap_admin,
            self._client,
            self._tenant_name,
            self._force
        )
        validator.validate()

    def _restore_files_to_manager(self):
        new_tenant = self._tenant_name \
            if self._snapshot_version < V_4_0_0 else ''
        ctx.logger.info('Restoring files from the archive to the manager')
        utils.copy_files_between_manager_and_snapshot(
            self._tempdir,
            self._config,
            to_archive=False,
            new_tenant=new_tenant
        )
        ctx.logger.info('Successfully restored archive files')

    def _restore_db(self, postgres):
        ctx.logger.info('Restoring database')
        if self._snapshot_version > V_4_0_0:
            postgres.restore(self._tempdir)
            if self._premium_enabled:
                postgres.restore_stage(self._tempdir)
        elif self._snapshot_version == V_4_0_0:
            with utils.db_schema('333998bc1627'):
                postgres.restore(self._tempdir)
        else:
            if self._should_clean_old_db_for_3_x_snapshot():
                postgres.clean_db()

            # If no tenant name was passed, we can assume that we're working
            # with the community edition (due to the validations we've made)
            tenant_name = self._tenant_name or \
                self._config['default_tenant_name']
            ElasticSearch.restore_db_from_pre_4_version(
                self._tempdir,
                tenant_name
            )
        ctx.logger.info('Successfully restored database')

    def _should_clean_old_db_for_3_x_snapshot(self):
        """The one case in which the DB should be cleared is when restoring
        a 3.x snapshot, is when we have a community edition manager, with a
        dirty DB and the `force` flag was passed

        :return: True if all the above conditions are met
        """
        return not self._premium_enabled and \
            self._force and \
            self._client.blueprints.list(_all_tenants=True).items

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

    def _get_snapshot_path(self):
        """Calculate the snapshot path from the config + snapshot ID
        """
        file_server_root = self._config.file_server_root
        snapshots_dir = os.path.join(
            file_server_root,
            FILE_SERVER_SNAPSHOTS_FOLDER
        )
        return os.path.join(
            snapshots_dir,
            self._snapshot_id,
            '{0}.zip'.format(self._snapshot_id)
        )

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
        ctx.logger.info('Successfully restored plugins')

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

    def _restore_influxdb(self):
        ctx.logger.info('Restoring InfluxDB metrics')
        InfluxDB.restore(self._tempdir)
        ctx.logger.info('Successfully restored InfluxDB metrics')

    def _restore_credentials(self, postgres):
        ctx.logger.info('Restoring credentials')
        restore_credentials(self._tempdir, postgres)
        ctx.logger.info('Successfully restored credentials')

    def _restore_agents(self):
        ctx.logger.info('Restoring cloudify agent data')
        Agents().restore(self._tempdir, self._tenant_client)
        ctx.logger.info('Successfully restored cloudify agent data')

    def _get_tenant_client(self):
        with self._update_tenant_in_ctx():
            return get_rest_client()

    @contextmanager
    def _update_tenant_in_ctx(self):
        """Temporarily change the tenant in the current context to be the
        tenant passed in the restore command
        """
        curr_tenant = ctx.tenant_name
        tenant_name = self._tenant_name if self._tenant_name else curr_tenant
        try:
            ctx._context['tenant_name'] = tenant_name
            yield
        finally:
            ctx._context['tenant_name'] = curr_tenant

    def _restore_deployment_envs(self, existing_dep_envs):
        """Restore any deployment environments on the manager that didn't
        exist before restoring the snapshot

        :param existing_dep_envs: A list of deployment ID of environments that
        existed prior to the restore
        """
        if not self._recreate_deployments_envs:
            return
        ctx.logger.info('Restoring deployment environments')
        with self._update_tenant_in_ctx():
            deployments_contexts = ctx.deployments_contexts

        for deployment_id, dep_ctx in deployments_contexts.iteritems():
            if deployment_id in existing_dep_envs:
                continue
            with dep_ctx:
                dep = self._tenant_client.deployments.get(deployment_id)
                blueprint = self._tenant_client.blueprints.get(
                    dep_ctx.blueprint.id)
                tasks_graph = self._get_tasks_graph(dep_ctx, blueprint, dep)
                tasks_graph.execute()
                ctx.logger.debug('Successfully created deployment environment '
                                 'for deployment {0}'.format(deployment_id))
        ctx.logger.info('Successfully restored  deployment environments')

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


class SnapshotRestoreValidator(object):
    def __init__(self,
                 snapshot_version,
                 manager_version,
                 is_premium_enabled,
                 is_user_bootstrap_admin,
                 client,
                 tenant_name,
                 force):
        self._snapshot_version = snapshot_version
        self._manager_version = manager_version
        self._is_premium_enabled = is_premium_enabled
        self._is_user_bootstrap_admin = is_user_bootstrap_admin
        self._client = client
        self._force = force
        self._tenant_name = tenant_name

        ctx.logger.info('Validating snapshot\n'
                        'Manager version = {0}, snapshot version = {1}'
                        .format(manager_version, snapshot_version))

    def validate(self):
        if self._snapshot_version > self._manager_version:
            raise NonRecoverableError(
                'Cannot restore a newer manager\'s snapshot on this manager '
                '[{0} > {1}]'.format(str(self._snapshot_version),
                                     str(self._manager_version)))

        if self._snapshot_version >= V_4_0_0:
            self._validate_v_4_snapshot()
        else:
            self._validate_v_3_snapshot()

    def _validate_v_4_snapshot(self):
        if self._tenant_name:
            raise NonRecoverableError(
                'Tenant name `{0}` passed when restoring snapshot of version '
                '{1}. Tenant name should only be passed when restoring '
                'versions prior to {2}'.format(
                    self._tenant_name,
                    self._snapshot_version,
                    V_4_0_0
                )
            )

        if not self._is_user_bootstrap_admin:
            raise NonRecoverableError(
                'The current user is not authorized to restore v4 snapshots. '
                'Only the bootstrap admin is allowed to perform this action'
            )

        self._assert_clean_db()

    def _validate_v_3_snapshot(self):
        if self._tenant_name:
            if self._is_premium_enabled:
                self._assert_tenant_does_not_exist()
            else:
                raise NonRecoverableError(
                    'Passing a tenant name when restoring a snapshot is a '
                    'feature that exists only in the premium edition of '
                    'Cloudify. \nPlease contact sales for additional info.'
                )
        else:
            if self._is_premium_enabled:
                raise NonRecoverableError(
                    'Tenant name was not provided when restoring a snapshot '
                    'of version {0}. Tenant name must be provided when '
                    'restoring versions prior to {1}'.format(
                        self._snapshot_version,
                        V_4_0_0
                    ))
            else:
                self._assert_clean_db()

    def _assert_tenant_does_not_exist(self):
        try:
            self._client.tenants.get(self._tenant_name)
            raise NonRecoverableError(
                'Tenant `{0}` already exists on the manager. A *new* tenant '
                'name must be provided when restoring a snapshot of version '
                'prior to {1}'.format(self._tenant_name, V_4_0_0)
            )
        except CloudifyClientError:
            # We're expecting a client error here if the tenant does not exist
            pass

    def _assert_clean_db(self):
        if self._client.blueprints.list(_all_tenants=True).items:
            if self._force:
                ctx.logger.warning(
                    "Forcing snapshot restoration on a non-empty manager. "
                    "Existing data will be deleted")
            else:
                raise NonRecoverableError(
                    "Snapshot restoration on a non-empty manager is not "
                    "permitted. Pass the --force flag to force the restore "
                    "and delete existing data from the manager"
                )
