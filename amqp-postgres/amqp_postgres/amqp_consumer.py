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

import json
from uuid import uuid4

from flask import current_app


class AMQPLogsEventsConsumer(object):
    LOGS_EXCHANGE = 'cloudify-logs'
    EVENTS_EXCHANGE = 'cloudify-events'

    def __init__(self, message_processor):
        self.queue = str(uuid4())
        self._connection = None
        self._in_channel = None
        self._message_processor = message_processor

        # This is here because AMQPConnection expects it
        self.routing_key = ''

    def register(self, connection):
        self._connection = connection
        self._in_channel = connection.channel()
        self._register_queue(self._in_channel)

    def _register_queue(self, channel):
        channel.confirm_delivery()
        channel.queue_declare(queue=self.queue,
                              durable=True,
                              auto_delete=False)

        for exchange in [self.LOGS_EXCHANGE, self.EVENTS_EXCHANGE]:
            channel.exchange_declare(exchange=exchange,
                                     auto_delete=False,
                                     durable=True,
                                     exchange_type='fanout')
            channel.queue_bind(queue=self.queue,
                               exchange=exchange)

        channel.basic_consume(self.process, self.queue)

    def process(self, channel, method, properties, body):
        channel.basic_ack(method.delivery_tag)
        try:
            parsed_body = json.loads(body)
            self._message_processor(parsed_body, method.exchange)
        except Exception as e:
            current_app.logger.warn('Failed message processing: {0}'.format(e))
