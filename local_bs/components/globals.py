from .. import constants
from ..config import config
from ..logger import get_logger

from .service_names import RABBITMQ, MANAGER

logger = get_logger('Globals')


def _set_external_port_and_protocol():
    # TODO: Change to nginx config
    if config[MANAGER]['security']['ssl_enabled']:
        logger.info('SSL is enabled, setting rest port to 443 and '
                    'rest protocol to https...')
        external_rest_port = 443
        external_rest_protocol = 'https'
    else:
        logger.info('SSL is disabled, setting rest port '
                    'to 80 and rest protocols to http...')
        external_rest_port = 80
        external_rest_protocol = 'http'
    config['external_rest_port'] = external_rest_port
    config['external_rest_protocol'] = external_rest_protocol


def _set_rabbitmq_config():
    config[RABBITMQ]['endpoint_ip'] = config['agent']['broker_ip']
    config[RABBITMQ]['broker_cert_path'] = constants.INTERNAL_CA_CERT_PATH


def _set_ip_config():
    if not config['agent']['broker_ip']:
        config['agent']['broker_ip'] = config[MANAGER]['private_ip']

    config[MANAGER]['file_server_root'] = constants.MANAGER_RESOURCES_HOME
    config[MANAGER]['file_server_url'] = 'https://{0}:{1}/resources'.format(
        config[MANAGER]['private_ip'],
        constants.INTERNAL_REST_PORT
    )


def set():
    _set_ip_config()
    _set_rabbitmq_config()
    _set_external_port_and_protocol()
