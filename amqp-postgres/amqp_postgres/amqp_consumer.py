########
# Copyright (c) 2018 Cloudify Platform Ltd.. All rights reserved
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
import logging

from cloudify._compat import queue
from cloudify.amqp_client import AMQPConnection
from cloudify.constants import EVENTS_EXCHANGE_NAME, LOGS_EXCHANGE_NAME


class AckingAMQPConnection(AMQPConnection):
    def _process_publish(self, channel):
        self._process_acks()
        super(AckingAMQPConnection, self)._process_publish(channel)

    def _process_acks(self):
        while True:
            try:
                channel, tag = self.acks_queue.get_nowait()
                channel.basic_ack(tag)
            except queue.Empty:
                return


logger = logging.getLogger(__name__)


class AMQPLogsEventsConsumer(object):

    def __init__(self, message_processor):
        self.queue = 'cloudify-logs-events'
        self._message_processor = message_processor

        # This is here because AMQPConnection expects it
        self.routing_key = ''

    def register(self, connection, channel):
        channel.confirm_delivery()
        channel.queue_declare(queue=self.queue,
                              durable=True,
                              auto_delete=False)

        # Binding the logs queue
        self._bind_queue_to_exchange(channel, LOGS_EXCHANGE_NAME, 'fanout')

        # Binding the events queue
        self._bind_queue_to_exchange(channel,
                                     EVENTS_EXCHANGE_NAME,
                                     'topic',
                                     routing_key='events.#')
        channel.basic_consume(self.queue, self.process)

    def process(self, channel, method, properties, body):
        try:
            if method.routing_key == 'events.hooks':
                channel.basic_ack(method.delivery_tag)
                return
            parsed_body = json.loads(body)
            self._message_processor(parsed_body, method.exchange,
                                    (channel, method.delivery_tag))
        except Exception as e:
            logger.warn('Failed message processing: %s', e)
            logger.debug('Message was: %s', body)

    def _bind_queue_to_exchange(self,
                                channel,
                                exchange_name,
                                exchange_type,
                                routing_key=None):
        channel.exchange_declare(exchange=exchange_name,
                                 auto_delete=False,
                                 durable=True,
                                 exchange_type=exchange_type)
        channel.queue_bind(queue=self.queue,
                           exchange=exchange_name,
                           routing_key=routing_key)
