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

import psycopg2
from cloudify.utils import setup_logger
from integration_tests.framework import docker
from manager_rest.flask_utils import get_postgres_conf
from manager_rest.storage import db

logger = setup_logger('postgresql', logging.INFO)
setup_logger('postgresql.trace', logging.INFO)


def run_query(container_id, query, db_name=None, fetch_results=True):
    conf = get_postgres_conf()
    manager_ip = docker.get_manager_ip(container_id)

    db_name = db_name or conf.db_name
    with psycopg2.connect(database=db_name,
                          user=conf.username,
                          password=conf.password,
                          host=manager_ip) as con:
        con.autocommit = True
        logger.info('Trying to execute SQL query: ' + query)
        with closing(con.cursor()) as cur:
            try:
                cur.execute(query)
                fetchall = cur.fetchall() if fetch_results else None
                status_message = 'ok'
            except Exception as e:
                fetchall = None
                status_message = str(e)
            return {'status': status_message, 'all': fetchall}


def safe_drop_all(keep_tables):
    """Creates a single transaction that *always* drops all tables, regardless
    of relationships and foreign key constraints (as opposed to `db.drop_all`)
    """
    meta = db.metadata
    for table in reversed(meta.sorted_tables):
        if table.name in keep_tables:
            continue
        db.session.execute(table.delete())
    db.session.commit()
