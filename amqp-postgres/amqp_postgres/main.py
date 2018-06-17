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

from cloudify.amqp_client import get_client

from manager_rest.flask_utils import setup_flask_app
from manager_rest.config import instance as manager_config

from .amqp_consumer import AMQPLogsEventsConsumer
from .postgres_publisher import DBLogEventPublisher

BROKER_PORT_SSL = 5671
BROKER_PORT_NO_SSL = 5672


def main():
    setup_flask_app()

    port = BROKER_PORT_SSL if \
        manager_config.amqp_ca_path else BROKER_PORT_NO_SSL
    amqp_client = get_client(
        amqp_host=manager_config.amqp_host,
        amqp_user=manager_config.amqp_username,
        amqp_pass=manager_config.amqp_password,
        amqp_vhost='/',
        amqp_port=port,
        ssl_enabled=bool(manager_config.amqp_ca_path),
        ssl_cert_path=manager_config.amqp_ca_path
    )

    db_publisher = DBLogEventPublisher()
    amqp_consumer = AMQPLogsEventsConsumer(
        message_processor=db_publisher.process
    )

    amqp_client.add_handler(amqp_consumer)
    amqp_client.consume()


if __name__ == '__main__':
    main()
