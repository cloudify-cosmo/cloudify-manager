from os.path import join

from ..service_names import STAGE

from ...utils import common
from ...config import config
from ...logger import get_logger
from ...utils.systemd import systemd
from ...utils.deploy import copy_notice
from ...utils.network import wait_for_port
from ...utils.logrotate import set_logrotate
from ...utils.users import create_service_user
from ...utils.files import get_local_source_path
from ...utils.sudoers import deploy_sudo_command_script
from ...constants import BASE_LOG_DIR, BASE_RESOURCES_PATH

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


def _install_stage():
    stage_source_url = config[STAGE]['sources']['stage_source_url']
    try:
        stage_tar = get_local_source_path(stage_source_url)
    except StandardError:
        logger.info('Stage package not found in manager resources package')
        logger.notice('Stage will not be installed.')
        config[STAGE]['skip_installation'] = True
        return

    _create_paths()

    logger.info('Installing Cloudify Stage (UI)...')
    common.untar(stage_tar, HOME_DIR)


def _create_user_and_set_permissions():
    create_service_user(STAGE_USER, STAGE_GROUP, HOME_DIR)

    logger.info('Fixing permissions...')
    common.chown(STAGE_USER, STAGE_GROUP, HOME_DIR)
    common.chown(STAGE_USER, STAGE_GROUP, NODEJS_DIR)
    common.chown(STAGE_USER, STAGE_GROUP, LOG_DIR)


def _install_nodejs():
    logger.info('Installing NodeJS...')
    nodejs_source_url = config[STAGE]['sources']['nodejs_source_url']
    nodejs = get_local_source_path(nodejs_source_url)
    common.untar(nodejs, NODEJS_DIR)


def _deploy_restore_snapshot_script():
    # Used in the script template
    config[STAGE]['home_dir'] = HOME_DIR
    script_name = 'restore-snapshot.py'
    deploy_sudo_command_script(
        script_name,
        'Restore stage directories from a snapshot path',
        component=STAGE,
        allow_as=STAGE_USER
    )
    common.chmod('a+rx', join(BASE_RESOURCES_PATH, STAGE, script_name))


def _run_db_migrate():
    backend_dir = join(HOME_DIR, 'backend')
    npm_path = join(NODEJS_DIR, 'bin', 'npm')
    common.run(
        'cd {0}; {1} run db-migrate'.format(backend_dir, npm_path),
        shell=True
    )


def _start_and_validate_stage():
    # Used in the service template
    config[STAGE]['service_user'] = STAGE_USER
    config[STAGE]['service_group'] = STAGE_GROUP
    systemd.configure(STAGE)

    logger.info('Starting Stage service...')
    systemd.restart(STAGE)
    wait_for_port(8088)


def run():
    logger.notice('Installing Stage...')
    _install_stage()
    if config[STAGE]['skip_installation']:
        return
    copy_notice(STAGE)
    set_logrotate(STAGE)
    _create_user_and_set_permissions()
    _install_nodejs()
    _deploy_restore_snapshot_script()
    _run_db_migrate()
    _start_and_validate_stage()
    logger.notice('Stage installed successfully')
