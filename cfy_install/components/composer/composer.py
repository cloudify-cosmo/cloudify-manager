from os.path import join, dirname

from ..service_names import COMPOSER

from ...utils import common
from ...config import config
from ...logger import get_logger
from ...utils.systemd import systemd
from ...utils.deploy import copy_notice
from ...utils.network import wait_for_port
from ...utils.logrotate import set_logrotate
from ...utils.users import create_service_user
from ...utils.files import get_local_source_path
from ...constants import BASE_LOG_DIR, CLOUDIFY_USER

logger = get_logger(COMPOSER)

HOME_DIR = join('/opt', 'cloudify-{0}'.format(COMPOSER))
CONF_DIR = join(HOME_DIR, 'backend', 'conf')
NODEJS_DIR = join('/opt', 'nodejs')
LOG_DIR = join(BASE_LOG_DIR, COMPOSER)

COMPOSER_USER = '{0}_user'.format(COMPOSER)
COMPOSER_GROUP = '{0}_group'.format(COMPOSER)


def _create_paths():
    common.mkdir(NODEJS_DIR)
    common.mkdir(HOME_DIR)
    common.mkdir(LOG_DIR)


def _install():
    composer_source_url = config[COMPOSER]['sources']['composer_source_url']
    try:
        composer_tar = get_local_source_path(composer_source_url)
    except StandardError:
        logger.info('Composer package not found in manager resources package')
        logger.notice('Composer will not be installed.')
        config[COMPOSER]['skip_installation'] = True
        return

    _create_paths()

    logger.info('Installing Cloudify Composer...')
    common.untar(composer_tar, HOME_DIR)


def _start_and_validate_composer():
    # Used in the service template
    config[COMPOSER]['service_user'] = COMPOSER_USER
    config[COMPOSER]['service_group'] = COMPOSER_GROUP
    systemd.configure(COMPOSER)

    logger.info('Starting Composer service...')
    systemd.restart(COMPOSER)
    wait_for_port(3000)


def _run_db_migrate():
    npm_path = join(NODEJS_DIR, 'bin', 'npm')
    common.run(
        'cd {}; {} run db-migrate'.format(HOME_DIR, npm_path),
        shell=True
    )


def _create_user_and_set_permissions():
    create_service_user(COMPOSER_USER, COMPOSER_GROUP, HOME_DIR)
    # adding cfyuser to the composer group so that its files are r/w for
    # replication and snapshots
    common.sudo(['usermod', '-aG', COMPOSER_GROUP, CLOUDIFY_USER])

    logger.info('Fixing permissions...')
    common.chown(COMPOSER_USER, COMPOSER_GROUP, HOME_DIR)
    common.chown(COMPOSER_USER, COMPOSER_GROUP, LOG_DIR)

    common.chmod('g+w', CONF_DIR)
    common.chmod('g+w', dirname(CONF_DIR))


def _configure():
    copy_notice(COMPOSER)
    set_logrotate(COMPOSER)
    _create_user_and_set_permissions()
    _run_db_migrate()
    _start_and_validate_composer()


def install():
    logger.notice('Installing Cloudify Composer...')
    _install()
    if config[COMPOSER]['skip_installation']:
        return
    _configure()
    logger.notice('Cloudify Composer installed successfully')


def configure():
    logger.info('Configuring Cloudify Composer...')
    _configure()
    logger.info('Cloudify Composer successfully configured')

