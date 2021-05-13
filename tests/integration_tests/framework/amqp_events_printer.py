########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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

import os
import json
import time

from pika.exceptions import AMQPConnectionError

import cloudify.event
import cloudify.logs
from cloudify_cli.colorful_event import ColorfulEvent
from cloudify.constants import EVENTS_EXCHANGE_NAME, LOGS_EXCHANGE_NAME

from integration_tests.framework import utils

logger = utils.setup_logger('events_printer')


def _consume_events(connection):
    channel = connection.channel()
    queues = []

    # Binding the logs queue
    _bind_queue_to_exchange(channel, LOGS_EXCHANGE_NAME, 'fanout', queues)

    # Binding the events queue
    _bind_queue_to_exchange(channel, EVENTS_EXCHANGE_NAME, 'topic', queues,
                            routing_key='events.#')

    if not os.environ.get('CI'):
        cloudify.logs.EVENT_CLASS = ColorfulEvent
    cloudify.logs.EVENT_VERBOSITY_LEVEL = cloudify.event.MEDIUM_VERBOSE

    def callback(ch, method, properties, body):
        try:
            ev = json.loads(body)
            output = cloudify.logs.create_event_message_prefix(ev)
            if output:
                print(output)
        except Exception:
            logger.error('event/log format error - output: {0}'
                         .format(body), exc_info=True)

    channel.basic_consume(queues[0], callback, auto_ack=True)
    channel.basic_consume(queues[1], callback, auto_ack=True)
    channel.start_consuming()


def _bind_queue_to_exchange(channel,
                            exchange_name,
                            exchange_type,
                            queues,
                            routing_key=None):
    channel.exchange_declare(exchange=exchange_name,
                             exchange_type=exchange_type,
                             auto_delete=False,
                             durable=True)
    result = channel.queue_declare('', exclusive=True)
    queue_name = result.method.queue
    queues.append(queue_name)
    channel.queue_bind(exchange=exchange_name,
                       queue=queue_name,
                       routing_key=routing_key)


def print_events(container_id):
    """Print logs and events from rabbitmq.

    This consumes directly cloudify-logs and cloudify-events-topic exchanges.
    (As opposed to the usual means of fetching events using the REST api).

    Note: This method is only used for events/logs printing.
    Tests that need to assert on event should use the REST client events
    module.
    """
    while True:
        try:
            connection = utils.create_pika_connection(container_id)
            _consume_events(connection)
        except AMQPConnectionError as e:
            logger.debug('print_events got: %s', e)
            time.sleep(3)
