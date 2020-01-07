########
# Copyright (c) 2015-2019 Cloudify Platform Ltd. All rights reserved
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

import re
import os
import json
import time
import Queue
import base64
import shutil
import zipfile
import platform
import tempfile
import threading
import subprocess
from contextlib import closing, contextmanager

import wagon
from cloudify.workflows import ctx
from cloudify.manager import get_rest_client
from cloudify.state import current_workflow_ctx
from cloudify.exceptions import NonRecoverableError
from cloudify.constants import (
    NEW_TOKEN_FILE_NAME,
    FILE_SERVER_SNAPSHOTS_FOLDER,
)
from cloudify.snapshots import SNAPSHOT_RESTORE_FLAG_FILE
from cloudify.utils import ManagerVersion, get_local_rest_certificate

from cloudify_rest_client.executions import Execution
from cloudify_system_workflows.deployment_environment import \
    generate_create_dep_tasks_graph

from . import networks, utils
from cloudify_system_workflows.snapshots import npm
from .agents import Agents
from .postgres import Postgres
from .credentials import restore as restore_credentials
from .constants import (
    ADMIN_DUMP_FILE,
    ADMIN_TOKEN_SCRIPT,
    ARCHIVE_CERT_DIR,
    CERT_DIR,
    DENY_DB_CLIENT_CERTS_SCRIPT,
    HASH_SALT_FILENAME,
    INTERNAL_CA_CERT_FILENAME,
    INTERNAL_CA_KEY_FILENAME,
    INTERNAL_CERT_FILENAME,
    INTERNAL_KEY_FILENAME,
    INTERNAL_P12_FILENAME,
    METADATA_FILENAME,
    M_SCHEMA_REVISION,
    M_STAGE_SCHEMA_REVISION,
    M_VERSION,
    MANAGER_PYTHON,
    V_4_0_0,
    V_4_2_0,
    V_4_3_0,
    V_4_4_0,
    SECURITY_FILE_LOCATION,
    SECURITY_FILENAME
)


class SnapshotRestore(object):
    SCHEMA_REVISION_4_0 = '333998bc1627'

    def __init__(self,
                 config,
                 snapshot_id,
                 recreate_deployments_envs,
                 force,
                 timeout,
                 premium_enabled,
                 user_is_bootstrap_admin,
                 restore_certificates,
                 no_reboot,
                 ignore_plugin_failure):
        self._config = utils.DictToAttributes(config)
        self._snapshot_id = snapshot_id
        self._force = force
        self._timeout = timeout
        self._restore_certificates = restore_certificates
        self._no_reboot = no_reboot
        self._premium_enabled = premium_enabled
        self._user_is_bootstrap_admin = user_is_bootstrap_admin
        self._ignore_plugin_failure = \
            ignore_plugin_failure
        self._post_restore_commands = []

        self._tempdir = None
        self._snapshot_version = None
        self._client = get_rest_client()
        self._manager_version = utils.get_manager_version(self._client)
        self._encryption_key = None
        self._semaphore = threading.Semaphore(
            self._config.snapshot_restore_threads)

    def restore(self):
        self._mark_manager_restoring()
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
            stage_revision = metadata.get(M_STAGE_SCHEMA_REVISION) or ''
            if stage_revision and self._premium_enabled:
                stage_revision = re.sub(r".*\n", '', stage_revision)
            self._validate_snapshot()

            existing_plugins = self._get_existing_plugin_names()
            with Postgres(self._config) as postgres:
                self._restore_files_to_manager()
                utils.sudo(DENY_DB_CLIENT_CERTS_SCRIPT)
                with self._pause_services():
                    self._restore_db(postgres, schema_revision, stage_revision)
                self._restore_hash_salt()
                self._encrypt_secrets(postgres)
                self._encrypt_rabbitmq_passwords(postgres)
                self._possibly_update_encryption_key()
                self._generate_new_rest_token()
                self._restart_rest_service()
                self._restore_plugins(existing_plugins)
                self._restore_credentials(postgres)
                self._restore_agents()
                self._restore_amqp_vhosts_and_users()
                self._restore_deployment_envs(postgres)

                if self._premium_enabled:
                    self._reconfigure_status_reporter(postgres)

            if self._restore_certificates:
                self._restore_certificate()

        finally:
            self._trigger_post_restore_commands()
            ctx.logger.debug('Removing temp dir: {0}'.format(self._tempdir))
            shutil.rmtree(self._tempdir)

    @contextmanager
    def _pause_services(self):
        """Stop cloudify-amqp-postgres for the duration of this context"""
        # While the snapshot is being restored, the database is downgraded
        # and upgraded back, and the snapshot execution itself might not
        # be in the database during that time.
        # If we try to insert logs during that time, they won't be stored,
        # because they can't have a FK to a non-existent execution.
        # Pause amqp-postgres so that all the logs are only stored after
        # the database has finished restoring
        # Also for manager's status reporter that uses manager's rest
        # endpoint and in turn uses the DB for auth, that could cause
        # failure for migration of the users table.
        process_to_pause = ['cloudify-amqp-postgres']
        if self._premium_enabled:
            process_to_pause.append('cloudify-status-reporter')
        utils.run('sudo systemctl stop {0}'.format(
            ' '.join(process_to_pause)))
        try:
            yield
        finally:
            utils.run('sudo systemctl start {0}'.format(
             ' '.join(process_to_pause)))

    def _generate_new_rest_token(self):
        """
        `snapshot restore` is triggered with a REST call that is authenticated
        using security keys that are located in opt/manager/rest-security.conf.
        During restore the rest-security.conf is changed, therefore any
        restart of the REST service will result in authentication failure
        (security config is loaded when the REST service starts).
        Gunicorn restarts REST workers every 1000 calls.
        Our solution:
        1. At the earliest stage possible create a new valid REST token
           using the new rest-security.conf file
        2. Restart REST service
        3. Continue with restore snapshot
        (CY-767)
        """
        self._generate_new_token()
        new_token = self._get_token_from_file()
        # Replace old token with new one in the workflow context, and create
        # new REST client
        ctx._context['rest_token'] = new_token
        self._client = get_rest_client()

    def _restart_rest_service(self):
        restart_command = 'cfy_manager restart restservice'
        utils.run(restart_command)
        self._wait_for_rest_to_restart()

    def _wait_for_rest_to_restart(self, timeout=60):
        deadline = time.time() + timeout
        while True:
            time.sleep(0.5)
            if time.time() > deadline:
                raise NonRecoverableError(
                    'Failed to restart cloudify-restservice.')
            try:
                self._client.manager.get_status()
                break
            except Exception:
                pass

    def _generate_new_token(self):
        dir_path = os.path.dirname(os.path.realpath(__file__))
        script_path = os.path.join(dir_path, 'generate_new_rest_token.py')
        command = [MANAGER_PYTHON, script_path, self._tempdir]
        utils.run(command)

    def _get_token_from_file(self):
        """
        The new token in saved at the snapshot`s temp dir (which is passed as
        an argument to the 'generate_new_rest_token.py' script).
        """
        new_token_path = os.path.join(self._tempdir, NEW_TOKEN_FILE_NAME)
        with open(new_token_path, 'r') as f:
            new_token = f.read()
        return new_token

    def _should_ignore_plugin_failure(self,
                                      message):
        return 'cloudify_agent.operations.install_plugins' in \
               message and self._ignore_plugin_failure

    def _get_and_execute_task_graph(self, token_info, deployment_id,
                                    dep_ctx, tenant, tenant_client,
                                    workflow_ctx, ctx_params,
                                    deps_with_failed_plugins,
                                    failed_deployments):
        """
        While in the correct workflow context, this method
        creates a `create_deployment_env` task graph and executes it.
        Since this method is being executed by threads, it appends errors
        to thread-safe queues, in order to handle them later outside of
        this scope.
        """
        # The workflow context is thread local so we need to push it for
        # each thread.
        try:
            with current_workflow_ctx.push(workflow_ctx, ctx_params):
                try:
                    api_token = self._get_api_token(
                        token_info[tenant][deployment_id]
                    )
                    dep = tenant_client.deployments.get(deployment_id)
                    blueprint = tenant_client.blueprints.get(
                        dep_ctx.blueprint.id,
                    )
                    tasks_graph = self._get_tasks_graph(
                        dep_ctx,
                        blueprint,
                        dep,
                        api_token,
                    )
                    with dep_ctx:
                        tasks_graph.execute()
                except RuntimeError as re:
                    if self._should_ignore_plugin_failure(re.message):
                        ctx.logger.warning('Failed to install plugins for '
                                           'deployment `{0}` under tenant '
                                           '`{1}`.  Proceeding since '
                                           '`ignore_plugin_failure` flag was'
                                           ' used.'
                                           .format(deployment_id, tenant))
                        ctx.logger.debug(re.message)
                        deps_with_failed_plugins.put((deployment_id, tenant))
                    else:
                        failed_deployments.put((deployment_id, tenant))
                        ctx.logger.info(re)
        finally:
            self._semaphore.release()

    def _possibly_update_encryption_key(self):
        with open(SECURITY_FILE_LOCATION) as security_conf_file:
            rest_security_conf = json.load(security_conf_file)
        enc_key = base64.urlsafe_b64decode(str(
            rest_security_conf['encryption_key'],
        ))
        if len(enc_key) == 32:
            ctx.logger.info(
                'Updating encryption key for AES256'
            )
            subprocess.check_call([
                '/opt/cloudify/encryption/update-encryption-key', '--commit'
            ])

    def _restore_deployment_envs(self, postgres):
        deps = utils.get_dep_contexts(self._snapshot_version)
        token_info = postgres.get_deployment_creator_ids_and_tokens()
        deps_with_failed_plugins = Queue.Queue()
        failed_deployments = Queue.Queue()
        threads = list()

        for tenant, deployments in deps:
            ctx.logger.info(
                'Restoring deployment environments for {tenant}'.format(
                    tenant=tenant,
                )
            )
            tenant_client = get_rest_client(tenant=tenant)

            for deployment_id, dep_ctx in deployments.iteritems():
                # Task graph is created and executed by threads to
                # shorten restore time significantly
                wf_ctx = current_workflow_ctx.get_ctx()
                wf_parameters = current_workflow_ctx.get_parameters()
                self._semaphore.acquire()
                t = threading.Thread(target=self._get_and_execute_task_graph,
                                     args=(token_info, deployment_id, dep_ctx,
                                           tenant, tenant_client, wf_ctx,
                                           wf_parameters,
                                           deps_with_failed_plugins,
                                           failed_deployments)
                                     )
                t.setDaemon(True)
                threads.append(t)
                t.start()

        for t in threads:
            t.join()

        if not failed_deployments.empty():
            deployments = list(failed_deployments.queue)
            raise NonRecoverableError('Failed to restore snapshot, the '
                                      'following deployment environments were'
                                      ' not restored: {0}. See exception'
                                      ' tracebacks logged above for more'
                                      ' details.'.format(deployments))

        self._log_final_information(deps_with_failed_plugins)

    @staticmethod
    def _log_final_information(deps_with_failed_plugins):
        if deps_with_failed_plugins.empty():
            ctx.logger.info('Successfully restored deployment environments.')

        # Alert users that some deployments were restored but their
        # plugins were not installed.
        else:
            deployments = list(deps_with_failed_plugins.queue)
            ctx.logger.warning('Finished restoring deployment evnironments.'
                               ' Please note that the following deployment '
                               'plugins were not installed and need to be'
                               ' installed manually on each deployment`s '
                               'virtual env: {0}'.
                               format(deployments))

    def _restore_amqp_vhosts_and_users(self):
        subprocess.check_call(
            [MANAGER_PYTHON, self._get_script_path('restore_amqp.py')]
        )

    def _restore_certificate(self):
        archive_cert_dir = os.path.join(self._tempdir, ARCHIVE_CERT_DIR)
        existing_cert_dir = os.path.dirname(get_local_rest_certificate())
        restored_cert_dir = '{0}_from_snapshot_{1}'.format(existing_cert_dir,
                                                           self._snapshot_id)

        # Put the certificates where we need them
        utils.copy_snapshot_path(archive_cert_dir, restored_cert_dir)

        certs = [
            INTERNAL_CA_CERT_FILENAME,
            INTERNAL_CA_KEY_FILENAME,
            INTERNAL_CERT_FILENAME,
            INTERNAL_KEY_FILENAME,
            INTERNAL_P12_FILENAME,
        ]
        # Restore each cert from the snapshot over the current manager one
        for cert in certs:
            self._post_restore_commands.append(
                'mv -f {source_dir}/{cert} {dest_dir}/{cert}'.format(
                    dest_dir=existing_cert_dir,
                    source_dir=restored_cert_dir,
                    cert=cert,
                )
            )

        if not os.path.exists(
                os.path.join(archive_cert_dir, INTERNAL_CA_CERT_FILENAME)):
            for source, target in \
                    [(INTERNAL_CERT_FILENAME, INTERNAL_CA_CERT_FILENAME),
                     (INTERNAL_KEY_FILENAME, INTERNAL_CA_KEY_FILENAME)]:
                source = os.path.join(CERT_DIR, source)
                target = os.path.join(CERT_DIR, target)
                self._post_restore_commands.append(
                    'cp {source} {target}'.format(
                        source=source,
                        target=target,
                    )
                )

        if not self._no_reboot:
            self._post_restore_commands.append('sudo shutdown -r now')

    def _load_admin_dump(self):
        # This should only have been called if the hash salt was found, so
        # there should be no case where this gets called but the file does not
        # exist.
        admin_dump_file_path = os.path.join(self._tempdir, ADMIN_DUMP_FILE)
        with open(admin_dump_file_path) as admin_dump_handle:
            admin_account = json.load(admin_dump_handle)

        return admin_account

    def _restore_admin_user(self):
        admin_account = self._load_admin_dump()
        with Postgres(self._config) as postgres:
            psql_command = ' '.join(postgres.get_psql_command())
        psql_command += ' -c '
        update_prefix = '"UPDATE users SET '
        # Hardcoded uid as we only allow running restore on a clean manager
        # at the moment, so admin must be the first user (ID=0)
        update_suffix = ' WHERE users.id=0"'
        # Discard the id, we don't need it
        admin_account.pop('id')
        updates = []
        for column, value in admin_account.items():
            if value:
                updates.append("{column}='{value}'".format(
                    column=column,
                    value=value,
                ))
        updates = ','.join(updates)
        updates = updates.replace('$', '\\$')
        command = psql_command + update_prefix + updates + update_suffix
        # We have to do this after the restore process or it'll break the
        # workflow execution updating and thus cause the workflow to fail
        self._post_restore_commands.append(command)
        # recreate the admin REST token file
        self._post_restore_commands.append(ADMIN_TOKEN_SCRIPT)

    def _get_admin_user_token(self):
        return self._load_admin_dump()['api_token_key']

    def _trigger_post_restore_commands(self):
        # The last thing the workflow does is delete the tempdir.
        command = 'while [[ -d {tempdir} ]]; do sleep 0.5; done; '.format(
            tempdir=self._tempdir,
        )
        # Give a short delay afterwards for the workflow to be marked as
        # completed, in case of any delays that might be upset by certs being
        # messed around with while running.
        command += 'sleep 3; '

        self._post_restore_commands.append(
            'rm -f {0}'.format(SNAPSHOT_RESTORE_FLAG_FILE)
        )

        command += '; '.join(self._post_restore_commands)

        ctx.logger.info(
            'After restore, the following commands will run: {cmds}'.format(
                cmds=command,
            )
        )

        subprocess.Popen(command, shell=True)

    def _validate_snapshot(self):
        validator = SnapshotRestoreValidator(
            self._snapshot_version,
            self._premium_enabled,
            self._user_is_bootstrap_admin,
            self._client,
            self._force,
            self._tempdir
        )
        validator.validate()

    def _restore_files_to_manager(self):
        ctx.logger.info('Restoring files from the archive to the manager')
        utils.copy_files_between_manager_and_snapshot(
            self._tempdir,
            self._config,
            to_archive=False,
            tenant_name=None,
        )
        # Only restore stage files to their correct location
        # if this snapshot version is the same as the manager version
        # or from 4.3 onwards we support stage upgrade
        if self._snapshot_version == self._manager_version or \
                self._snapshot_version >= V_4_3_0:
            stage_restore_override = True
        else:
            stage_restore_override = False
        self._restore_security_file()
        utils.restore_stage_files(self._tempdir, stage_restore_override)
        utils.restore_composer_files(self._tempdir)
        ctx.logger.info('Successfully restored archive files')

    def _restore_security_file(self):
        """Update the rest security config file according to the snapshot
        """
        with open(SECURITY_FILE_LOCATION) as security_conf_file:
            rest_security_conf = json.load(security_conf_file)

        # Starting from 4.4.0 we save the rest-security.conf in the snapshot
        if self._snapshot_version < V_4_4_0:
            self._encryption_key = str(rest_security_conf['encryption_key'])
            return

        snapshot_security_path = os.path.join(self._tempdir, SECURITY_FILENAME)
        with open(snapshot_security_path) as snapshot_security_file:
            snapshot_security_conf = json.load(snapshot_security_file)

        rest_security_conf.update(snapshot_security_conf)
        with open(SECURITY_FILE_LOCATION, 'w') as security_conf_file:
            json.dump(rest_security_conf, security_conf_file)
        self._encryption_key = str(rest_security_conf['encryption_key'])

    def _restore_db(self, postgres, schema_revision, stage_revision):
        """Restore database from snapshot.

        :param postgres: Database wrapper for snapshots
        :type: :class:`cloudify_system_workflows.snapshots.postgres.Postgres`
        :param schema_revision:
            Schema revision for the dump file in the snapshot
        :type schema_revision: str

        """
        ctx.logger.info('Restoring database')
        postgres.dump_license_to_file(self._tempdir)
        admin_user_update_command = 'echo No admin user to update.'
        postgres.init_current_execution_data()

        config_dump_path = postgres.dump_config_tables(self._tempdir)
        status_reporter_roles_path, status_reporter_users_path = \
            postgres.dump_status_reporters(self._tempdir)
        with utils.db_schema(schema_revision, config=self._config):
            admin_user_update_command = postgres.restore(
                self._tempdir, premium_enabled=self._premium_enabled)
        postgres.restore_config_tables(config_dump_path)
        postgres.restore_current_execution()
        postgres.restore_status_reporters(status_reporter_roles_path,
                                          status_reporter_users_path)
        try:
            self._restore_stage(postgres, self._tempdir, stage_revision)
        except Exception as e:
            if self._snapshot_version < V_4_3_0:
                ctx.logger.warning('Could not restore stage ({0})'.format(e))
            else:
                raise
        self._restore_composer(postgres, self._tempdir)
        if not self._license_exists(postgres):
            postgres.restore_license_from_dump(self._tempdir)
        ctx.logger.info('Successfully restored database')
        # This is returned so that we can decide whether to restore the admin
        # user depending on whether we have the hash salt
        return admin_user_update_command

    def _license_exists(self, postgres):
        result = postgres.run_query('SELECT * FROM licenses;')
        return False if '0' in result['status'] else True

    def _encrypt_secrets(self, postgres):
        # The secrets are encrypted
        if self._snapshot_version >= V_4_4_0:
            return

        ctx.logger.info('Encrypting the secrets values')
        postgres.encrypt_values(self._encryption_key, 'secrets', 'value')
        ctx.logger.info('Successfully encrypted the secrets values')

    def _encrypt_rabbitmq_passwords(self, postgres):
        # The passwords are encrypted
        if self._snapshot_version >= V_4_4_0:
            return

        ctx.logger.info('Encrypting the passwords of RabbitMQ vhosts')
        postgres.encrypt_values(self._encryption_key,
                                'tenants',
                                'rabbitmq_password',
                                primary_key='id')
        ctx.logger.info('Successfully encrypted the passwords of RabbitMQ')

    def _restore_stage(self, postgres, tempdir, migration_version):
        if not self._premium_enabled:
            return
        ctx.logger.info('Restoring stage DB')
        npm.clear_db()
        npm.downgrade_stage_db(migration_version)
        try:
            postgres.restore_stage(tempdir)
        finally:
            npm.upgrade_stage_db()
        ctx.logger.debug('Stage DB restored')

    def _restore_composer(self, postgres, tempdir):
        if not (self._snapshot_version >= V_4_2_0 and self._premium_enabled):
            return
        ctx.logger.info('Restoring composer DB')
        postgres.restore_composer(tempdir)
        ctx.logger.debug('Composer DB restored')

    def _should_clean_old_db_for_3_x_snapshot(self):
        """The one case in which the DB should be cleared is when restoring
        a 3.x snapshot, is when we have a community edition manager, with a
        dirty DB and the `force` flag was passed

        :return: True if all the above conditions are met
        """
        return not self._premium_enabled and \
            self._force and \
            self._client.blueprints.list(_all_tenants=True,
                                         _include=['id'],
                                         _get_all_results=True).items

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
        existing_plugins = self._client.plugins.list(_all_tenants=True,
                                                     _get_all_results=True)
        return [self._get_plugin_info(p) for p in existing_plugins]

    def _get_plugin_info(self, plugin):
        return {
            'path': os.path.join(
                '/opt/manager/resources/plugins',
                plugin['id'],
                plugin.archive_name
            ),
            'id': plugin['id'],
            'tenant': plugin['tenant_name'],
            'visibility': plugin['visibility'],
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
        all_plugins = self._client.plugins.list(_all_tenants=True,
                                                _get_all_results=True)
        installable_plugins = [
            self._get_plugin_info(plugin) for plugin in all_plugins
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

    @staticmethod
    def _restore_plugin(client, tenant, plugin, plugins_tmp):
        plugin_dir = os.path.dirname(plugin['path'])
        wagon_name = os.path.basename(plugin['path'])
        ctx.logger.info(
            'Installing plugin {plugin} for {tenant}'.format(
                plugin=wagon_name,
                tenant=tenant,
            )
        )

        temp_plugin = os.path.join(plugins_tmp, wagon_name)
        # in case there are both wagon and yaml files
        if len(os.listdir(plugin_dir)) > 1:
            temp_plugin += '.zip'
            # creating a zip containing the wagon and plugin.yaml
            with closing(zipfile.ZipFile(temp_plugin, 'w')) as zip_file:
                for root, _, files in os.walk(plugin_dir):
                    for filename in files:
                        file_path = os.path.join(root, filename)
                        zip_file.write(file_path, os.path.relpath(file_path,
                                                                  plugin_dir))
        else:
            # support case of no plugin.yaml - copy only wagon
            shutil.copyfile(plugin['path'], temp_plugin)

        client.plugins.delete(plugin['id'], force=True)
        try:
            client.plugins.upload(temp_plugin,
                                  visibility=plugin['visibility'])
        finally:
            # In any case, failure or success, delete tmp* folder
            os.remove(temp_plugin)

    def _wait_for_plugin_executions(self, client):
        while True:
            executions = client.executions.list(
                include_system_workflows=True,
                _all_tenants=True,
                _get_all_results=True
            )
            waiting = []
            for execution in executions:
                if execution.workflow_id == 'install_plugin':
                    if execution.status not in Execution.END_STATES:
                        waiting.append(execution)
            if not waiting:
                break
            else:
                ctx.logger.info(
                    'Waiting for plugin install executions to finish: {0} '
                    '(state: {1})'
                    .format(execution.id, execution.status))
                time.sleep(3)

    @staticmethod
    def __remove_failed_plugins_footprints(client, failed_plugins):
        for failed_plugin in failed_plugins:
            # Removing failed plugins from the database and file server
            try:
                ctx.logger.info('Removing failed plugin footprints')
                client.plugins.delete(failed_plugin['id'], force=True)
            except Exception as ex:
                ctx.logger.warning('Failed to delete plugin footprints {0} '
                                   'with error: {1}. Proceeding...'
                                   .format(failed_plugin, ex.message))

    @staticmethod
    def __log_message_for_plugin_restore(failed_plugins):
        if not failed_plugins:
            ctx.logger.info('Successfully restored plugins')
        else:
            plugin_installation_log_message = \
                'Plugins: {0} have not been installed ' \
                'successfully'.format(failed_plugins)
            ctx.logger.warning(plugin_installation_log_message)

    def _restore_plugins(self, existing_plugins):
        """Install any plugins that weren't installed prior to the restore

        :param existing_plugins: Names of already installed plugins
        """
        ctx.logger.info('Restoring plugins')
        plugins_to_install = self._get_plugins_to_install(existing_plugins)
        failed_plugins = []
        for tenant, plugins in plugins_to_install.items():
            client = get_rest_client(tenant=tenant)
            plugins_tmp = tempfile.mkdtemp()
            try:
                for plugin in plugins:
                    try:
                        self._restore_plugin(client,
                                             tenant,
                                             plugin,
                                             plugins_tmp)
                    except Exception as ex:
                        if self._ignore_plugin_failure:
                            ctx.logger.warning(
                                'Failed to restore plugin: {0}, '
                                'ignore-plugin-failure flag '
                                'used. Proceeding...'.format(plugin))
                            ctx.logger.debug('Restore plugin failure error: '
                                             '{0}'.format(ex))
                            failed_plugins.append(plugin)
                        else:
                            raise ex
                self._wait_for_plugin_executions(client)
                SnapshotRestore.__remove_failed_plugins_footprints(
                    client, failed_plugins)
            finally:
                os.rmdir(plugins_tmp)
        SnapshotRestore.__log_message_for_plugin_restore(failed_plugins)

    @staticmethod
    def _plugin_installable_on_current_platform(plugin):
        dist, _, release = platform.linux_distribution(
            full_distribution_name=False)
        dist, release = dist.lower(), release.lower()
        return (plugin['supported_platform'] == 'any' or all([
            plugin['supported_platform'] == wagon.get_platform(),
            plugin['distribution'] == dist,
            plugin['distribution_release'] == release
        ]))

    def _restore_credentials(self, postgres):
        ctx.logger.info('Restoring credentials')
        restore_credentials(self._tempdir, postgres, self._snapshot_version)
        ctx.logger.info('Successfully restored credentials')

    def _restore_agents(self):
        ctx.logger.info('Restoring cloudify agent data')
        Agents().restore(self._tempdir, self._snapshot_version)
        ctx.logger.info('Successfully restored cloudify agent data')

    def _get_tasks_graph(self, dep_ctx, blueprint, deployment, token):
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
                'api_token': token,
                'policy_types': deployment['policy_types'],
                'policy_triggers': deployment['policy_triggers'],
                'groups': deployment['groups']
            }
        )

    def _load_hash_salt(self):
        if self._snapshot_version >= V_4_4_0:
            with open(SECURITY_FILE_LOCATION) as security_conf_handle:
                rest_security_conf = json.load(security_conf_handle)
            return rest_security_conf['hash_salt']

        hash_salt = None
        try:
            with open(os.path.join(self._tempdir,
                                   HASH_SALT_FILENAME), 'r') as f:
                hash_salt = json.load(f)
        except IOError:
            ctx.logger.warn('Hash salt not found in snapshot. '
                            'Restored users are not expected to work without '
                            'password resets.')
        return hash_salt

    def _restore_hash_salt(self):
        """Restore the hash salt so that restored users can log in.
        """
        # Starting from snapshot version 4.4.0 we restore the file
        # rest-security.conf, so we don't restore the hash_salt separately
        if self._snapshot_version < V_4_4_0:
            hash_salt = self._load_hash_salt()
            if hash_salt is None:
                return

            with open(SECURITY_FILE_LOCATION) as security_conf_handle:
                rest_security_conf = json.load(security_conf_handle)

            rest_security_conf['hash_salt'] = hash_salt

            with open(SECURITY_FILE_LOCATION, 'w') as security_conf_handle:
                json.dump(rest_security_conf, security_conf_handle)

        self._restore_admin_user()

    def _get_script_path(self, script_name):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            script_name)

    def _get_api_token(self, token_info):
        # The token info's UID here is referring to the creator of the
        # deployment that an API token is needed for.
        # If this is the admin user and the snapshot contains a hash salt then
        # we will be restoring the admin user from the old manager, including
        # its API token, so we should use that instead of the one currently in
        # the database.
        if token_info['uid'] == 0 and self._load_hash_salt():
            token_info['token'] = self._get_admin_user_token()

        prefix = self._get_encoded_user_id(token_info['uid'])
        return prefix + token_info['token']

    def _reconfigure_status_reporter(self, postgres):
        if not self._premium_enabled:
            return
        ctx.logger.debug("Reconfiguring the Manager's status reporter...")
        reporter = postgres.get_manager_reporter_info()
        encoded_id = self._get_encoded_user_id(reporter['id'])
        token = encoded_id + reporter['api_token_key']
        utils.run("sudo cfy_manager status-reporter configure --token '{0}'"
                  "".format(token))

    def _get_encoded_user_id(self, user_id):
        return utils.run([
            MANAGER_PYTHON,
            self._get_script_path('getencodeduser.py'),
            '--user_id',
            str(user_id),
        ]).aggr_stdout.strip()

    @staticmethod
    def _mark_manager_restoring():
        with open(SNAPSHOT_RESTORE_FLAG_FILE, 'a'):
            os.utime(SNAPSHOT_RESTORE_FLAG_FILE, None)
        ctx.logger.debug('Marked manager is snapshot restoring with file:'
                         ' {0}'.format(SNAPSHOT_RESTORE_FLAG_FILE))


class SnapshotRestoreValidator(object):
    def __init__(self,
                 snapshot_version,
                 is_premium_enabled,
                 is_user_bootstrap_admin,
                 client,
                 force,
                 tempdir):
        self._snapshot_version = snapshot_version
        self._client = client
        self._manager_version = utils.get_manager_version(self._client)
        self._is_premium_enabled = is_premium_enabled
        self._is_user_bootstrap_admin = is_user_bootstrap_admin
        self._force = force
        self._tempdir = tempdir

        ctx.logger.info('Validating snapshot\n'
                        'Manager version = {0}, snapshot version = {1}'
                        .format(self._manager_version, snapshot_version))

    def validate(self):
        if self._snapshot_version > self._manager_version:
            raise NonRecoverableError(
                'Cannot restore a newer manager\'s snapshot on this manager '
                '[{0} > {1}]'.format(str(self._snapshot_version),
                                     str(self._manager_version)))

        if self._snapshot_version >= V_4_0_0:
            self._validate_v_4_snapshot()
        else:
            raise NonRecoverableError(
                'Restoring snapshot from version '
                '{0} is not supported'.format(self._snapshot_version))

    def _validate_v_4_snapshot(self):
        if not self._is_user_bootstrap_admin:
            raise NonRecoverableError(
                'The current user is not authorized to restore v4 snapshots. '
                'Only the bootstrap admin is allowed to perform this action'
            )

        self._assert_clean_db()
        if self._snapshot_version >= V_4_2_0:
            self._assert_manager_networks()

    def _assert_clean_db(self, all_tenants=True):
        blueprints_list = self._client.blueprints.list(
            _all_tenants=all_tenants,
            _include=['id'],
            _get_all_results=True
        )
        if blueprints_list.items:
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

    def _assert_manager_networks(self):
        used_networks = networks.get_networks_from_snapshot(self._tempdir)
        manager_networks, broker_networks = \
            networks.get_current_networks(self._client)
        missing_manager_networks = used_networks - manager_networks
        missing_broker_networks = used_networks - broker_networks
        missing_networks = missing_manager_networks | missing_broker_networks

        if not missing_networks:
            return

        msg = ('Snapshot networks: `{0}` are used by agents, but are '
               'missing from '
               .format(', '.join(missing_networks)))
        parts = []
        if missing_manager_networks:
            parts.append('the manager (manager networks: `{0}`)'
                         .format(', '.join(manager_networks)))
        if missing_broker_networks:
            parts.append('the broker (broker networks: `{0}`)'
                         .format(', '.join(broker_networks)))
        msg += ' and '.join(parts)
        raise NonRecoverableError(msg)
