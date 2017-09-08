from os.path import join, isfile

from ... import constants
from ...logger import get_logger
from ...config import config

from ...utils.yum import yum_install
from ...utils.deploy import copy_notice
from ...utils.common import move, mkdir, sudo


SERVICE_NAME = 'java'
logger = get_logger(SERVICE_NAME)
HOME_DIR = join('/opt', SERVICE_NAME)
LOG_DIR = join(constants.BASE_LOG_DIR, SERVICE_NAME)


def _install_java():
    logger.info('Installing Java...')
    java_source_url = config[SERVICE_NAME]['sources']['java_source_url']
    yum_install(java_source_url)

    mkdir(LOG_DIR)

    # Java install log is dropped in /var/log.
    # Move it to live with the rest of the cloudify logs
    java_install_log = '/var/log/java_install.log'
    if isfile(java_install_log):
        move(java_install_log, LOG_DIR)


def _validate_java_installed():
    java_result = sudo(['java', '-version'], ignore_failures=True)
    if java_result.returncode != 0:
        raise StandardError('Java runtime error: java was not installed')


def run():
    copy_notice(SERVICE_NAME)
    _install_java()
    _validate_java_installed()
