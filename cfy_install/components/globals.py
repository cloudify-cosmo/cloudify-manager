from .. import constants
from ..config import config
from ..logger import get_logger

from .service_names import RABBITMQ, MANAGER, AGENT, NGINX

logger = get_logger('Globals')


def _set_external_port_and_protocol():
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
    config[NGINX]['external_rest_port'] = external_rest_port
    config[NGINX]['external_rest_protocol'] = external_rest_protocol
    config[NGINX]['internal_rest_port'] = constants.INTERNAL_REST_PORT


def _set_rabbitmq_config():
    config[RABBITMQ]['endpoint_ip'] = config['agent']['broker_ip']
    config[RABBITMQ]['broker_cert_path'] = constants.INTERNAL_CA_CERT_PATH


def _set_ip_config():
    private_ip = config[MANAGER]['private_ip']
    if not config[AGENT]['broker_ip']:
        config[AGENT]['broker_ip'] = private_ip

    config[MANAGER]['file_server_root'] = constants.MANAGER_RESOURCES_HOME
    config[MANAGER]['file_server_url'] = 'https://{0}:{1}/resources'.format(
        private_ip,
        constants.INTERNAL_REST_PORT
    )

    networks = config[AGENT]['networks']
    if not networks or 'default' not in networks:
        networks['default'] = private_ip


def _set_cert_config():
    nginx_conf = config[NGINX]
    nginx_conf['internal_rest_host'] = config[MANAGER]['private_ip']
    nginx_conf['external_rest_host'] = config[MANAGER]['public_ip']
    nginx_conf['internal_ca_cert_path'] = constants.INTERNAL_CA_CERT_PATH
    nginx_conf['internal_cert_path'] = constants.INTERNAL_CERT_PATH
    nginx_conf['internal_key_path'] = constants.INTERNAL_KEY_PATH
    nginx_conf['external_cert_path'] = constants.EXTERNAL_CERT_PATH
    nginx_conf['external_key_path'] = constants.EXTERNAL_KEY_PATH


def _validate_inputs():
    for key in ('private_ip', 'public_ip'):
        ip = config[MANAGER].get(key)
        if not ip:
            raise StandardError(
                '{0} not set in the config.\n'
                'Edit {1}/config.json to set it'.format(
                    key, constants.CLOUDIFY_BOOTSTRAP_DIR
                )
            )


def set_globals():
    _validate_inputs()
    _set_ip_config()
    _set_rabbitmq_config()
    _set_external_port_and_protocol()
    _set_cert_config()
