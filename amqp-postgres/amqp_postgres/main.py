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
import yaml
import logging

from cloudify.amqp_client import get_client

from .amqp_consumer import AMQPLogsEventsConsumer
from .postgres_publisher import DBLogEventPublisher

logger = logging.getLogger(__name__)
BROKER_PORT_SSL = 5671
BROKER_PORT_NO_SSL = 5672

DEFAULT_LOG_PATH = '/var/log/cloudify/amqp-postgres/amqp_postgres.log'
CONFIG_PATH = '/opt/manager/cloudify-rest.conf'


def _create_amqp_client(config):
    db_publisher = DBLogEventPublisher(config)
    amqp_consumer = AMQPLogsEventsConsumer(
        message_processor=db_publisher.process
    )

    port = BROKER_PORT_SSL if config['amqp_ca_path'] else BROKER_PORT_NO_SSL
    amqp_client = get_client(
        amqp_host=config['amqp_host'],
        amqp_user=config['amqp_username'],
        amqp_pass=config['amqp_password'],
        amqp_vhost='/',
        amqp_port=port,
        ssl_enabled=bool(config['amqp_ca_path']),
        ssl_cert_path=config['amqp_ca_path']
    )
    amqp_client.add_handler(amqp_consumer)
    return amqp_client


def main():
    logging.basicConfig(level=logging.INFO)
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)
    amqp_client = _create_amqp_client(config)

    logger.info('Starting consuming...')
    amqp_client.consume()


if __name__ == '__main__':
    main()
