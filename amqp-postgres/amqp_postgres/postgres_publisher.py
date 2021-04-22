import json
import logging
from time import time
from threading import Thread, Lock

import psycopg2
import psycopg2.errorcodes
from psycopg2.extras import execute_values, DictCursor
from collections import OrderedDict

from cloudify._compat import queue
from cloudify.constants import EVENTS_EXCHANGE_NAME, LOGS_EXCHANGE_NAME
from manager_rest.flask_utils import setup_flask_app


logger = logging.getLogger(__name__)

BATCH_DELAY = 0.5

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
        visibility,
        source_id,
        target_id)
    VALUES %s
"""

EVENT_VALUES_TEMPLATE = """(
        now() at time zone 'utc',
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
        %(visibility)s,
        %(source_id)s,
        %(target_id)s
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
        visibility,
        source_id,
        target_id)
    VALUES %s
"""

LOG_VALUES_TEMPLATE = """(
        now() at time zone 'utc',
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
        %(visibility)s,
        %(source_id)s,
        %(target_id)s
    )
"""

EXECUTION_SELECT_QUERY = """
    SELECT
        id,
        _storage_id,
        _creator_id,
        _tenant_id,
        visibility
    FROM executions
    WHERE id = %s
"""


def _strip_nul(text):
    """Remove NUL values from the text, so that it can be treated as text

    There should likely be no NUL values in human-readable logs anyway.
    """
    return text.replace('\x00', '<NUL>')


class DBLogEventPublisher(object):
    COMMIT_DELAY = 0.1  # seconds

    def __init__(self, config, connection):
        self._lock = Lock()
        self._batch = queue.Queue()

        self._last_commit = time()
        self.config = config
        self._amqp_connection = connection
        self._started = queue.Queue()
        self._reset_cache()
        # exception stored here will be raised by the main thread
        self.error_exit = None

    def _reset_cache(self):
        self._executions_cache = LimitedSizeDict(100)

    def _sanitize_cache(self):
        """Drop None executions from the cache.

        This is to be run after every batch of items, so that the cached
        result that "the execution doesn't exist" can be dropped, because
        the execution might well exist on the next batch.
        """
        for key, execution in list(self._executions_cache.items()):
            if execution is None:
                self._executions_cache.pop(key)

    def start(self):
        self.error_exit = None
        # Create a separate thread to allow proper batching without losing
        # messages. Without this thread, if the messages were just committed,
        # and 1 new message is sent, then process will never commit, because
        # batch size wasn't exceeded and commit delay hasn't passed yet
        publish_thread = Thread(target=self._message_publisher)
        publish_thread.daemon = True
        publish_thread.start()
        try:
            started = self._started.get(3)
        except queue.Empty:
            raise RuntimeError('Timeout connecting to database')
        else:
            if isinstance(started, Exception):
                raise started

    def process(self, message, exchange, tag):
        self._batch.put((message, exchange, tag))

    def connect(self):
        with setup_flask_app().app_context():
            db_url = self.config.db_url
            # This is to cope with Azure external DB urls:
            # https://docs.microsoft.com/en-us/azure/postgresql/
            #   quickstart-create-server-database-azure-cli
            if db_url.count('@') > 1:
                db_url = db_url.replace('@', '%40', 1)
            return psycopg2.connect(
                db_url,
                cursor_factory=DictCursor,
            )

    def _message_publisher(self):
        try:
            conn = self.connect()
        except psycopg2.OperationalError as e:
            self._started.put(e)
            self.on_db_connection_error(e)
        else:
            self._started.put(True)
        items = []
        while True:
            try:
                items.append(self._batch.get(timeout=BATCH_DELAY / 2))
            except queue.Empty:
                pass
            if len(items) > 100 or \
                    (items and (time() - self._last_commit > BATCH_DELAY)):
                try:
                    self._store(conn, items)
                except psycopg2.OperationalError as e:
                    self.on_db_connection_error(e)
                except Exception:
                    logger.info('Error storing %d logs+events in batch',
                                len(items))
                    conn.rollback()
                    # in case the integrityError was caused by stale cache,
                    # clean it entirely before trying to insert without
                    # batching.
                    # This happens rarely.
                    self._reset_cache()
                    self._store_nobatch(conn, items)
                items = []
                self._last_commit = time()
                self._sanitize_cache()

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

    def _get_db_item(self, conn, message, exchange):
        execution_id = message['context']['execution_id']
        execution = self._get_execution(conn, execution_id)
        if execution is None:
            logger.warning('No execution found: %s', execution_id)
            return

        if exchange == EVENTS_EXCHANGE_NAME:
            get_item = self._get_event
        elif exchange == LOGS_EXCHANGE_NAME:
            get_item = self._get_log
        else:
            raise ValueError('Unknown exchange type: {0}'.format(exchange))
        return get_item(message, execution)

    def _store(self, conn, items):
        events, logs = [], []

        acks = []
        for message, exchange, ack in items:
            acks.append(ack)
            item = self._get_db_item(conn, message, exchange)
            if item is None:
                continue
            target = events if exchange == EVENTS_EXCHANGE_NAME else logs
            target.append(item)

        with conn.cursor() as cur:
            self._insert_events(cur, events)
            self._insert_logs(cur, logs)
        logger.debug('commit %s', len(logs) + len(events))
        conn.commit()
        for ack in acks:
            self._amqp_connection.acks_queue.put(ack)

    def _store_nobatch(self, conn, items):
        """Store the items one by one, without batching.

        This is to be used in the anomalous cases where inserting the whole
        batch throws an IntegrityError - we fall back to inserting the items
        one by one, so that only the errorneous message is dropped.
        """
        for message, exchange, ack in items:
            item = self._get_db_item(conn, message, exchange)
            if item is None:
                continue
            insert = (self._insert_events if exchange == EVENTS_EXCHANGE_NAME
                      else self._insert_logs)
            try:
                with conn.cursor() as cur:
                    insert(cur, [item])
                conn.commit()
            except psycopg2.OperationalError as e:
                self.on_db_connection_error(e)
            except (psycopg2.IntegrityError, ValueError):
                logger.debug('Error storing %s: %s', exchange, item)
                conn.rollback()
            except psycopg2.ProgrammingError as e:
                if e.pgcode == psycopg2.errorcodes.UNDEFINED_COLUMN:
                    logger.debug('Error storing %s: %s (undefined column)',
                                 exchange, item)
                else:
                    logger.exception('Error storing %s: %s (ProgrammingError)',
                                     exchange, item)
                conn.rollback()
            except Exception:
                logger.exception('Unexpected error while storing %s: %s',
                                 exchange, item)
                conn.rollback()

    def _insert_events(self, cursor, events):
        if not events:
            return
        execute_values(cursor, EVENT_INSERT_QUERY, events,
                       template=EVENT_VALUES_TEMPLATE)

    def _insert_logs(self, cursor, logs):
        if not logs:
            return
        execute_values(cursor, LOG_INSERT_QUERY, logs,
                       template=LOG_VALUES_TEMPLATE)

    def on_db_connection_error(self, err):
        logger.critical('Database down - cannot continue')
        self._amqp_connection.close()
        self.error_exit = err
        raise self.error_exit

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
                'message': _strip_nul(message['message']['text']),
                'message_code': message.get('message_code'),
                'operation': message['context'].get('operation'),
                'node_id': message['context'].get('node_id'),
                'source_id': message['context'].get('source_id'),
                'target_id': message['context'].get('target_id'),
                'visibility': execution['visibility']
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
                'message': _strip_nul(message['message']['text']),
                'message_code': message.get('message_code'),
                'operation': message['context'].get('operation'),
                'node_id': message['context'].get('node_id'),
                'source_id': message['context'].get('source_id'),
                'target_id': message['context'].get('target_id'),
                'error_causes': task_error_causes,
                'visibility': execution['visibility']
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
