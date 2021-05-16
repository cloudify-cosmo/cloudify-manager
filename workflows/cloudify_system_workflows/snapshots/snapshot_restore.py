import re
import os
import json
import time
import uuid
import base64
import shutil
import zipfile
import tempfile
import threading
import subprocess
from contextlib import contextmanager

from cloudify.workflows import ctx
from cloudify.manager import get_rest_client
from cloudify.exceptions import NonRecoverableError
from cloudify.constants import (
    NEW_TOKEN_FILE_NAME,
    FILE_SERVER_SNAPSHOTS_FOLDER,
)
from cloudify.snapshots import SNAPSHOT_RESTORE_FLAG_FILE
from cloudify.utils import ManagerVersion, get_local_rest_certificate

from cloudify_rest_client.executions import Execution

from . import networks, utils
from cloudify_system_workflows.deployment_environment import \
    _create_deployment_workdir
from cloudify_system_workflows.snapshots import npm
from .agents import Agents
from .postgres import Postgres
from .credentials import restore as restore_credentials
from .constants import (
    ADMIN_DUMP_FILE,
    ADMIN_TOKEN_SCRIPT,
    ALLOW_DB_CLIENT_CERTS_SCRIPT,
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
    M_COMPOSER_SCHEMA_REVISION,
    M_VERSION,
    MANAGER_PYTHON,
    V_4_0_0,
    V_4_2_0,
    V_4_3_0,
    V_4_4_0,
    V_4_6_0,
    V_5_0_5,
    V_5_3_0,
    V_6_0_0,
    SECURITY_FILE_LOCATION,
    SECURITY_FILENAME,
    REST_AUTHORIZATION_CONFIG_PATH,
    STAGE_USER,
    STAGE_APP,
    COMPOSER_USER,
    COMPOSER_APP
)
from .utils import is_later_than_now, parse_datetime_string


class SnapshotRestore(object):
    SCHEMA_REVISION_4_0 = '333998bc1627'

    def __init__(self,
                 config,
                 snapshot_id,
                 force,
                 timeout,
                 premium_enabled,
                 user_is_bootstrap_admin,
                 restore_certificates,
                 no_reboot):
        self._config = utils.DictToAttributes(config)
        self._snapshot_id = snapshot_id
        self._force = force
        self._timeout = timeout
        self._restore_certificates = restore_certificates
        self._no_reboot = no_reboot
        self._premium_enabled = premium_enabled
        self._user_is_bootstrap_admin = user_is_bootstrap_admin
        self._post_restore_commands = []

        self._tempdir = None
        self._snapshot_version = None
        self._client = get_rest_client()
        self._manager_version = utils.get_manager_version(self._client)
        self._encryption_key = None
        self._service_management = None
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
            composer_revision = metadata.get(M_COMPOSER_SCHEMA_REVISION) or ''
            if composer_revision == '20170601133017-4_1-init.js':
                # Old composer metadata always incorrectly put the first
                # migration not the last one. As we don't support anything
                # earlier than the last migration before 5.3, this will always
                # be the right answer
                composer_revision = '20171229105614-4_3-blueprint-repo.js'
            if composer_revision and self._premium_enabled:
                composer_revision = re.sub(r".*\n", '', composer_revision)
            self._validate_snapshot()

            with Postgres(self._config) as postgres:
                utils.sudo(ALLOW_DB_CLIENT_CERTS_SCRIPT)
                self._restore_files_to_manager()
                utils.sudo(DENY_DB_CLIENT_CERTS_SCRIPT)
                self._service_management = \
                    json.loads(postgres.get_service_management())
                with self._pause_services():
                    self._restore_db(
                        postgres,
                        schema_revision,
                        stage_revision,
                        composer_revision
                    )
                self._restore_hash_salt()
                self._encrypt_secrets(postgres)
                self._encrypt_rabbitmq_passwords(postgres)
                self._possibly_update_encryption_key()
                self._generate_new_rest_token()
                self._restart_rest_service()
                self._restart_stage_service()
                self._restore_credentials(postgres)
                self._restore_amqp_vhosts_and_users()
                self._restore_agents()
                self._restore_deployment_envs()
                self._restore_scheduled_executions()
                self._restore_inter_deployment_dependencies()
                self._update_roles_and_permissions()
                self._update_deployment_statuses()
                self._update_node_instance_indices()
                self._set_default_user_profile_flags()

            if self._restore_certificates:
                self._restore_certificate()

        finally:
            self._trigger_post_restore_commands()
            ctx.logger.debug('Removing temp dir: {0}'.format(self._tempdir))
            shutil.rmtree(self._tempdir)

    @contextmanager
    def _pause_services(self):
        """Stop db-using services for the duration of this context"""
        # While the snapshot is being restored, the database is downgraded
        # and upgraded back, and these services must not attempt to use it
        to_pause = ['cloudify-amqp-postgres', 'cloudify-execution-scheduler']
        for service in to_pause:
            utils.run_service(self._service_management, 'stop', service)
        try:
            yield
        finally:
            for service in to_pause:
                utils.run_service(self._service_management, 'start', service)

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
        utils.run_service(
            self._service_management,
            'restart',
            'cloudify-restservice'
        )
        self._wait_for_rest_to_restart()

    def _restart_stage_service(self):
        utils.run_service(
            self._service_management,
            'restart',
            'cloudify-stage'
        )

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

    def _update_roles_and_permissions(self):
        ctx.logger.info('Updating roles and permissions')
        if os.path.exists(REST_AUTHORIZATION_CONFIG_PATH):
            utils.run(['/opt/manager/scripts/load_permissions.py'])

    def _create_system_filters(self):
        ctx.logger.info('Creating system filters')
        if self._snapshot_version < V_6_0_0:
            utils.run(['/opt/manager/scripts/create_system_filters.py'])

    def _update_deployment_statuses(self):
        ctx.logger.info('Updating deployment statuses.')
        if self._snapshot_version < V_5_3_0:
            dir_path = os.path.dirname(os.path.realpath(__file__))
            scrip_path = os.path.join(
                dir_path,
                'populate_deployment_statuses.py'
            )
            command = [MANAGER_PYTHON, scrip_path, self._tempdir]
            utils.run(command)

    def _update_node_instance_indices(self):
        ctx.logger.info('Updating node indices.')
        if self._snapshot_version < V_5_0_5:
            with Postgres(self._config) as postgres:
                postgres.run_query(
                    'update node_instances ni set index=u.rank '
                    'from (select node_instances._storage_id, rank() '
                    'over (partition by node_instances._node_fk '
                    'order by node_instances._storage_id) '
                    'from node_instances) u '
                    'where ni._storage_id = u._storage_id;'
                )

    def _set_default_user_profile_flags(self):
        if self._snapshot_version < V_5_3_0:
            ctx.logger.info(
                'Disabling `getting started` for all existing users.')
            users = self._client.users.list()
            for user in users:
                self._client.users.set_show_getting_started(user.username,
                                                            False)

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

    def _restore_deployment_envs(self):
        deps = utils.get_dep_contexts(self._snapshot_version)
        for tenant, deployments in deps:
            ctx.logger.info('Creating deployment dirs for %s', tenant)
            for deployment_id in deployments:
                _create_deployment_workdir(
                    deployment_id=deployment_id,
                    tenant=tenant,
                    logger=ctx.logger,
                )
        ctx.logger.info('Successfully created deployment dirs.')

    def _restore_inter_deployment_dependencies(self):
        # managers older than 4.6.0 didn't have the support get_capability.
        # manager newer than 5.0.5 have the inter deployment dependencies as
        # part of the database dump
        if (self._snapshot_version < V_4_6_0 or
                self._snapshot_version > V_5_0_5):
            return

        ctx.logger.info('Restoring inter deployment dependencies')
        update_service_composition = (self._snapshot_version == V_5_0_5)

        script_path = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            'restore_idd_script.py'
        )
        cmd = ['/opt/manager/env/bin/python',
               script_path,
               ctx.tenant_name,
               str(update_service_composition)]
        restore_idd_script = subprocess.run(cmd)

        if restore_idd_script.returncode:
            restore_idd_log_path = 'mgmtworker/logs/restore_idd.log'
            raise NonRecoverableError('Failed to restore snapshot, could not '
                                      'create the inter deployment '
                                      'dependencies. See log {0} for more '
                                      'details'.format(restore_idd_log_path))
        ctx.logger.info('Successfully restored inter deployment dependencies.')

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
        self._post_restore_commands.append(
            'sudo {0}'.format(ADMIN_TOKEN_SCRIPT))

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
        utils.restore_stage_files(
            self._tempdir,
            self._service_management,
            stage_restore_override,
        )
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

    def _restore_db(
            self,
            postgres,
            schema_revision,
            stage_revision,
            composer_revision
    ):
        """Restore database from snapshot.

        :param postgres: Database wrapper for snapshots
        :type: :class:`cloudify_system_workflows.snapshots.postgres.Postgres`
        :param schema_revision:
            Schema revision for the dump file in the snapshot
        :type schema_revision: str
        :param stage_revision:
            Stage Schema revision for the dump file in the snapshot
        :type stage_revision: str
        :param composer_revision:
            Composer Schema revision for the dump file in the snapshot
        :type composer_revision: str

        """
        ctx.logger.info('Restoring database')
        postgres.dump_license_to_file(self._tempdir)
        admin_user_update_command = 'echo No admin user to update.'
        postgres.init_current_execution_data()

        config_dump_path = postgres.dump_config_tables(self._tempdir)
        # We dump and restore _MANAGER_TABLES separately for pre-5 Cloudify
        # versions, otherwise they will get eaten by the schema downgrade
        if self._snapshot_version <= V_4_6_0:
            mgr_tables_dump_path = postgres.dump_manager_tables(self._tempdir)
        permissions_dump_path = postgres.dump_permissions_table(self._tempdir)
        with utils.db_schema(schema_revision, config=self._config):
            admin_user_update_command = postgres.restore(
                self._tempdir, premium_enabled=self._premium_enabled,
                snapshot_version=self._snapshot_version)
        if self._snapshot_version <= V_4_6_0:
            postgres.restore_manager_tables(mgr_tables_dump_path)
        postgres.restore_config_tables(config_dump_path)
        if not self._permissions_exist(postgres):
            postgres.restore_permissions_table(permissions_dump_path)
        postgres.restore_current_execution()
        try:
            self._restore_stage(postgres, self._tempdir, stage_revision)
        except Exception as e:
            if self._snapshot_version < V_4_3_0:
                ctx.logger.warning('Could not restore stage ({0})'.format(e))
            else:
                raise
        if composer_revision:
            self._restore_composer(postgres, self._tempdir, composer_revision)
        if not self._license_exists(postgres):
            postgres.restore_license_from_dump(self._tempdir)
        ctx.logger.info('Successfully restored database')
        # This is returned so that we can decide whether to restore the admin
        # user depending on whether we have the hash salt
        return admin_user_update_command

    def _license_exists(self, postgres):
        result = postgres.run_query('SELECT * FROM licenses;')
        return '0' not in result['status']

    def _permissions_exist(self, postgres):
        result = postgres.run_query('SELECT count(1) FROM permissions')
        if not result['all']:
            return False
        count = result['all'][0][0]  # the only row's only column is the count
        return count > 0

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
        npm.clear_db(STAGE_APP, STAGE_USER)
        npm.downgrade_app_db(STAGE_APP, STAGE_USER, migration_version)
        try:
            postgres.restore_stage(tempdir)
        finally:
            npm.upgrade_app_db(STAGE_APP, STAGE_USER)
        ctx.logger.debug('Stage DB restored')

    def _restore_composer(self, postgres, tempdir, migration_version):
        if not (self._snapshot_version >= V_4_2_0 and self._premium_enabled):
            return
        ctx.logger.info('Restoring composer DB')
        npm.clear_db(COMPOSER_APP, COMPOSER_USER)
        npm.downgrade_app_db(COMPOSER_APP, COMPOSER_USER, migration_version)
        try:
            postgres.restore_composer(tempdir)
        finally:
            npm.upgrade_app_db(COMPOSER_APP, COMPOSER_USER)
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

    def _restore_credentials(self, postgres):
        ctx.logger.info('Restoring credentials')
        restore_credentials(self._tempdir, postgres, self._snapshot_version)
        ctx.logger.info('Successfully restored credentials')

    def _restore_agents(self):
        ctx.logger.info('Restoring cloudify agent data')
        Agents().restore(self._tempdir, self._snapshot_version)
        ctx.logger.info('Successfully restored cloudify agent data')

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

    def _get_encoded_user_id(self, user_id):
        return utils.run([
            MANAGER_PYTHON,
            self._get_script_path('getencodeduser.py'),
            '--user_id',
            str(user_id),
        ]).aggr_stdout.strip()

    def _restore_scheduled_executions(self):
        """Restore executions scheduled for a time after snapshot creation."""
        for execution in self._client.executions.list(
                _get_all_results=True, status=Execution.SCHEDULED):
            if is_later_than_now(execution.scheduled_for):
                ctx.logger.debug("Re-scheduling execution %s (at %s)",
                                 execution.workflow_id,
                                 execution.scheduled_for)

                schedule_name = '{}_restored_{}'.format(execution.workflow_id,
                                                        uuid.uuid4().hex)
                self._client.execution_schedules.create(
                    schedule_name,
                    execution.deployment_id,
                    execution.workflow_id,
                    execution_arguments={
                        'allow_custom_parameters': True,
                        'dry_run': execution.is_dry_run,
                    },
                    parameters=execution.parameters,
                    since=parse_datetime_string(execution.scheduled_for),
                    count=1)

            self._client.executions.update(execution.id, Execution.FAILED)
            ctx.logger.warning(
                "Marking original execution %s scheduled for %s as FAILED.",
                execution.id, execution.scheduled_for)

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
