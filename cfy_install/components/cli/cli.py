from .. import SOURCES, SECURITY

from ..service_names import CLI, MANAGER

from ...config import config
from ...logger import get_logger

from ...utils import common
from ...utils.install import yum_install, yum_remove


logger = get_logger(CLI)


def _install():
    source_url = config[CLI][SOURCES]['cli_source_url']
    yum_install(source_url)


def _configure():
    username = config[MANAGER][SECURITY]['admin_username']
    password = config[MANAGER][SECURITY]['admin_password']

    cmd = [
        'cfy', 'profiles', 'use', 'localhost', '-u', username,
        '-p', password, '-t', 'default_tenant'
    ]
    logger.info('Setting CLI for default user...')
    common.run(cmd)

    logger.info('Setting CLI for root user...')
    root_cmd = ['sudo', '-u', 'root'] + cmd
    common.run(root_cmd)


def install():
    logger.notice('Installing Cloudify CLI...')
    _install()
    _configure()
    logger.notice('Cloudify CLI successfully installed')


def configure():
    logger.notice('Configuring Cloudify CLI...')
    _configure()
    logger.notice('Cloudify CLI successfully configured')


def remove():
    logger.notice('Removing Cloudify CLI...')
    yum_remove('cloudify')
    logger.notice('Cloudify CLI successfully removed')
