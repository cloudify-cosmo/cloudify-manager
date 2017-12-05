#!/usr/bin/env python
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

import sys
import argh
from time import time
from traceback import format_exception

from .components import cli
from .components import java
from .components import nginx
from .components import stage
from .components import sanity
from .components import consul
from .components import python
from .components import manager
from .components import riemann
from .components import composer
from .components import logstash
from .components import rabbitmq
from .components import influxdb
from .components import syncthing
from .components import amqpinflux
from .components import mgmtworker
from .components import postgresql
from .components import restservice
from .components import manager_ip_setter

from .components.globals import set_globals
from .components.validations import validate

from .components.service_names import MANAGER
from .components import SECURITY, PRIVATE_IP, PUBLIC_IP, ADMIN_PASSWORD

from .config import config
from .exceptions import BootstrapError
from .logger import get_logger, setup_console_logger

from .utils.files import remove_temp_files
from .utils.certificates import (
    create_internal_certs,
    create_external_certs
)

logger = get_logger('Main')

COMPONENTS = [
    manager,
    manager_ip_setter,
    nginx,
    python,
    postgresql,
    rabbitmq,
    restservice,
    influxdb,
    amqpinflux,
    java,
    riemann,
    consul,
    syncthing,
    stage,
    composer,
    logstash,
    mgmtworker,
    cli,
    sanity
]

START_TIME = time()


def _print_time():
    running_time = time() - START_TIME
    m, s = divmod(running_time, 60)
    logger.notice(
        'Finished in {0} minutes and {1} seconds'.format(int(m), int(s))
    )


def _exception_handler(type_, value, traceback):
    remove_temp_files()

    error = type_.__name__
    if str(value):
        error = '{0}: {1}'.format(error, str(value))
    logger.error(error)
    debug_traceback = ''.join(format_exception(type_, value, traceback))
    logger.debug(debug_traceback)


sys.excepthook = _exception_handler


def _load_config_and_logger(verbose=False,
                            private_ip=None,
                            public_ip=None,
                            admin_password=None):
    setup_console_logger(verbose)
    config.load_config()
    manager_config = config[MANAGER]
    if private_ip:
        manager_config[PRIVATE_IP] = private_ip
    if public_ip:
        manager_config[PUBLIC_IP] = public_ip
    if admin_password:
        manager_config[SECURITY][ADMIN_PASSWORD] = admin_password


def _print_finish_message():
    manager_config = config[MANAGER]
    logger.notice('Manager is up at {0}'.format(manager_config[PUBLIC_IP]))
    logger.notice('#' * 50)
    logger.notice('Manager password is {0}'.format(
        manager_config[SECURITY][ADMIN_PASSWORD]))
    logger.notice('#' * 50)


def install(verbose=False,
            private_ip=None,
            public_ip=None,
            admin_password=None):
    """ Install Cloudify Manager """

    _load_config_and_logger(verbose, private_ip, public_ip, admin_password)

    logger.notice('Installing Cloudify Manager...')
    validate()
    set_globals()

    for component in COMPONENTS:
        component.install()

    remove_temp_files()
    logger.notice('Cloudify Manager successfully installed!')
    _print_finish_message()
    _print_time()


def configure(verbose=False,
              private_ip=None,
              public_ip=None,
              admin_password=None):
    """ Configure Cloudify Manager """

    _load_config_and_logger(verbose, private_ip, public_ip, admin_password)

    logger.notice('Configuring Cloudify Manager...')
    validate(skip_validations=True)
    set_globals()

    for component in COMPONENTS:
        component.configure()

    remove_temp_files()
    logger.notice('Cloudify Manager successfully configured!')
    _print_finish_message()
    _print_time()


def remove(verbose=False, force=False):
    """ Uninstall Cloudify Manager """

    _load_config_and_logger(verbose)
    if not force:
        raise BootstrapError(
            'The --force flag must be passed to `cfy_manager remove`'
        )

    logger.notice('Removing Cloudify Manager...')

    for component in COMPONENTS:
        component.remove()

    logger.notice('Cloudify Manager successfully removed!')
    _print_time()


if __name__ == '__main__':
    argh.dispatch_commands([
        install,
        configure,
        remove,
        create_internal_certs,
        create_external_certs
    ])
