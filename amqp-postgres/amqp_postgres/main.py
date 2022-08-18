import logging
import argparse
import queue

from cloudify.amqp_client import get_client
from manager_rest import config
from manager_rest.flask_utils import setup_flask_app

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
    port = BROKER_PORT_SSL if cfy_config.amqp_ca else BROKER_PORT_NO_SSL
    amqp_client = get_client(
        amqp_host=cfy_config.amqp_host,
        amqp_user=cfy_config.amqp_username,
        amqp_pass=cfy_config.amqp_password,
        amqp_vhost='/',
        amqp_port=port,
        ssl_enabled=bool(cfy_config.amqp_ca),
        ssl_cert_data=cfy_config.amqp_ca,
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
    with setup_flask_app().app_context():
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
