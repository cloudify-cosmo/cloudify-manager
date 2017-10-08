from os.path import join

from .. import (
    SOURCES,
    SERVICE_USER,
    SERVICE_GROUP,
    HOME_DIR_KEY
)

from ..service_names import STAGE, MANAGER

from ...config import config
from ...logger import get_logger
from ...exceptions import FileError
from ...constants import BASE_LOG_DIR, BASE_RESOURCES_PATH, CLOUDIFY_GROUP

from ...utils import common, files
from ...utils.systemd import systemd
from ...utils.network import wait_for_port
from ...utils.users import (create_service_user,
                            delete_service_user,
                            delete_group)
from ...utils.sudoers import deploy_sudo_command_script
from ...utils.logrotate import set_logrotate, remove_logrotate

logger = get_logger(STAGE)

STAGE_USER = '{0}_user'.format(STAGE)
STAGE_GROUP = '{0}_group'.format(STAGE)

HOME_DIR = join('/opt', 'cloudify-{0}'.format(STAGE))
NODEJS_DIR = join('/opt', 'nodejs')
LOG_DIR = join(BASE_LOG_DIR, STAGE)


def _create_paths():
    common.mkdir(NODEJS_DIR)
    common.mkdir(HOME_DIR)
    common.mkdir(LOG_DIR)


def _set_community_mode():
    premium_edition = config[MANAGER]['premium_edition']
    community_mode = '' if premium_edition else '-mode community'

    # This is used in the stage systemd service file
    config[STAGE]['community_mode'] = community_mode


def _install():
    stage_source_url = config[STAGE][SOURCES]['stage_source_url']
    try:
        stage_tar = files.get_local_source_path(stage_source_url)
    except FileError:
        logger.info('Stage package not found in manager resources package')
        logger.notice('Stage will not be installed.')
        config[STAGE]['skip_installation'] = True
        return

    _create_paths()

    logger.info('Extracting Stage package...')
    common.untar(stage_tar, HOME_DIR)


def _create_user_and_set_permissions():
    create_service_user(STAGE_USER, STAGE_GROUP, HOME_DIR)

    logger.debug('Fixing permissions...')
    common.chown(STAGE_USER, STAGE_GROUP, HOME_DIR)
    common.chown(STAGE_USER, STAGE_GROUP, NODEJS_DIR)
    common.chown(STAGE_USER, STAGE_GROUP, LOG_DIR)


def _install_nodejs():
    logger.info('Installing NodeJS...')
    nodejs_source_url = config[STAGE][SOURCES]['nodejs_source_url']
    nodejs = files.get_local_source_path(nodejs_source_url)
    common.untar(nodejs, NODEJS_DIR)


def _deploy_restore_snapshot_script():
    # Used in the script template
    config[STAGE][HOME_DIR_KEY] = HOME_DIR
    script_name = 'restore-snapshot.py'
    deploy_sudo_command_script(
        script_name,
        'Restore stage directories from a snapshot path',
        component=STAGE,
        allow_as=STAGE_USER
    )
    common.chmod('a+rx', join(BASE_RESOURCES_PATH, STAGE, script_name))
    common.sudo(['usermod', '-aG', CLOUDIFY_GROUP, STAGE_USER])


def _run_db_migrate():
    backend_dir = join(HOME_DIR, 'backend')
    npm_path = join(NODEJS_DIR, 'bin', 'npm')
    common.run(
        'cd {0}; {1} run db-migrate'.format(backend_dir, npm_path),
        shell=True
    )


def _start_and_validate_stage():
    _set_community_mode()
    # Used in the service template
    config[STAGE][SERVICE_USER] = STAGE_USER
    config[STAGE][SERVICE_GROUP] = STAGE_GROUP
    systemd.configure(STAGE)

    logger.info('Starting Stage service...')
    systemd.restart(STAGE)
    wait_for_port(8088)


def _configure():
    files.copy_notice(STAGE)
    set_logrotate(STAGE)
    _create_user_and_set_permissions()
    _install_nodejs()
    _deploy_restore_snapshot_script()
    _run_db_migrate()
    _start_and_validate_stage()


def install():
    logger.notice('Installing Stage...')
    _install()
    if config[STAGE]['skip_installation']:
        return
    _configure()
    logger.notice('Stage successfully installed')


def configure():
    logger.notice('Configuring Stage...')
    _configure()
    logger.notice('Stage successfully configured')


def remove():
    logger.notice('Removing Stage...')
    files.remove_notice(STAGE)
    remove_logrotate(STAGE)
    systemd.remove(STAGE)
    delete_service_user(STAGE_USER)
    delete_group(STAGE_GROUP)
    files.remove_files([HOME_DIR, NODEJS_DIR, LOG_DIR])
    logger.notice('Stage successfully removed')
