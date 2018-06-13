########
# Copyright (c) 2018 GigaSpaces Technologies Ltd. All rights reserved
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

import logging

from manager_rest.storage import get_storage_manager
from manager_rest.storage.models import Event, Log, Execution

logging.basicConfig()
logger = logging.getLogger('amqp_postgres.publisher')


class DBLogEventPublisher(object):
    def __init__(self):
        self._sm = get_storage_manager()

    def process(self, message, exchange):
        execution = self._sm.get(Execution, message['execution_id'])

        if exchange == 'cloudify-events':
            item = self._get_event(message)
        elif exchange == 'cloudify-logs':
            item = self._get_log(message)
        else:
            raise StandardError('Unknown exchange type: {0}'.format(exchange))

        item.execution = execution
        self._sm.put(item)

    @staticmethod
    def _get_log(message):
        return Log(
            reported_timestamp=message['timestamp'],
            logger=message['logger'],
            level=message['level'],
            message=message['message']['text'],
            operation=message['context'].get('operation'),
            node_id=message['context'].get('node_id')
        )

    @staticmethod
    def _get_event(message):
        return Event(
            reported_timestamp=message['timestamp'],
            event_type=message['event_type'],
            message=message['message']['text'],
            operation=message['context'].get('operation'),
            node_id=message['context'].get('node_id'),
            error_causes=message['context'].get('task_error_causes')
        )
