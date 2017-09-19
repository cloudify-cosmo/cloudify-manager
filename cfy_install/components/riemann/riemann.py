from os.path import join

from ..service_names import RIEMANN

from ... import constants
from ...config import config
from ...logger import get_logger

from ...utils import common, files
from ...utils.systemd import systemd
from ...utils.install import yum_install, yum_remove
from ...utils.logrotate import set_logrotate, remove_logrotate
from ...utils.users import (create_service_user,
                            delete_service_user,
                            delete_group)

logger = get_logger(RIEMANN)

HOME_DIR = join('/opt', RIEMANN)
CONFIG_PATH = join('/etc', RIEMANN)
LOG_DIR = join(constants.BASE_LOG_DIR, RIEMANN)
LANGOHR_HOME = '/opt/lib'
LANGOHR_JAR_PATH = join(LANGOHR_HOME, 'langohr.jar')


def _create_paths():
    common.mkdir(HOME_DIR)
    common.mkdir(LOG_DIR)
    common.mkdir(LANGOHR_HOME)
    common.mkdir(CONFIG_PATH)
    common.mkdir('{0}/conf.d'.format(CONFIG_PATH))

    # Need to allow access to mgmtworker (thus cfyuser)
    common.chown(RIEMANN, constants.CLOUDIFY_GROUP, HOME_DIR)
    common.chown(RIEMANN, RIEMANN, LOG_DIR)


def _install():
    sources = config[RIEMANN]['sources']

    langohr_resource_path = \
        files.get_local_source_path(sources['langohr_source_url'])
    common.copy(langohr_resource_path, LANGOHR_JAR_PATH)
    common.chmod('644', LANGOHR_JAR_PATH)

    yum_install(sources['daemonize_source_url'])
    yum_install(sources['riemann_source_url'])


def _configure_riemann():
    logger.debug('Getting manager repo archive...')
    cloudify_resources_url = \
        config[RIEMANN]['sources']['cloudify_resources_url']
    local_tar_path = files.get_local_source_path(cloudify_resources_url)
    manager_dir = common.untar(local_tar_path, unique_tmp_dir=True)

    logger.debug('Deploying Riemann manager.config...')
    config_src_path = join(
        manager_dir, 'plugins', 'riemann-controller',
        'riemann_controller', 'resources', 'manager.config'
    )
    common.move(config_src_path, join(CONFIG_PATH, 'conf.d', 'manager.config'))


def _deploy_riemann_config():
    logger.info('Deploying Riemann config...')
    files.deploy(
        src=join(constants.COMPONENTS_DIR, RIEMANN, 'config', 'main.clj'),
        dst=join(CONFIG_PATH, 'main.clj')
    )
    common.chown(RIEMANN, RIEMANN, CONFIG_PATH)


def _start_and_verify_service():
    logger.info('Starting Riemann service...')
    systemd.configure(RIEMANN)
    systemd.restart(RIEMANN)
    systemd.verify_alive(RIEMANN)


def _create_user():
    create_service_user(RIEMANN, RIEMANN, home=constants.CLOUDIFY_HOME_DIR)

    # Used in the service template
    config[RIEMANN]['service_user'] = RIEMANN
    config[RIEMANN]['service_group'] = RIEMANN


def _configure():
    files.copy_notice(RIEMANN)
    _create_user()
    _create_paths()
    set_logrotate(RIEMANN)
    _configure_riemann()
    _deploy_riemann_config()
    _start_and_verify_service()


def install():
    logger.notice('Installing Riemann...')
    _install()
    _configure()
    logger.notice('Riemann successfully installed')


def configure():
    logger.notice('Configuring Riemann...')
    _configure()
    logger.notice('Riemann successfully configured')


def remove():
    logger.notice('Removing Riemann...')
    files.remove_notice(RIEMANN)
    systemd.remove(RIEMANN)
    remove_logrotate(RIEMANN)
    delete_service_user(RIEMANN)
    delete_group(RIEMANN)
    files.remove_files([
        HOME_DIR,
        CONFIG_PATH,
        LOG_DIR,
        LANGOHR_JAR_PATH,
    ])
    yum_remove(RIEMANN)
    logger.notice('Riemann successfully removed')
