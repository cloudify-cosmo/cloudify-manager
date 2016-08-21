########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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
import logging
from psycopg2 import connect
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from cloudify.utils import setup_logger

from .. import utils


logger = setup_logger('postgresql')
PS_SERVICE_NAME = 'postgresql'


class Postgresql(object):
    """
    Manages an PostgreSQL lifecycle.
    """

    def __init__(self):
        self._on_ci = os.environ.get('CI') == 'true'
        self._ps_port = 5432
        self._username = 'cloudify'
        self._password = 'cloudify'
        self._host = 'localhost'
        setup_logger('postgresql', logging.INFO)
        setup_logger('postgresql.trace', logging.INFO)

    def is_running(self):
        return utils.is_port_open(self._ps_port)

    def _run_query(self, query):
        with connect(dbname='postgres',
                     user=self._username,
                     host=self._host,
                     password=self._password) as con:
            con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            with con.cursor() as cur:
                cur.execute(query)
                logger.info('Running: ' + cur.query)
                status_message = cur.statusmessage
                try:
                    fetchall = cur.fetchall()
                except:
                    fetchall = None
                return {'status': status_message, 'all': fetchall}

    def create_db(self, db_name):
        query = "SELECT 1 from pg_database WHERE datname='{0}'".\
            format(db_name)
        result = self._run_query(query)
        db_exist = '1' in result['status']
        if db_exist:
            logger.info('database {0} exist, going to delete it!'.
                        format(db_name))
        self._run_query('DROP DATABASE IF EXISTS ' + db_name)
        self._run_query('CREATE DATABASE ' + db_name)
