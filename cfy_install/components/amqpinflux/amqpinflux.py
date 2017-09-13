from os.path import join
from ..service_names import AMQPINFLUX

from ...config import config
from ...logger import get_logger

from ...utils import common
from ...utils.systemd import systemd
from ...utils.deploy import copy_notice
from ...utils.install import yum_install
from ...utils.users import create_service_user


logger = get_logger(AMQPINFLUX)

HOME_DIR = join('/opt', AMQPINFLUX)
AMQPINFLUX_VENV = join(HOME_DIR, 'env')


def _install():
    source_url = config[AMQPINFLUX]['sources']['amqpinflux_source_url']
    yum_install(source_url)


def _start_and_verify():
    logger.info('Starting AMQP-Influx Broker Service...')
    systemd.configure(AMQPINFLUX)
    systemd.restart(AMQPINFLUX)
    systemd.verify_alive(AMQPINFLUX)


def _configure():
    config[AMQPINFLUX]['service_user'] = AMQPINFLUX
    config[AMQPINFLUX]['service_group'] = AMQPINFLUX

    copy_notice(AMQPINFLUX)
    common.mkdir(HOME_DIR)
    create_service_user(AMQPINFLUX, AMQPINFLUX, HOME_DIR)
    common.chown(AMQPINFLUX, AMQPINFLUX, HOME_DIR)
    _start_and_verify()


def install():
    logger.notice('Installing AMQP-Influx...')
    _install()
    _configure()
    logger.notice('AMQP-Influx successfully installed')


def configure():
    logger.notice('Configuring AMQP-Influx...')
    _configure()
    logger.notice('AMQP-Influx successfully configured')
