########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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
import os

from cloudify.amqp_client import get_client

from manager_rest.app_logging import setup_logger
from manager_rest.config import instance as config
from manager_rest.flask_utils import setup_flask_app

from .amqp_consumer import AMQPLogsEventsConsumer
from .postgres_publisher import DBLogEventPublisher

BROKER_PORT_SSL = 5671
BROKER_PORT_NO_SSL = 5672

DEFAULT_LOG_PATH = '/var/log/cloudify/amqp-postgres/amqp_postgres.log'


def _setup_flask_app():
    app = setup_flask_app()
    config.load_configuration()
    config.rest_service_log_path = os.environ.get(
        'LOG_PATH', DEFAULT_LOG_PATH
    )
    setup_logger(app.logger)
    return app


def main():
    app = _setup_flask_app()

    port = BROKER_PORT_SSL if \
        config.amqp_ca_path else BROKER_PORT_NO_SSL
    amqp_client = get_client(
        amqp_host=config.amqp_host,
        amqp_user=config.amqp_username,
        amqp_pass=config.amqp_password,
        amqp_vhost='/',
        amqp_port=port,
        ssl_enabled=bool(config.amqp_ca_path),
        ssl_cert_path=config.amqp_ca_path
    )

    db_publisher = DBLogEventPublisher()
    amqp_consumer = AMQPLogsEventsConsumer(
        message_processor=db_publisher.process
    )

    amqp_client.add_handler(amqp_consumer)

    app.logger.info('Starting consuming...')
    amqp_client.consume()


if __name__ == '__main__':
    main()
