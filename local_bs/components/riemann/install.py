from os.path import join

from ..service_names import RIEMANN

from ... import constants
from ...config import config
from ...logger import get_logger

from ...utils import common
from ...utils.systemd import systemd
from ...utils.install import yum_install
from ...utils.network import wait_for_port
from ...utils.logrotate import set_logrotate
from ...utils.users import create_service_user
from ...utils.deploy import copy_notice, deploy
from ...utils.files import get_local_source_path

logger = get_logger(RIEMANN)

HOME_DIR = join('/opt', RIEMANN)
CONFIG_PATH = join('/etc', RIEMANN)
LOG_DIR = join(constants.BASE_LOG_DIR, RIEMANN)
LANGOHR_HOME = '/opt/lib'


def _create_paths():
    common.mkdir(HOME_DIR)
    common.mkdir(LOG_DIR)
    common.mkdir(LANGOHR_HOME)
    common.mkdir(CONFIG_PATH)
    common.mkdir('{0}/conf.d'.format(CONFIG_PATH))

    # Need to allow access to mgmtworker (thus cfyuser)
    common.chown(RIEMANN, constants.CLOUDIFY_GROUP, HOME_DIR)
    common.chown(RIEMANN, RIEMANN, LOG_DIR)


def _install_riemann():
    sources = config[RIEMANN]['sources']

    tmp_langohr_jar_path = get_local_source_path(sources['langohr_source_url'])
    langohr_jar_path = join(LANGOHR_HOME, 'langohr.jar')
    common.copy(tmp_langohr_jar_path, langohr_jar_path)
    common.chmod('644', langohr_jar_path)

    yum_install(sources['daemonize_source_url'])
    yum_install(sources['riemann_source_url'])


def _configure_riemann():
    logger.info('Getting manager repo archive...')
    cloudify_resources_url = \
        config[RIEMANN]['sources']['cloudify_resources_url']
    local_tar_path = get_local_source_path(cloudify_resources_url)
    manager_dir = common.untar(local_tar_path, unique_tmp_dir=True)

    logger.info('Deploying Riemann manager.config...')
    config_src_path = join(
        manager_dir, 'plugins', 'riemann-controller',
        'riemann_controller', 'resources', 'manager.config'
    )
    common.move(config_src_path, join(CONFIG_PATH, 'conf.d', 'manager.config'))
    common.remove(manager_dir)


def _deploy_riemann_config():
    logger.info('Deploying Riemann conf...')
    deploy(
        src=join(constants.COMPONENTS_DIR, RIEMANN, 'config', 'main.clj'),
        dst=join(CONFIG_PATH, 'main.clj')
    )
    common.chown(RIEMANN, RIEMANN, CONFIG_PATH)


def _start_and_verify_service():
    logger.info('Starting Riemann Service...')
    systemd.configure(RIEMANN)
    systemd.restart(RIEMANN)
    systemd.verify_alive(RIEMANN)
    wait_for_port(5555)


def _create_user():
    create_service_user(RIEMANN, RIEMANN, home=constants.CLOUDIFY_HOME_DIR)

    # Used in the service template
    config[RIEMANN]['service_user'] = RIEMANN
    config[RIEMANN]['service_group'] = RIEMANN


def run():
    logger.notice('Installing Riemann...')
    copy_notice(RIEMANN)
    _create_user()
    _create_paths()
    set_logrotate(RIEMANN)
    _install_riemann()
    _configure_riemann()
    _deploy_riemann_config()
    _start_and_verify_service()
    logger.notice('Riemann installed successfully')
