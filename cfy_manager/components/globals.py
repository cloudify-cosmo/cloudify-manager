#########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

import string
import random

from .. import constants
from ..config import config
from ..logger import get_logger

from .service_names import RABBITMQ, MANAGER, INFLUXB

from . import PRIVATE_IP, ENDPOINT_IP, SECURITY, AGENT, CONSTANTS,\
    ADMIN_PASSWORD

BROKER_IP = 'broker_ip'
BROKER_USERNAME = 'broker_user'
BROKER_PASSWORD = 'broker_pass'
logger = get_logger('Globals')


def _set_external_port_and_protocol():
    if config[MANAGER][SECURITY]['ssl_enabled']:
        logger.info('SSL is enabled, setting rest port to 443 and '
                    'rest protocol to https...')
        external_rest_port = 443
        external_rest_protocol = 'https'
    else:
        logger.info('SSL is disabled, setting rest port '
                    'to 80 and rest protocols to http...')
        external_rest_port = 80
        external_rest_protocol = 'http'

    config[MANAGER]['external_rest_port'] = external_rest_port
    config[MANAGER]['external_rest_protocol'] = external_rest_protocol


def _set_rabbitmq_config():
    config[RABBITMQ][ENDPOINT_IP] = config[AGENT][BROKER_IP]
    config[RABBITMQ]['broker_cert_path'] = constants.CA_CERT_PATH


def _set_ip_config():
    private_ip = config[MANAGER][PRIVATE_IP]
    config[AGENT][BROKER_IP] = private_ip

    config[MANAGER]['file_server_root'] = constants.MANAGER_RESOURCES_HOME
    config[MANAGER]['file_server_url'] = 'https://{0}:{1}/resources'.format(
        private_ip,
        constants.INTERNAL_REST_PORT
    )

    networks = config[AGENT]['networks']
    if not networks or 'default' not in networks:
        networks['default'] = private_ip


def _set_agent_broker_credentials():
    config[AGENT][BROKER_USERNAME] = config[RABBITMQ]['username']
    config[AGENT][BROKER_PASSWORD] = config[RABBITMQ]['password']


def _set_constant_config():
    const_conf = config.setdefault(CONSTANTS, {})

    const_conf['ca_cert_path'] = constants.CA_CERT_PATH
    const_conf['internal_cert_path'] = constants.INTERNAL_CERT_PATH
    const_conf['internal_key_path'] = constants.INTERNAL_KEY_PATH
    const_conf['external_cert_path'] = constants.EXTERNAL_CERT_PATH
    const_conf['external_key_path'] = constants.EXTERNAL_KEY_PATH

    const_conf['internal_rest_port'] = constants.INTERNAL_REST_PORT


def _set_admin_password():
    if not config[MANAGER][SECURITY][ADMIN_PASSWORD]:
        config[MANAGER][SECURITY][ADMIN_PASSWORD] = _generate_password()


def _generate_password(length=12):
    chars = string.ascii_lowercase + string.ascii_uppercase + string.digits
    password = ''.join(random.choice(chars) for _ in range(length))
    logger.info('Generated password: {0}'.format(password))
    return password


def _set_influx_db_endpoint():
    influxdb_endpoint_ip = config[INFLUXB][ENDPOINT_IP]

    if influxdb_endpoint_ip:
        config[INFLUXB]['is_internal'] = False
        logger.info('External InfluxDB Endpoint IP provided: {0}'.format(
            influxdb_endpoint_ip))
    else:
        config[INFLUXB]['is_internal'] = True
        influxdb_endpoint_ip = config[MANAGER][PRIVATE_IP]
        config[INFLUXB][ENDPOINT_IP] = influxdb_endpoint_ip


def set_globals():
    _set_ip_config()
    _set_agent_broker_credentials()
    _set_rabbitmq_config()
    _set_external_port_and_protocol()
    _set_constant_config()
    _set_admin_password()
    _set_influx_db_endpoint()
