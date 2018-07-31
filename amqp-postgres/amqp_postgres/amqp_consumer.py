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
import Queue
import logging

from cloudify.amqp_client import AMQPConnection


class AckingAMQPConnection(AMQPConnection):
    def _process_publish(self, channel):
        self._process_acks()
        super(AckingAMQPConnection, self)._process_publish(channel)

    def _process_acks(self):
        while True:
            try:
                channel, tag = self.acks_queue.get_nowait()
                channel.basic_ack(tag)
            except Queue.Empty:
                return


logger = logging.getLogger(__name__)


class AMQPLogsEventsConsumer(object):
    LOGS_EXCHANGE = 'cloudify-logs'
    EVENTS_EXCHANGE = 'cloudify-events'

    def __init__(self, message_processor):
        self.queue = 'cloudify-logs-events'
        self._message_processor = message_processor

        # This is here because AMQPConnection expects it
        self.routing_key = ''

    def register(self, connection):
        channel = connection.channel()
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
#        channel.basic_recover(requeue=True)

    def process(self, channel, method, properties, body):
        try:
            parsed_body = json.loads(body)
            self._message_processor(parsed_body, method.exchange,
                                    (channel, method.delivery_tag))
        except Exception as e:
            logger.warn('Failed message processing: %s', e)
            logger.debug('Message was: %s', body)
