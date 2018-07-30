########
# Copyright (c) 2018 Cloudify Platform Ltd. All rights reserved
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
############

import Queue
from time import time
from threading import Thread, Lock

import psycopg2
from psycopg2.extras import execute_values, DictCursor
from collections import OrderedDict


EVENT_INSERT_QUERY = """
    INSERT INTO events (
        timestamp,
        reported_timestamp,
        _execution_fk,
        _tenant_id,
        _creator_id,
        event_type,
        message,
        message_code,
        operation,
        node_id,
        error_causes)
    VALUES %s
"""

EVENT_VALUES_TEMPLATE = """(
        now() AT TIME ZONE 'utc',
        CAST (%(timestamp)s AS TIMESTAMP),
        %(execution_id)s,
        %(tenant_id)s,
        %(creator_id)s,
        %(logger)s,
        %(level)s,
        %(message)s,
        %(message_code)s,
        %(operation)s,
        %(ndoe_id)s
    )
"""

LOG_INSERT_QUERY = """
    INSERT INTO logs (
        timestamp,
        reported_timestamp,
        _execution_fk,
        _tenant_id,
        _creator_id,
        logger,
        level,
        message,
        message_code,
        operation,
        node_id)
    VALUES %s
"""
LOG_VALUES_TEMPLATE = """(
        now() AT TIME ZONE 'utc',
        CAST (%(timestamp)s AS TIMESTAMP),
        %(execution_id)s,
        %(tenant_id)s,
        %(creator_id)s,
        %(logger)s,
        %(level)s,
        %(message)s,
        %(message_code)s,
        %(operation)s,
        %(node_id)s
    )
"""

EXECUTION_SELECT_QUERY = """
    SELECT
        id,
        _storage_id,
        _creator_id,
        _tenant_id
    FROM executions
    WHERE id = %s
"""


class DBLogEventPublisher(object):
    COMMIT_DELAY = 0.1  # seconds

    def __init__(self, config, acks_queue):
        self._lock = Lock()
        self._batch = Queue.Queue()

        self._last_commit = time()
        self.config = config
        self._executions_cache = LimitedSizeDict(10000)
        self._acks_queue = acks_queue

        # Create a separate thread to allow proper batching without losing
        # messages. Without this thread, if the messages were just committed,
        # and 1 new message is sent, then process will never commit, because
        # batch size wasn't exceeded and commit delay hasn't passed yet
        publish_thread = Thread(target=self._message_publisher)
        publish_thread.daemon = True
        publish_thread.start()

    def process(self, message, exchange, tag):
        self._batch.put((message, exchange, tag))

    def _message_publisher(self):
        conn = psycopg2.connect(
            dbname=self.config['postgresql_db_name'],
            host=self.config['postgresql_host'],
            user=self.config['postgresql_username'],
            password=self.config['postgresql_password'],
            cursor_factory=DictCursor
        )
        items = []
        while True:
            try:
                items.append(self._batch.get(0.3))
            except Queue.Empty:
                pass
            if len(items) > 100 or \
                    (items and (time() - self._last_commit > 0.5)):
                self._store(conn, items)
                items = []
                self._last_commit = time()

    def _get_execution(self, conn, item):
        execution_id = item['context']['execution_id']
        if execution_id not in self._executions_cache:
            with conn.cursor() as cur:
                cur.execute(EXECUTION_SELECT_QUERY, (execution_id, ))
                executions = cur.fetchall()
            if len(executions) != 1:
                raise ValueError('Expected 1 execution, found {0} (id: {1})'
                                 .format(len(executions), execution_id))
            self._executions_cache[execution_id] = executions[0]
        return self._executions_cache[execution_id]

    def _store(self, conn, items):
        events, logs = [], []

        tags = set()
        for item, exchange, tag in items:
            execution = self._get_execution(conn, item)
            if exchange == 'cloudify-events':
                events.append(self._get_event(item, execution))
            elif exchange == 'cloudify-logs':
                logs.append(self._get_log(item, execution))
            else:
                raise ValueError('Unknown exchange type: {0}'.format(exchange))
            tags.add(tag)

        with conn.cursor() as cur:
            if events:
                execute_values(cur, EVENT_INSERT_QUERY, events,
                               template=EVENT_VALUES_TEMPLATE)
            if logs:
                execute_values(cur, LOG_INSERT_QUERY, logs,
                               template=LOG_VALUES_TEMPLATE)
        conn.commit()
        for tag in tags:
            self._acks_queue.put(tag)

    @staticmethod
    def _get_log(message, execution):
        return {
            'timestamp': message['timestamp'],
            'execution_id': execution['_storage_id'],
            'tenant_id': execution['_tenant_id'],
            'creator_id': execution['_creator_id'],
            'logger': message['logger'],
            'level': message['level'],
            'message': message['message']['text'],
            'message_code': message['message_code'],
            'operation': message['context'].get('operation', ''),
            'node_id': message['context'].get('node_id', '')
        }

    @staticmethod
    def _get_event(message, execution):
        return {
            'timestamp': message['timestamp'],
            'execution_id': execution['_storage_id'],
            'tenant_id': execution['_tenant_id'],
            'creator_id': execution['_creator_id'],
            'logger': message['event_type'],
            'level': message['message']['text'],
            'message': message['message_code'],
            'message_code': message['context'].get('operation', ''),
            'operation': message['context'].get('node_id', ''),
            'node_id': message['context'].get('task_error_causes', '')
        }


class LimitedSizeDict(OrderedDict):
    """
    A FIFO dictionary with a maximum size limit. If number of keys reaches
    the limit, the elements added first will be popped
    Implementation taken from https://stackoverflow.com/a/2437645/978089
    """
    def __init__(self, size_limit=None, *args, **kwds):
        self.size_limit = size_limit
        OrderedDict.__init__(self, *args, **kwds)
        self._check_size_limit()

    def __setitem__(self, key, value):
        OrderedDict.__setitem__(self, key, value)
        self._check_size_limit()

    def _check_size_limit(self):
        if self.size_limit is not None:
            while len(self) > self.size_limit:
                self.popitem(last=False)
