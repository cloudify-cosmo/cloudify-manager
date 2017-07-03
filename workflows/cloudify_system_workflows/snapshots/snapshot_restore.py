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
import subprocess

from wagon import wagon

from cloudify.workflows import ctx
from cloudify.utils import ManagerVersion, get_local_rest_certificate
from cloudify.utils import get_tenant_name, internal as internal_utils
from cloudify.manager import get_rest_client
from cloudify.exceptions import NonRecoverableError
from cloudify.constants import FILE_SERVER_SNAPSHOTS_FOLDER

from cloudify_system_workflows.deployment_environment import \
    generate_create_dep_tasks_graph

from . import utils
from .npm import Npm
from .agents import Agents
from .influxdb import InfluxDB
from .postgres import Postgres
from .es_snapshot import ElasticSearch
from .credentials import restore as restore_credentials
from .constants import (
    ARCHIVE_CERT_DIR,
    METADATA_FILENAME,
    M_SCHEMA_REVISION,
    M_STAGE_SCHEMA_REVISION,
    M_VERSION,
    MANAGER_PYTHON
)


V_4_0_0 = ManagerVersion('4.0.0')
V_4_1_0 = ManagerVersion('4.1.0')


class SnapshotRestore(object):

    SCHEMA_REVISION_4_0 = '333998bc1627'

    def __init__(self,
                 config,
                 snapshot_id,
                 recreate_deployments_envs,
                 force,
                 timeout,
                 tenant_name,
                 premium_enabled,
                 user_is_bootstrap_admin,
                 restore_certificates,
                 no_reboot):
        self._npm = Npm()
        self._config = utils.DictToAttributes(config)
        self._snapshot_id = snapshot_id
        self._force = force
        self._timeout = timeout
        self._tenant_name = tenant_name
        self._restore_certificates = restore_certificates
        self._no_reboot = no_reboot
        self._premium_enabled = premium_enabled
        self._user_is_bootstrap_admin = user_is_bootstrap_admin

        self._tempdir = None
        self._snapshot_version = None
        self._client = get_rest_client()

    def restore(self):
        self._tempdir = tempfile.mkdtemp('-snapshot-data')
        snapshot_path = self._get_snapshot_path()
        ctx.logger.debug('Going to restore snapshot, '
                         'snapshot_path: {0}'.format(snapshot_path))
        try:
            metadata = self._extract_snapshot_archive(snapshot_path)
            self._snapshot_version = ManagerVersion(metadata[M_VERSION])
            schema_revision = metadata.get(
                M_SCHEMA_REVISION,
                self.SCHEMA_REVISION_4_0,
            )
            stage_revision = metadata.get(
                M_STAGE_SCHEMA_REVISION,
                None,
            )
            self._validate_snapshot()

            existing_plugins = self._get_existing_plugin_names()

            with Postgres(self._config) as postgres:
                self._restore_db(postgres, schema_revision, stage_revision)
                self._restore_files_to_manager()
                self._restore_plugins(existing_plugins)
                self._restore_influxdb()
                self._restore_credentials(postgres)
                self._restore_agents()
                self._restore_amqp_vhosts_and_users()
                self._restore_deployment_envs()
            if self._restore_certificates:
                self._restore_certificate()
        finally:
            ctx.logger.debug('Removing temp dir: {0}'.format(self._tempdir))
            shutil.rmtree(self._tempdir)

    def _restore_deployment_envs(self):
        deps = {}
        tenants = [get_tenant_name()] if self._snapshot_version < V_4_0_0 \
            else utils.get_tenants_list()
        for tenant_name in tenants:
            # Temporarily assign the context a different tenant name so that
            # we can retrieve that tenant's deployment contexts
            with internal_utils._change_tenant(ctx, tenant_name):
                # We have to zero this out each time or the cached version for
                # the previous tenant will be used
                ctx._dep_contexts = None

                # Get deployment contexts for this tenant
                deps[tenant_name] = ctx.deployments_contexts

        for tenant, deployments in deps.iteritems():
            ctx.logger.info(
                'Restoring deployment environments for {tenant}'.format(
                    tenant=tenant,
                )
            )
            tenant_client = get_rest_client(tenant=tenant)
            for deployment_id, dep_ctx in deployments.iteritems():
                ctx.logger.info('Restoring deployment {dep_id}'.format(
                    dep_id=deployment_id,
                ))
                with dep_ctx:
                    dep = tenant_client.deployments.get(deployment_id)
                    blueprint = tenant_client.blueprints.get(
                        dep_ctx.blueprint.id,
                    )
                    tasks_graph = self._get_tasks_graph(
                        dep_ctx,
                        blueprint,
                        dep,
                    )
                    tasks_graph.execute()
                    ctx.logger.info(
                        'Successfully created deployment environment '
                        'for deployment {deployment}'.format(
                            deployment=deployment_id,
                        )
                    )
            ctx.logger.info(
                'Finished restoring deployment environments for '
                '{tenant}'.format(
                    tenant=tenant,
                )
            )

    def _restore_amqp_vhosts_and_users(self):
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   'restore_amqp.py')
        subprocess.check_call([MANAGER_PYTHON, script_path])

    def _restore_certificate(self):
        archive_cert_dir = os.path.join(self._tempdir, ARCHIVE_CERT_DIR)
        old_cert_dir = os.path.dirname(get_local_rest_certificate())
        new_cert_dir = old_cert_dir + '_from_snapshot'
        if not utils.compare_cert_metadata(old_cert_dir, archive_cert_dir):
            return
        utils.copy_snapshot_path(archive_cert_dir, new_cert_dir)
        time_to_wait_for_workflow_to_finish = 3
        cmd = 'sleep {0}; rm -rf {1}; mv {2} {1}'.format(
            time_to_wait_for_workflow_to_finish, old_cert_dir, new_cert_dir)
        if not self._no_reboot:
            cmd += '; sudo shutdown -r now'
        subprocess.Popen(cmd, shell=True)

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
        ctx.logger.info('Restoring files from the archive to the manager')
        utils.copy_files_between_manager_and_snapshot(
            self._tempdir,
            self._config,
            to_archive=False,
            tenant_name=(
                ctx.tenant_name if self._snapshot_version < V_4_0_0 else None
            ),
        )
        utils.restore_stage_files(self._tempdir)
        utils.restore_composer_files(self._tempdir)
        ctx.logger.info('Successfully restored archive files')

    def _restore_db(self, postgres, schema_revision, stage_revision):
        """Restore database from snapshot.

        :param postgres: Database wrapper for snapshots
        :type: :class:`cloudify_system_workflows.snapshots.postgres.Postgres`
        :param schema_revision:
            Schema revision for the dump file in the snapshot
        :type schema_revision: str

        """
        ctx.logger.info('Restoring database')
        if self._snapshot_version >= V_4_0_0:
            with utils.db_schema(schema_revision, config=self._config):
                postgres.restore(self._tempdir)
            self._restore_stage(postgres, self._tempdir, stage_revision)
        else:
            if self._should_clean_old_db_for_3_x_snapshot():
                postgres.clean_db()

            ElasticSearch.restore_db_from_pre_4_version(
                self._tempdir,
                ctx.tenant_name,
            )
        ctx.logger.info('Successfully restored database')

    def _restore_stage(self, postgres, tempdir, migration_version):
        if not (self._snapshot_version > V_4_0_0 and self._premium_enabled):
            return
        ctx.logger.info('Restoring stage DB')
        self._npm.clear_db()
        self._npm.downgrade_stage_db(migration_version)
        postgres.restore_stage(tempdir)
        self._npm.upgrade_stage_db()
        ctx.logger.debug('Stage DB restored')

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
        existing_plugins = self._client.plugins.list(_all_tenants=True)
        return [self._get_plugin_archive_path_id_and_tenant(p)
                for p in existing_plugins]

    def _get_plugin_archive_path_id_and_tenant(self, plugin):
        return {
            'path': os.path.join(
                '/opt/manager/resources/plugins',
                plugin['id'],
                plugin.archive_name
            ),
            'id': plugin['id'],
            'tenant': plugin['tenant_name'],
        }

    def _get_plugins_to_install(self, existing_plugins):
        """Return a list of plugins that need to be installed (meaning, they
        weren't installed on the manager before the restore and they *can* be
        installed on the manager)

        :param existing_plugins: Names of already installed plugins
        """
        def should_install(plugin):
            # Can't just do 'not in' as plugin is a dict
            hashable_existing = (frozenset(p) for p in existing_plugins)
            return frozenset(plugin.items()) not in hashable_existing

        ctx.logger.debug('Looking for plugins to install')
        all_plugins = self._client.plugins.list(_all_tenants=True)
        installable_plugins = [
            self._get_plugin_archive_path_id_and_tenant(plugin)
            for plugin in all_plugins
            if self._plugin_installable_on_current_platform(plugin)
        ]
        ctx.logger.debug('Found {0} plugins in total'
                         .format(len(all_plugins)))
        plugins_to_install = {}
        for plugin in installable_plugins:
            if should_install(plugin):
                tenant = plugin['tenant']
                plugins_to_install.setdefault(tenant, []).append(plugin)
        ctx.logger.info('Found plugins to install for tenant: {p}'.format(
            p=plugins_to_install,
        ))
        return plugins_to_install

    def _restore_plugins(self, existing_plugins):
        """Install any plugins that weren't installed prior to the restore

        :param existing_plugins: Names of already installed plugins
        """
        ctx.logger.info('Restoring plugins')
        plugins_to_install = self._get_plugins_to_install(existing_plugins)
        for tenant, plugins in plugins_to_install.items():
            client = get_rest_client(tenant=tenant)
            plugins_tmp = tempfile.mkdtemp()
            try:
                for plugin in plugins:
                    wagon_name = os.path.basename(plugin['path'])
                    ctx.logger.info(
                        'Installing plugin {plugin} for {tenant}'.format(
                            plugin=wagon_name,
                            tenant=tenant,
                        )
                    )
                    temp_plugin = os.path.join(plugins_tmp, wagon_name)
                    shutil.copyfile(plugin['path'], temp_plugin)
                    client.plugins.delete(plugin['id'], force=True)
                    client.plugins.upload(temp_plugin)
                    os.remove(temp_plugin)
            finally:
                os.rmdir(plugins_tmp)
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
        Agents().restore(self._tempdir,
                         is_older_than_4_1_0=self._snapshot_version < V_4_1_0)
        ctx.logger.info('Successfully restored cloudify agent data')

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
                'Tenant name `{tenant}` passed when restoring snapshot of '
                'version {version}.'.format(
                    tenant=self._tenant_name,
                    version=self._snapshot_version,
                )
            )

        if not self._is_user_bootstrap_admin:
            raise NonRecoverableError(
                'The current user is not authorized to restore v4 snapshots. '
                'Only the bootstrap admin is allowed to perform this action'
            )

        self._assert_clean_db()

    def _validate_v_3_snapshot(self):
        # validate only for the snapshot's tenant
        self._assert_clean_db(all_tenants=False)

    def _assert_clean_db(self, all_tenants=True):
        if self._client.blueprints.list(_all_tenants=all_tenants).items:
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
