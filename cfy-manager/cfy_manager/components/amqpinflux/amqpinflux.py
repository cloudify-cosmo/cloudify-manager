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

from os.path import join

from .. import SERVICE_USER, SERVICE_GROUP

from ..service_names import AMQPINFLUX

from ...config import config
from ...logger import get_logger

from ...utils import common
from ...utils.systemd import systemd
from ...utils.files import remove_files, remove_notice, copy_notice
from ...utils.users import (create_service_user,
                            delete_service_user,
                            delete_group)


logger = get_logger(AMQPINFLUX)

HOME_DIR = join('/opt', AMQPINFLUX)
AMQPINFLUX_VENV = join(HOME_DIR, 'env')


def _start_and_verify():
    logger.info('Starting AMQP-Influx Broker Service...')
    systemd.configure(AMQPINFLUX)
    systemd.restart(AMQPINFLUX)
    systemd.verify_alive(AMQPINFLUX)


def _configure():
    config[AMQPINFLUX][SERVICE_USER] = AMQPINFLUX
    config[AMQPINFLUX][SERVICE_GROUP] = AMQPINFLUX

    copy_notice(AMQPINFLUX)
    common.mkdir(HOME_DIR)
    create_service_user(AMQPINFLUX, AMQPINFLUX, HOME_DIR)
    common.chown(AMQPINFLUX, AMQPINFLUX, HOME_DIR)
    _start_and_verify()


def install():
    logger.notice('Installing AMQP-Influx...')
    _configure()
    logger.notice('AMQP-Influx successfully installed')


def configure():
    logger.notice('Configuring AMQP-Influx...')
    _configure()
    logger.notice('AMQP-Influx successfully configured')


def remove():
    logger.notice('Removing AMQP-Influx...')
    systemd.remove(AMQPINFLUX)
    remove_notice(AMQPINFLUX)
    remove_files([HOME_DIR])
    delete_service_user(AMQPINFLUX)
    delete_group(AMQPINFLUX)
    logger.notice('AMQP-Influx successfully removed')
