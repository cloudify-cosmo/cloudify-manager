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

import utils
from cloudify.workflows import ctx


class Postgres(object):
    def __init__(self, config):
        ctx.logger.debug('Init Postgres config: {0}'.format(config))
        self._psql_bin = os.path.join(config.postgresql_bin_path,
                                      'psql')
        self._pg_dump_bin = os.path.join(config.postgresql_bin_path,
                                         'pg_dump')
        self._pg_restore = os.path.join(config.postgresql_bin_path,
                                        'pg_restore')
        self._drop_db_bin = os.path.join(config.postgresql_bin_path,
                                         'dropdb')
        self._create_db_bin = os.path.join(config.postgresql_bin_path,
                                           'createdb')
        self._db_name = config.postgresql_db_name
        self._host = config.postgresql_host
        self._username = config.postgresql_username
        self._password = config.postgresql_password

    def drop_db(self):
        ctx.logger.info('Dropping db')
        command = [self._drop_db_bin,
                   '--host', self._host,
                   '-U', self._username,
                   self._db_name]
        utils.run(command)

    def create_db(self):
        ctx.logger.debug('Creating db')
        command = [self._create_db_bin,
                   '--host', self._host,
                   '-U', self._username,
                   '-T', 'template0',
                   self._db_name]
        utils.run(command)

    def dump(self, destination_path, exclude_tables=None):
        ctx.logger.debug('Creating db dump file: {0}, excluding: {0}'.
                         format(destination_path, exclude_tables))
        exclude_tables = exclude_tables if exclude_tables else []
        flags = ["--exclude-table={0}".format(t)
                 for t in exclude_tables]
        flags.extend(["--exclude-table-data={0}".format(t)
                      for t in exclude_tables])
        command = [self._pg_dump_bin,
                   '-a',
                   '--host', self._host,
                   '-U', self._username,
                   self._db_name,
                   '-f', destination_path]
        command.extend(flags)
        utils.run(command)

    def restore(self, dump_file):
        ctx.logger.debug('Restoring db dump file: {0}'.format(dump_file))
        command = [self._psql_bin,
                   '--single-transaction',
                   '--host', self._host,
                   '-U', self._username,
                   self._db_name,
                   '-f', dump_file]
        utils.run(command)

    def append_dump(self, dump_file, query):
        ctx.logger.debug('Adding to end of dump: {0}'.format(query))
        with open(dump_file, 'a') as f:
            f.write('\n{0}\n'.format(query))

    def prepend_dump(self, dump_file, queries):
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
        utils.run(command=cat_content, redirect_output_path=new_dump_file)
        return new_dump_file

    def run_query(self, query):
        str_query = query.decode(encoding='UTF-8', errors='replace')\
            .replace(u"\uFFFD", "?")
        ctx.logger.debug('Running query: {0}'.format(str_query))
        with closing(self._connect()) as conn:
            conn.autocommit = True
            with closing(conn.cursor()) as cur:
                try:
                    cur.execute(query)
                    status_message = cur.statusmessage
                    fetchall = cur.fetchall()
                    result = {'status': status_message, 'all': fetchall}
                    ctx.logger.debug('Running query result status: {0}'
                                     .format(status_message))
                except Exception, e:
                    fetchall = None
                    status_message = str(e)
                    result = {'status': status_message, 'all': fetchall}
                    ctx.logger.error('Running query result status: {0}'
                                     .format(status_message))
                return result

    def _connect(self):
        try:
            return psycopg2.connect(
                database=self._db_name,
                user=self._username,
                password=self._password,
                host=self._host
            )
        except psycopg2.DatabaseError as e:
            raise Exception('Error during connection to postgres: {0}'
                            .format(str(e)))
