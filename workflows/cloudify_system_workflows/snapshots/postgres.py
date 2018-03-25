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
import psycopg2
from uuid import uuid4
from contextlib import closing
from cryptography.fernet import Fernet
from psycopg2.extras import execute_values

from cloudify.workflows import ctx
from cloudify.exceptions import NonRecoverableError

from .constants import ADMIN_DUMP_FILE
from .utils import run as run_shell

POSTGRESQL_DEFAULT_PORT = 5432


class Postgres(object):
    """Use as a context manager

    with Postgres(config) as postgres:
        postgres.restore()
    """
    _TRUNCATE_QUERY = "TRUNCATE {0} CASCADE;"
    _POSTGRES_DUMP_FILENAME = 'pg_data'
    _STAGE_DB_NAME = 'stage'
    _COMPOSER_DB_NAME = 'composer'
    _TABLES_TO_KEEP = ['alembic_version', 'provider_context', 'roles']
    _TABLES_TO_EXCLUDE_ON_DUMP = _TABLES_TO_KEEP + ['snapshots']
    _TABLES_TO_RESTORE = ['users', 'tenants']
    _STAGE_TABLES_TO_EXCLUDE = ['"SequelizeMeta"']
    _COMPOSER_TABLES_TO_EXCLUDE = ['"SequelizeMeta"']

    def __init__(self, config):
        ctx.logger.debug('Init Postgres config: {0}'.format(config))
        self._bin_dir = config.postgresql_bin_path
        self._db_name = config.postgresql_db_name
        self._host = config.postgresql_host
        self._port = str(POSTGRESQL_DEFAULT_PORT)
        self._username = config.postgresql_username
        self._password = config.postgresql_password
        self._connection = None
        if ':' in self._host:
            self._host, self._port = self._host.split(':')
            ctx.logger.debug('Updating Postgres config: host: {0}, port: {1}'
                             .format(self._host, self._port))

    def restore(self, tempdir):
        ctx.logger.info('Restoring DB from postgres dump')
        dump_file = os.path.join(tempdir, self._POSTGRES_DUMP_FILENAME)

        # Add to the beginning of the dump queries that recreate the schema
        clear_tables_queries = self._get_clear_tables_queries()
        dump_file = self._prepend_dump(dump_file, clear_tables_queries)

        # Add the current execution
        self._append_dump(dump_file, self._get_execution_restore_query())

        # Don't change admin user during the restore or the workflow will
        # fail to correctly execute (the admin user update query reverts it
        # to the one from before the restore)
        self._append_dump(dump_file, self._get_admin_user_update_query())

        self._restore_dump(dump_file, self._db_name)

        self._make_api_token_keys()

        ctx.logger.debug('Postgres restored')

    def dump(self, tempdir, include_logs, include_events):
        ctx.logger.info('Dumping Postgres, include logs {0} include events {1}'
                        .format(include_logs, include_events))
        destination_path = os.path.join(tempdir, self._POSTGRES_DUMP_FILENAME)
        admin_dump_path = os.path.join(tempdir, ADMIN_DUMP_FILE)
        try:
            if not include_logs:
                self._TABLES_TO_EXCLUDE_ON_DUMP = \
                    self._TABLES_TO_EXCLUDE_ON_DUMP + ['logs']
            if not include_events:
                self._TABLES_TO_EXCLUDE_ON_DUMP = \
                    self._TABLES_TO_EXCLUDE_ON_DUMP + ['events']
            self._dump_to_file(
                destination_path,
                self._db_name,
                exclude_tables=self._TABLES_TO_EXCLUDE_ON_DUMP
            )
            self._dump_admin_user_to_file(
                admin_dump_path,
                self._db_name,
            )
        except Exception as ex:
            raise NonRecoverableError('Error during dumping Postgres data, '
                                      'exception: {0}'.format(ex))
        self._append_delete_current_execution(destination_path)

    def dump_stage(self, tempdir):
        self._dump_db(
            tempdir=tempdir,
            database_name=self._STAGE_DB_NAME,
            exclude_tables=self._STAGE_TABLES_TO_EXCLUDE,
        )

    def dump_composer(self, tempdir):
        self._dump_db(
            tempdir=tempdir,
            database_name=self._COMPOSER_DB_NAME,
            exclude_tables=self._COMPOSER_TABLES_TO_EXCLUDE,
        )

    def _dump_db(self, tempdir, database_name, exclude_tables=()):
        if not self._db_exists(database_name):
            return
        destination_path = os.path.join(tempdir, database_name + '_data')
        try:
            self._dump_to_file(
                destination_path=destination_path,
                db_name=database_name,
                exclude_tables=exclude_tables,
            )
        except Exception as ex:
            raise NonRecoverableError(
                'Error during dumping {db_name} data. Exception: '
                '{exception}'.format(
                    db_name=database_name,
                    exception=ex,
                )
            )

    def _restore_db(self, tempdir, database_name):
        if not self._db_exists(database_name):
            return
        ctx.logger.info('Restoring {db} DB'.format(db=database_name))
        dump_file = os.path.join(tempdir, database_name + '_data')
        self._restore_dump(dump_file, database_name)
        ctx.logger.debug('{db} DB restored'.format(db=database_name))

    def restore_stage(self, tempdir):
        self._restore_db(tempdir, self._STAGE_DB_NAME)

    def restore_composer(self, tempdir):
        self._restore_db(tempdir, self._COMPOSER_DB_NAME)

    def _db_exists(self, db_name):
        """Return True if the stage DB exists"""

        exists_query = "SELECT 1 FROM pg_database " \
                       "WHERE datname='{0}'".format(db_name)
        response = self.run_query(exists_query)
        # Will either be an empty list, or a list with 1 in it
        return bool(response['all'])

    def _append_delete_current_execution(self, dump_file):
        """Append to the dump file a query that deletes the current execution
        """
        delete_current_execution_query = "DELETE FROM executions " \
                                         "WHERE id = '{0}';" \
                                         .format(ctx.execution_id)
        self._append_dump(dump_file, delete_current_execution_query)

    def _get_admin_user_update_query(self):
        """Return a query that updates the admin user in the DB
        """
        username, password = self._get_admin_credentials()
        return "UPDATE users " \
               "SET username='{0}', password='{1}' " \
               "WHERE id=0;" \
               .format(username, password)

    def _get_execution_restore_query(self):
        """Return a query that creates an execution to the DB with the ID (and
        other data) from the snapshot restore execution
        """
        record_creation_date = self._get_restore_execution_date()
        return "INSERT INTO executions (id, created_at, " \
               "is_system_workflow, " \
               "status, workflow_id, _tenant_id, _creator_id) " \
               "VALUES ('{0}', '{1}', 't', " \
               "'started', 'restore_snapshot', 0, 0);"\
            .format(ctx.execution_id, record_creation_date)

    def clean_db(self):
        """Run a series of queries that recreate the schema and restore the
        admin user, the provider context and the current execution
        """
        queries = self._get_clear_tables_queries(preserve_defaults=True)
        queries.append(self._get_admin_user_update_query())
        queries.append(self._get_execution_restore_query())
        # Make the admin user actually has the admin role
        queries.append("INSERT INTO users_roles (user_id, role_id)"
                       "VALUES (0, 1);")
        queries.append("INSERT INTO users_tenants (user_id, tenant_id)"
                       "VALUES (0, 0);")
        for query in queries:
            self.run_query(query)

    def drop_db(self):
        ctx.logger.info('Dropping db')
        drop_db_bin = os.path.join(self._bin_dir, 'dropdb')
        command = [drop_db_bin,
                   '--host', self._host,
                   '--port', self._port,
                   '-U', self._username,
                   self._db_name]
        run_shell(command)

    def create_db(self):
        ctx.logger.debug('Creating db')
        create_db_bin = os.path.join(self._bin_dir, 'createdb')
        command = [create_db_bin,
                   '--host', self._host,
                   '--port', self._port,
                   '-U', self._username,
                   '-T', 'template0',
                   self._db_name]
        run_shell(command)

    def _dump_to_file(self, destination_path, db_name, exclude_tables=None):
        ctx.logger.debug('Creating db dump file: {0}, excluding: {0}'.
                         format(destination_path, exclude_tables))
        flags = []
        if exclude_tables:
            flags = ["--exclude-table={0}".format(t)
                     for t in exclude_tables]
            flags.extend(["--exclude-table-data={0}".format(t)
                          for t in exclude_tables])
        pg_dump_bin = os.path.join(self._bin_dir, 'pg_dump')
        command = [pg_dump_bin,
                   '-a',
                   '--host', self._host,
                   '--port', self._port,
                   '-U', self._username,
                   db_name,
                   '-f', destination_path]
        command.extend(flags)
        run_shell(command)

    def _dump_admin_user_to_file(self, destination_path, db_name):
        ctx.logger.debug('Dumping admin account')
        command = self.get_psql_command(db_name)

        # Hardcoded uid as we only allow running restore on a clean manager
        # at the moment, so admin must be the first user (ID=0)
        query = (
            'select row_to_json(row) from ('
            'select * from users where id=0'
            ') row;'
        )
        command.extend([
            '-c', query,
            '-t',  # Dump just the data, without extra headers, etc
            '-o', destination_path,
        ])
        run_shell(command)

    def get_psql_command(self, db_name=None):
        psql_bin = os.path.join(self._bin_dir, 'psql')
        db_name = db_name or self._db_name
        return [
            psql_bin,
            '--host', self._host,
            '--port', self._port,
            '-U', self._username,
            db_name,
        ]

    def _restore_dump(self, dump_file, db_name):
        """Execute `psql` to restore an SQL dump into the DB
        """
        ctx.logger.debug('Restoring db dump file: {0}'.format(dump_file))
        command = self.get_psql_command(db_name)
        command.extend([
            '--single-transaction',
            '-f', dump_file
        ])
        run_shell(command)

    @staticmethod
    def _append_dump(dump_file, query):
        ctx.logger.debug('Adding to end of dump: {0}'.format(query))
        with open(dump_file, 'a') as f:
            f.write('\n{0}\n'.format(query))

    @staticmethod
    def _prepend_dump(dump_file, queries):
        queries_str = '\n'.join(queries)
        ctx.logger.debug('Adding to beginning of dump: {0}'
                         .format(queries_str))
        pre_dump_file = '{0}.pre'.format(dump_file)
        new_dump_file = '{0}.new'.format(dump_file)
        with open(pre_dump_file, 'a') as f:
            f.write('\n{0}\n'.format(queries_str))
        # using cat command and output redirection
        # to avoid reading file content into memory (for big dumps)
        cat_content = 'cat {0} {1}'.format(pre_dump_file, dump_file)
        run_shell(command=cat_content, redirect_output_path=new_dump_file)
        return new_dump_file

    def run_query(self, query, vars=None, bulk_query=False):
        str_query = query.decode(encoding='UTF-8', errors='replace')
        str_query = str_query.replace(u"\uFFFD", "?")
        ctx.logger.debug('Running query: {0}'.format(str_query))
        with closing(self._connection.cursor()) as cur:
            try:
                if bulk_query:
                    execute_values(cur, query, vars)
                else:
                    cur.execute(query, vars)
                status_message = cur.statusmessage
                fetchall = cur.fetchall()
                result = {'status': status_message, 'all': fetchall}
                ctx.logger.debug('Running query result status: {0}'
                                 .format(status_message))
            except Exception, e:
                fetchall = None
                status_message = str(e)
                result = {'status': status_message, 'all': fetchall}
                if status_message != 'no results to fetch':
                    ctx.logger.error('Running query result status: {0}'
                                     .format(status_message))
            return result

    def _make_api_token_keys(self):
        # If this is from a snapshot that precedes token keys we need to
        # generate them
        result = self.run_query(
            "SELECT id, api_token_key FROM users"
        )

        for row in result['all']:
            uid = row[0]
            api_token_key = row[1]
            if not api_token_key:
                api_token_key = uuid4().hex
                self.run_query(
                    "UPDATE users "
                    "SET api_token_key=%s "
                    "WHERE id=%s",
                    (api_token_key, uid),
                )

    def get_deployment_creator_ids_and_tokens(self):
        result = self.run_query(
            "SELECT tenants.name, deployments.id,"
            "users.id, users.api_token_key "
            "FROM deployments, users, tenants "
            "WHERE deployments._creator_id=users.id "
            "AND tenants.id=deployments._tenant_id"
        )

        details = {}
        # Make structure the same as the deployments:
        # { 'tenant1': {'deploymentid': {info}, ...}, ...}
        for row in result['all']:
            tenant = row[0]
            deployment = row[1]
            if tenant not in details:
                details[tenant] = {}
            details[tenant][deployment] = {
                'uid': row[2],
                'token': row[3],
            }
        return details

    def encrypt_secrets_values(self, encryption_key):
        secrets = self.run_query("SELECT secrets.id, secrets.value "
                                 "FROM secrets")
        # There are no secrets in the snapshot
        if len(secrets['all']) < 1:
            return

        encrypted_secrets = []
        fernet = Fernet(encryption_key)
        for secret in secrets['all']:
            encrypted_value = fernet.encrypt(bytes(secret[1]))
            encrypted_secrets.append((secret[0], encrypted_value))

        update_query = """UPDATE secrets
                          SET value = encrypted_secrets.value
                          FROM (VALUES %s) AS encrypted_secrets (id, value)
                          WHERE secrets.id = encrypted_secrets.id"""

        self.run_query(update_query, vars=encrypted_secrets, bulk_query=True)

    def _connect(self):
        try:
            conn = psycopg2.connect(
                database=self._db_name,
                user=self._username,
                password=self._password,
                host=self._host,
                port=self._port
            )
            conn.autocommit = True
            return conn
        except psycopg2.DatabaseError as e:
            raise Exception('Error during connection to postgres: {0}'
                            .format(str(e)))

    def __enter__(self):
        self._connection = self._connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._connection:
            self._connection.close()

    def _get_clear_tables_queries(self, preserve_defaults=False):
        all_tables = self._get_all_tables()
        all_tables = [table for table in all_tables if
                      table not in self._TABLES_TO_KEEP]

        queries = [self._TRUNCATE_QUERY.format(table) for table in all_tables]
        if preserve_defaults:
            self._add_preserve_defaults_queries(queries)
        return queries

    def _add_preserve_defaults_queries(self, queries):
        """Replace regular truncate queries for users/tenants with ones that
        preserve the default user (id=0)/tenant (id=0)
        Used when restoring old snapshots that will not have those entities
        :param queries: List of truncate queries
        """
        queries.remove(self._TRUNCATE_QUERY.format('users'))
        queries.append('DELETE FROM users CASCADE WHERE id != 0;')
        queries.remove(self._TRUNCATE_QUERY.format('tenants'))
        queries.append('DELETE FROM tenants CASCADE WHERE id != 0;')

    def _get_all_tables(self):
        result = self.run_query("SELECT tablename "
                                "FROM pg_tables "
                                "WHERE schemaname = 'public';")

        # result['all'] is a list of tuples, each with a single value
        return [res[0] for res in result['all']]

    def _get_admin_credentials(self):
        response = self.run_query("SELECT username, password "
                                  "FROM users WHERE id=0")
        if not response:
            raise NonRecoverableError('Illegal state - '
                                      'missing admin user in db')
        return response['all'][0]

    def _get_restore_execution_date(self):
        response = self.run_query("SELECT created_at "
                                  "FROM executions "
                                  "WHERE id='{0}'".format(ctx.execution_id))
        if not response:
            raise NonRecoverableError('Illegal state - missing execution date '
                                      'for current execution')
        return response['all'][0][0]
