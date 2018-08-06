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

import json
import Queue
import logging
from time import time
from threading import Thread, Lock

import psycopg2
from psycopg2.extras import execute_values, DictCursor
from collections import OrderedDict


logger = logging.getLogger(__name__)

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
        error_causes,
        visibility)
    VALUES %s
"""

EVENT_VALUES_TEMPLATE = """(
        now() AT TIME ZONE 'utc',
        CAST (%(timestamp)s AS TIMESTAMP),
        %(execution_id)s,
        %(tenant_id)s,
        %(creator_id)s,
        %(event_type)s,
        %(message)s,
        %(message_code)s,
        %(operation)s,
        %(node_id)s,
        %(error_causes)s,
        %(visibility)s
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
        node_id,
        visibility)
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
        %(node_id)s,
        %(visibility)s
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

    def __init__(self, config, connection):
        self._lock = Lock()
        self._batch = Queue.Queue()

        self._last_commit = time()
        self.config = config
        self._executions_cache = LimitedSizeDict(10000)
        self._amqp_connection = connection
        self._started = Queue.Queue()

    def start(self):
        # Create a separate thread to allow proper batching without losing
        # messages. Without this thread, if the messages were just committed,
        # and 1 new message is sent, then process will never commit, because
        # batch size wasn't exceeded and commit delay hasn't passed yet
        publish_thread = Thread(target=self._message_publisher)
        publish_thread.daemon = True
        publish_thread.start()
        try:
            started = self._started.get(3)
        except Queue.Empty:
            raise RuntimeError('Timeout connecting to database')
        else:
            if isinstance(started, Exception):
                raise started

    def process(self, message, exchange, tag):
        self._batch.put((message, exchange, tag))

    def connect(self):
        host, _, port = self.config['postgresql_host'].partition(':')
        return psycopg2.connect(
            dbname=self.config['postgresql_db_name'],
            host=host,
            port=port or 5432,
            user=self.config['postgresql_username'],
            password=self.config['postgresql_password'],
            cursor_factory=DictCursor
        )

    def _message_publisher(self):
        try:
            conn = self.connect()
        except psycopg2.OperationalError as e:
            self._started.put(e)
            self.on_db_connection_error()
        else:
            self._started.put(True)
        items = []
        while True:
            try:
                items.append(self._batch.get(timeout=0.3))
            except Queue.Empty:
                pass
            if len(items) > 100 or \
                    (items and (time() - self._last_commit > 0.5)):
                try:
                    self._store(conn, items)
                except psycopg2.OperationalError:
                    self.on_db_connection_error()
                except psycopg2.IntegrityError:
                    logger.exception('Error storing %d logs+events',
                                     len(items))
                    conn.rollback()
                items = []
                self._last_commit = time()

    def _get_execution(self, conn, execution_id):
        if execution_id not in self._executions_cache:
            with conn.cursor() as cur:
                cur.execute(EXECUTION_SELECT_QUERY, (execution_id, ))
                executions = cur.fetchall()
            if len(executions) > 1:
                raise ValueError('Expected 1 execution, found {0} (id: {1})'
                                 .format(len(executions), execution_id))
            elif not executions:
                execution = None
            else:
                execution = executions[0]
            self._executions_cache[execution_id] = execution
        return self._executions_cache[execution_id]

    def _store(self, conn, items):
        events, logs = [], []

        acks = []
        for item, exchange, ack in items:
            acks.append(ack)
            execution_id = item['context']['execution_id']
            execution = self._get_execution(conn, execution_id)
            if execution is None:
                logger.warning('No execution found: %s', execution_id)
                continue
            if exchange == 'cloudify-events':
                event = self._get_event(item, execution)
                if event is not None:
                    events.append(event)
            elif exchange == 'cloudify-logs':
                log = self._get_log(item, execution)
                if log is not None:
                    logs.append(log)
            else:
                raise ValueError('Unknown exchange type: {0}'.format(exchange))

        with conn.cursor() as cur:
            if events:
                execute_values(cur, EVENT_INSERT_QUERY, events,
                               template=EVENT_VALUES_TEMPLATE)
            if logs:
                execute_values(cur, LOG_INSERT_QUERY, logs,
                               template=LOG_VALUES_TEMPLATE)
        logger.debug('commit %s', len(logs) + len(events))
        conn.commit()
        for ack in acks:
            self._amqp_connection.acks_queue.put(ack)

    def on_db_connection_error(self):
        logger.critical('Database down - cannot continue')
        self._amqp_connection.close()
        raise RuntimeError('Database down')

    @staticmethod
    def _get_log(message, execution):
        try:
            return {
                'timestamp': message['timestamp'],
                'execution_id': execution['_storage_id'],
                'tenant_id': execution['_tenant_id'],
                'creator_id': execution['_creator_id'],
                'logger': message['logger'],
                'level': message['level'],
                'message': message['message']['text'],
                'message_code': message.get('message_code'),
                'operation': message['context'].get('operation'),
                'node_id': message['context'].get('node_id'),
                'visibility': 'tenant'
            }
        except KeyError as e:
            logger.warning('Error formatting log: %s', e)
            logger.debug('Malformed log: %s', message)
            return None

    @staticmethod
    def _get_event(message, execution):
        task_error_causes = message['context'].get('task_error_causes')
        if task_error_causes is not None:
            task_error_causes = json.dumps(task_error_causes)
        try:
            return {
                'timestamp': message['timestamp'],
                'execution_id': execution['_storage_id'],
                'tenant_id': execution['_tenant_id'],
                'creator_id': execution['_creator_id'],
                'event_type': message['event_type'],
                'message': message['message']['text'],
                'message_code': message.get('message_code'),
                'operation': message['context'].get('operation'),
                'node_id': message['context'].get('node_id'),
                'error_causes': task_error_causes,
                'visibility': 'tenant'
            }
        except KeyError as e:
            logger.warning('Error formatting event: %s', e)
            logger.debug('Malformed event: %s', message)
            return None


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
