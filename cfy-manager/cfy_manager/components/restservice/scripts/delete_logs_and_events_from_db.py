#!/usr/bin/env python
#########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

import psycopg2
from datetime import datetime, timedelta
# cloudify rest configuration is available as config.instance
from manager_rest.config import instance as conf

POSTGRESQL_DEFAULT_PORT = 5432
RESTSERVICE_CONFIG_PATH = '/opt/manager/cloudify-rest.conf'
DEFAULT_SAVE_PERIOD = 5
EVENTS_TABLE_NAME = 'events'
LOGS_TABLE_NAME = 'logs'


def _connect():
    try:
        conn = psycopg2.connect(
            database=conf.postgresql_db_name,
            user=conf.postgresql_username,
            password=conf.postgresql_password,
            host=conf.postgresql_host,
            port=str(POSTGRESQL_DEFAULT_PORT)
        )
        conn.autocommit = True
        return conn
    except psycopg2.DatabaseError as e:
        raise Exception('Error during connection to postgres: {0}'
                        .format(str(e)))


def delete_old_logs_and_events():
    _delete_rows_from_table(DEFAULT_SAVE_PERIOD, EVENTS_TABLE_NAME)
    _delete_rows_from_table(DEFAULT_SAVE_PERIOD, LOGS_TABLE_NAME)


def _delete_rows_from_table(save_period, table):
    last_date_to_keep = str(datetime.today() - timedelta(days=save_period))
    with _connect() as conn:
        with conn.cursor() as cur:
            query = "DELETE FROM {0} WHERE reported_timestamp < '{1}'"\
                .format(table, last_date_to_keep)
            cur.execute(query)
            conn.commit()


if __name__ == '__main__':
    conf.load_from_file(RESTSERVICE_CONFIG_PATH)
    delete_old_logs_and_events()
