#!/usr/bin/env python
from time import time
from pprint import pformat

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
from .components.validations import validate_machine

from .config import config
from .utils.files import remove_temp_files
from .logger import get_logger, set_logger_level

logger = get_logger('Bootstrap')

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
    riemann,
    java,
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


def _init(bootstrap=True):
    if bootstrap:
        config.load_bootstrap_config()
    else:
        config.load_teardown_config()

    set_logger_level(config['log_level'].upper())


def install():
    _init()

    logger.info('Installing Cloudify Manager')
    validate_machine()
    set_globals()

    for component in COMPONENTS:
        component.install()

    logger.debug(pformat(config))
    config.dump_config()
    remove_temp_files()
    logger.info('Cloudify Manager installation complete!')
    _print_time()


def configure():
    _init()

    logger.info('Configuring Cloudify Manager')
    set_globals()

    for component in COMPONENTS:
        component.configure()

    remove_temp_files()
    logger.info('Cloudify Manager configuration complete!')
    _print_time()


def remove():
    _init(bootstrap=False)

    logger.info('Removing Cloudify Manager')
    set_globals()

    for component in COMPONENTS:
        component.remove()

    logger.info('Cloudify Manager uninstallation complete!')
    _print_time()


if __name__ == '__main__':
    install()
