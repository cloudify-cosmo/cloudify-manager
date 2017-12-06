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

import json
from os.path import join

from .. import (
    SERVICE_USER,
    SERVICE_GROUP,
    CONFIG,
    ENDPOINT_IP,
)

from ..service_names import INFLUXB

from ... import constants
from ...config import config
from ...logger import get_logger
from ...exceptions import ValidationError, BootstrapError

from ...utils import common
from ...utils.systemd import systemd
from ...utils.users import delete_service_user, delete_group
from ...utils.logrotate import set_logrotate, remove_logrotate
from ...utils.network import wait_for_port, check_http_response
from ...utils.files import copy_notice, remove_notice, remove_files, temp_copy

logger = get_logger(INFLUXB)

# Currently, cannot be changed due to webui not allowing to configure it.
INFLUXDB_ENDPOINT_PORT = 8086

HOME_DIR = join('/opt', INFLUXB)
LOG_DIR = join(constants.BASE_LOG_DIR, INFLUXB)
INIT_D_PATH = join('/etc', 'init.d', INFLUXB)
CONFIG_PATH = join(constants.COMPONENTS_DIR, INFLUXB, CONFIG)


def _configure_database(host, port):
    db_user = "root"
    db_pass = "root"
    db_name = "cloudify"

    logger.info('Creating InfluxDB Database...')

    # the below request is equivalent to running:
    # curl -S -s "http://localhost:8086/db?u=root&p=root" '-d "{\"name\": \"cloudify\"}"  # NOQA
    import urllib
    import urllib2
    import ast

    endpoint_for_list = 'http://{0}:{1}/db'.format(host, port)
    endpoint_for_creation = ('http://{0}:{1}/cluster/database_configs/'
                             '{2}'.format(host, port, db_name))
    params = urllib.urlencode(dict(u=db_user, p=db_pass))
    url_for_list = endpoint_for_list + '?' + params
    url_for_creation = endpoint_for_creation + '?' + params

    # check if db already exists
    db_list = eval(urllib2.urlopen(urllib2.Request(url_for_list)).read())
    try:
        assert not any(d.get('name') == db_name for d in db_list)
    except AssertionError:
        logger.info('Database {0} already exists!'.format(db_name))
        return

    try:
        tmp_path = temp_copy(join(CONFIG_PATH, 'retention.json'))

        with open(tmp_path) as policy_file:
            retention_policy = policy_file.read()
        logger.debug(
            'Using retention policy: \n{0}'.format(retention_policy))
        data = json.dumps(ast.literal_eval(retention_policy))
        logger.debug('Using retention policy: \n{0}'.format(data))
        content_length = len(data)
        request = urllib2.Request(url_for_creation, data, {
            'Content-Type': 'application/json',
            'Content-Length': content_length})
        logger.debug('Request is: {0}'.format(request))
        request_reader = urllib2.urlopen(request)
        response = request_reader.read()
        logger.debug('Response: {0}'.format(response))
        request_reader.close()
        common.remove('/tmp/retention.json')

    except Exception as ex:
        raise BootstrapError(
            'Failed to create: {0} ({1}).'.format(db_name, ex)
        )

    logger.debug('Verifying database created successfully...')
    db_list = eval(urllib2.urlopen(urllib2.Request(url_for_list)).read())
    try:
        assert any(d.get('name') == db_name for d in db_list)
    except AssertionError:
        raise ValidationError('Verification failed!')
    logger.info('Databased {0} successfully created'.format(db_name))


def _create_paths():
    common.mkdir(HOME_DIR)
    common.mkdir(LOG_DIR)

    _deploy_config_file()

    common.chown(INFLUXB, INFLUXB, HOME_DIR)
    common.chown(INFLUXB, INFLUXB, LOG_DIR)


def _deploy_config_file():
    logger.info('Deploying InfluxDB configuration...')
    common.copy(
        source=join(CONFIG_PATH, 'config.toml'),
        destination=join(HOME_DIR, 'shared', 'config.toml')
    )


def _configure_local_influxdb():
    config[INFLUXB][SERVICE_USER] = INFLUXB
    config[INFLUXB][SERVICE_GROUP] = INFLUXB

    _create_paths()
    copy_notice(INFLUXB)

    systemd.configure(INFLUXB)
    # Provided with InfluxDB's package. Will be removed if it exists.
    common.remove(INIT_D_PATH)
    set_logrotate(INFLUXB)


def _check_response():
    influxdb_endpoint_ip = config[INFLUXB][ENDPOINT_IP]
    influxdb_url = 'http://{0}:{1}'.format(
        influxdb_endpoint_ip,
        INFLUXDB_ENDPOINT_PORT
    )
    response = check_http_response(influxdb_url)

    # InfluxDB normally responds with a 404 on GET to /, but also allow other
    # non-server-error response codes to allow for that behaviour to change.
    if response.code >= 500:
        raise ValidationError('Could not validate InfluxDB')


def _start_and_verify_alive():
    logger.info('Starting InfluxDB Service...')
    systemd.restart(INFLUXB)
    systemd.verify_alive(INFLUXB)
    wait_for_port(INFLUXDB_ENDPOINT_PORT)
    _check_response()


def _configure():
    influxdb_endpoint_ip = config[INFLUXB][ENDPOINT_IP]
    is_internal = config[INFLUXB]['is_internal']
    if is_internal:
        _configure_local_influxdb()
        systemd.restart(INFLUXB)

    wait_for_port(INFLUXDB_ENDPOINT_PORT, influxdb_endpoint_ip)
    _configure_database(influxdb_endpoint_ip, INFLUXDB_ENDPOINT_PORT)

    if is_internal:
        _start_and_verify_alive()


def install():
    logger.notice('Installing InfluxDB...')
    _configure()
    logger.notice('InfluxDB successfully installed')


def configure():
    logger.notice('Configuring InfluxDB...')
    _configure()
    logger.notice('InfluxDB successfully configured')


def remove():
    logger.notice('Removing Influxdb...')
    remove_notice(INFLUXB)
    remove_logrotate(INFLUXB)
    systemd.remove(INFLUXB)
    remove_files([HOME_DIR, LOG_DIR, INIT_D_PATH])
    delete_service_user(INFLUXB)
    delete_group(INFLUXB)
    logger.notice('InfluxDB successfully removed')
