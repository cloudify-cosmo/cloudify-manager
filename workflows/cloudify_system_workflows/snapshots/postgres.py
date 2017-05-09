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
from contextlib import closing

from cloudify.workflows import ctx
from cloudify.exceptions import NonRecoverableError

from .utils import run as run_shell

POSTGRESQL_DEFAULT_PORT = 5432


class Postgres(object):
    """Use as a context manager

    with Postgres(config) as postgres:
        postgres.restore()
    """
    _TRUNCATE_QUERY = "TRUNCATE {0} CASCADE;"
    _POSTGRES_DUMP_FILENAME = 'pg_data'
    _STAGE_DUMP_FILENAME = 'stage_data'
    _STAGE_DB_NAME = 'stage'
    _TABLES_TO_KEEP = ['alembic_version', 'provider_context', 'roles']
    _TABLES_TO_EXCLUDE_ON_DUMP = _TABLES_TO_KEEP + ['snapshots']
    _TABLES_TO_RESTORE = ['users', 'tenants']
    _STAGE_TABLES_TO_EXCLUDE = ['"SequelizeMeta"']

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

        # Add admin user, provider context and the current execution
        restore_admin_query = self._get_admin_user_update_query()
        self._append_dump(dump_file, restore_admin_query)
        self._append_dump(dump_file, self._get_execution_restore_query())

        self._restore_dump(dump_file, self._db_name)
        ctx.logger.debug('Postgres restored')

    def dump(self, tempdir):
        destination_path = os.path.join(tempdir, self._POSTGRES_DUMP_FILENAME)
        try:
            self._dump_to_file(
                destination_path,
                self._db_name,
                exclude_tables=self._TABLES_TO_EXCLUDE_ON_DUMP
            )
        except Exception as ex:
            raise NonRecoverableError('Error during dumping Postgres data, '
                                      'exception: {0}'.format(ex))
        self._append_delete_current_execution(destination_path)

    def dump_stage(self, tempdir):
        if not self._stage_db_exists():
            return
        destination_path = os.path.join(tempdir, self._STAGE_DUMP_FILENAME)
        try:
            self._dump_to_file(
                destination_path=destination_path,
                db_name=self._STAGE_DB_NAME,
                exclude_tables=self._STAGE_TABLES_TO_EXCLUDE
            )
        except Exception as ex:
            raise NonRecoverableError('Error during dumping Stage data, '
                                      'exception: {0}'.format(ex))

    def restore_stage(self, tempdir):
        if not self._stage_db_exists():
            return
        ctx.logger.info('Clearing Stage DB')
        self._clear_stage_db()
        ctx.logger.info('Restoring Stage DB')
        stage_dump_file = os.path.join(tempdir, self._STAGE_DUMP_FILENAME)
        self._restore_dump(stage_dump_file, self._STAGE_DB_NAME)
        ctx.logger.debug('Stage DB restored')

    @staticmethod
    def _clear_stage_db():
        """ Run the script that clears the Stage DB """

        command = ['/opt/nodejs/bin/npm', 'run', 'db-migrate-clear']
        run_shell(command, cwd='/opt/cloudify-stage/backend')

    def _stage_db_exists(self):
        """Return True if the stage DB exists"""

        exists_query = "SELECT 1 FROM pg_database " \
                       "WHERE datname='{0}'".format(self._STAGE_DB_NAME)
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

    def _restore_dump(self, dump_file, db_name):
        """Execute `psql` to restore an SQL dump into the DB
        """
        ctx.logger.debug('Restoring db dump file: {0}'.format(dump_file))
        psql_bin = os.path.join(self._bin_dir, 'psql')
        command = [psql_bin,
                   '--single-transaction',
                   '--host', self._host,
                   '--port', self._port,
                   '-U', self._username,
                   db_name,
                   '-f', dump_file]
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

    def run_query(self, query, vars=None):
        str_query = query.decode(encoding='UTF-8', errors='replace')
        str_query = str_query.replace(u"\uFFFD", "?")
        ctx.logger.debug('Running query: {0}'.format(str_query))
        with closing(self._connection.cursor()) as cur:
            try:
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
