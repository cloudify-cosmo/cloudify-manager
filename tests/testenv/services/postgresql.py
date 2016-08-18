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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
from contextlib import closing

import pg8000

from cloudify.utils import setup_logger

from testenv import utils

logger = setup_logger('postgresql', logging.INFO)
setup_logger('postgresql.trace', logging.INFO)


def _run_query(query):
    with closing(pg8000.connect(database='postgres',
                                user='cloudify',
                                password='cloudify',
                                host=utils.get_manager_ip())) as con:
        con.autocommit = True
        with closing(con.cursor()) as cur:
            cur.execute(query)
            logger.info('Running: {0}'.format(query))
            status_message = cur.description
            try:
                fetchall = cur.fetchall()
            except:
                fetchall = None
            return {'status': status_message, 'all': fetchall}


def create_db(db_name):
    query = "SELECT 1 from pg_database WHERE datname='{0}'".format(db_name)
    result = _run_query(query)
    db_exist = '1' in result['status']
    if db_exist:
        logger.info('database {0} exist, going to delete it!'.format(db_name))
    _run_query('DROP DATABASE IF EXISTS {0}'.format(db_name))
    _run_query('CREATE DATABASE {0}'.format(db_name))
