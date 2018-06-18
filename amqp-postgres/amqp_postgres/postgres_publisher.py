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

from uuid import uuid4

from manager_rest.utils import set_current_tenant
from manager_rest.storage import get_storage_manager
from manager_rest.storage.models import Event, Log, Execution


class DBLogEventPublisher(object):
    def __init__(self):
        self._sm = get_storage_manager()

    def process(self, message, exchange):
        execution = self._get_current_execution(message)
        item = self._get_item(message, exchange)
        try:
            set_current_tenant(execution.tenant)
            item.set_execution(execution)
            self._sm.put(item)
        finally:
            set_current_tenant(None)

    def _get_current_execution(self, message):
        return self._sm.get(Execution, message['context']['execution_id'])

    def _get_item(self, message, exchange):
        if exchange == 'cloudify-events':
            return self._get_event(message)
        elif exchange == 'cloudify-logs':
            return self._get_log(message)
        else:
            raise ValueError('Unknown exchange type: {0}'.format(exchange))

    @staticmethod
    def _get_log(message):
        return Log(
            id=str(uuid4()),
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
            id=str(uuid4()),
            reported_timestamp=message['timestamp'],
            event_type=message['event_type'],
            message=message['message']['text'],
            operation=message['context'].get('operation'),
            node_id=message['context'].get('node_id'),
            error_causes=message['context'].get('task_error_causes')
        )
