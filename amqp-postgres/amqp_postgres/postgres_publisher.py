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

from uuid import uuid4
from time import time, sleep
from threading import Thread, Lock
from collections import OrderedDict

from manager_rest.storage import db
from manager_rest.storage.models import Event, Log, Execution


class DBLogEventPublisher(object):
    COMMIT_DELAY = 0.1  # seconds

    def __init__(self, app):
        self._lock = Lock()
        self._batch = []
        self._last_commit = time()
        self._app = app
        self._executions_cache = LimitedSizeDict(1000)

        # Create a separate thread to allow proper batching without losing
        # messages. Without this thread, if the messages were just committed,
        # and 1 new message is sent, then process will never commit, because
        # batch size wasn't exceeded and commit delay hasn't passed yet
        publish_thread = Thread(target=self._message_publisher)
        publish_thread.daemon = True
        publish_thread.start()

    def process(self, message, exchange):
        execution = self._get_current_execution(message)
        item = self._get_item(message, exchange, execution)
        with self._lock:
            self._batch.append(item)

    def _message_publisher(self):
        # This needs to be done here, because we need to push the app context
        # in each separate thread for the `db` object to work in it
        db.init_app(self._app)
        self._app.app_context().push()

        while True:
            if self._batch:
                with self._lock:
                    db.session.bulk_save_objects(self._batch)
                    self._safe_commit()
                    self._last_commit = time()
                    self._batch = []
            sleep(self.COMMIT_DELAY)

    @staticmethod
    def _safe_commit():
        try:
            db.session.commit()
        except BaseException:
            db.session.rollback()
            raise

    def _get_current_execution(self, message):
        """ Return execution from cache if exists, or from DB if needed """

        execution_id = message['context']['execution_id']
        execution = self._executions_cache.get(execution_id)
        if not execution:
            execution = Execution.query.filter_by(id=execution_id).first()
            self._executions_cache[execution_id] = execution
        return execution

    def _get_item(self, message, exchange, execution):
        if exchange == 'cloudify-events':
            return self._get_event(message, execution)
        elif exchange == 'cloudify-logs':
            return self._get_log(message, execution)
        else:
            raise ValueError('Unknown exchange type: {0}'.format(exchange))

    @staticmethod
    def _get_log(message, execution):
        return Log(
            id=str(uuid4()),
            reported_timestamp=message['timestamp'],
            logger=message['logger'],
            level=message['level'],
            message=message['message']['text'],
            operation=message['context'].get('operation'),
            node_id=message['context'].get('node_id'),
            _execution_fk=execution._storage_id,
            _tenant_id=execution._tenant_id,
            _creator_id=execution._creator_id
        )

    @staticmethod
    def _get_event(message, execution):
        return Event(
            id=str(uuid4()),
            reported_timestamp=message['timestamp'],
            event_type=message['event_type'],
            message=message['message']['text'],
            operation=message['context'].get('operation'),
            node_id=message['context'].get('node_id'),
            error_causes=message['context'].get('task_error_causes'),
            _execution_fk=execution._storage_id,
            _tenant_id=execution._tenant_id,
            _creator_id=execution._creator_id
        )


class LimitedSizeDict(OrderedDict):
    """
    A FIFO dictionary with a maximum size limit. If number of keys reaches
    the limit, the elements added first will be popped
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
