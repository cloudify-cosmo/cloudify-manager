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

import argparse

from cloudify.amqp_client import get_client

from manager_rest.flask_utils import setup_flask_app

from .amqp_consumer import AMQPLogsEventsConsumer
from .postgres_publisher import DBLogEventPublisher

BROKER_PORT_SSL = 5671
BROKER_PORT_NO_SSL = 5672


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--amqp-hostname', required=False,
                        default='localhost')
    parser.add_argument('--amqp-username', required=False,
                        default='guest')
    parser.add_argument('--amqp-password', required=False,
                        default='guest')
    parser.add_argument('--amqp-ssl-enabled', required=False,
                        type=bool, default=True)
    parser.add_argument('--amqp-ca-cert-path', required=False,
                        default='')
    parser.add_argument('--postgres-hostname', required=False,
                        default='localhost')
    parser.add_argument('--postgres-db', required=True)
    parser.add_argument('--postgres-user', required=True)
    parser.add_argument('--postgres-password', required=True)
    return parser.parse_args()


def main(args):
    setup_flask_app()

    port = BROKER_PORT_SSL if args.amqp_ssl_enabled else BROKER_PORT_NO_SSL
    amqp_client = get_client(
        amqp_host=args.amqp_hostname,
        amqp_user=args.amqp_username,
        amqp_pass=args.amqp_password,
        amqp_vhost='/',
        amqp_port=port,
        ssl_enabled=args.amqp_ssl_enabled,
        ssl_cert_path=args.amqp_ca_cert_path
    )

    db_publisher = DBLogEventPublisher()
    amqp_consumer = AMQPLogsEventsConsumer(
        message_processor=db_publisher.process
    )

    amqp_client.add_handler(amqp_consumer)
    amqp_client.consume()


if __name__ == '__main__':
    main(parse_args())
