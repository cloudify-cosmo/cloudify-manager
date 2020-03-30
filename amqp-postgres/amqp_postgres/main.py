########
# Copyright (c) 2014 Cloudify Platform Ltd. All rights reserved
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
import argparse

from cloudify._compat import queue
from cloudify.amqp_client import get_client
from manager_rest import config

from .amqp_consumer import AMQPLogsEventsConsumer, AckingAMQPConnection
from .postgres_publisher import DBLogEventPublisher

logger = logging.getLogger(__name__)
BROKER_PORT_SSL = 5671
BROKER_PORT_NO_SSL = 5672

DEFAULT_LOG_PATH = '/var/log/cloudify/amqp-postgres/amqp_postgres.log'
CONFIG_PATH = '/opt/manager/cloudify-rest.conf'


def _create_connections():
    acks_queue = queue.Queue()
    cfy_config = config.instance
    port = BROKER_PORT_SSL if cfy_config.amqp_ca_path else BROKER_PORT_NO_SSL
    amqp_client = get_client(
        amqp_host=cfy_config.amqp_host,
        amqp_user=cfy_config.amqp_username,
        amqp_pass=cfy_config.amqp_password,
        amqp_vhost='/',
        amqp_port=port,
        ssl_enabled=bool(cfy_config.amqp_ca_path),
        ssl_cert_path=cfy_config.amqp_ca_path,
        cls=AckingAMQPConnection
    )
    amqp_client.acks_queue = acks_queue
    db_publisher = DBLogEventPublisher(config.instance, amqp_client)
    amqp_consumer = AMQPLogsEventsConsumer(
        message_processor=db_publisher.process
    )

    amqp_client.add_handler(amqp_consumer)
    db_publisher.start()
    return amqp_client, db_publisher


def main(args):
    logging.basicConfig(
        level=args.get('loglevel', 'INFO').upper(),
        filename=args.get('logfile', DEFAULT_LOG_PATH),
        format="%(asctime)s %(message)s")
    config.instance.load_from_file(args['config'])
    config.instance.load_from_db()
    amqp_client, db_publisher = _create_connections()

    logger.info('Starting consuming...')
    amqp_client.consume()
    if db_publisher.error_exit:
        raise db_publisher.error_exit


def cli():
    """Parse arguments and run main"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=CONFIG_PATH,
                        help='Path to the config file')
    parser.add_argument('--logfile', default=DEFAULT_LOG_PATH,
                        help='Path to the log file')
    parser.add_argument('--log-level', dest='loglevel', default='INFO',
                        help='Logging level')
    args = parser.parse_args()
    main(vars(args))


if __name__ == '__main__':
    cli()
