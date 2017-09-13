from time import sleep
from os.path import join, dirname

from ..service_names import MGMTWORKER

from ... import constants as const
from ...config import config
from ...logger import get_logger

from ...utils import common
from ...utils.systemd import systemd
from ...utils.install import yum_install
from ...utils.logrotate import set_logrotate
from ...utils.deploy import copy_notice, deploy


HOME_DIR = '/opt/mgmtworker'
MGMTWORKER_VENV = join(HOME_DIR, 'env')
LOG_DIR = join(const.BASE_LOG_DIR, MGMTWORKER)
CONFIG_PATH = join(const.COMPONENTS_DIR, MGMTWORKER, 'config')

logger = get_logger(MGMTWORKER)


def _install():
    logger.info('Installing Management Worker...')
    source_url = config[MGMTWORKER]['sources']['mgmtworker_source_url']
    yum_install(source_url)

    # TODO: Take care of this
    # Prepare riemann dir. We will change the owner to riemann later, but the
    # management worker will still need access to it
    # common.mkdir('/opt/riemann')
    # utils.chown(CLOUDIFY_USER, CLOUDIFY_GROUP, riemann_dir)
    # utils.chmod('770', riemann_dir)


def _create_paths():
    common.mkdir(HOME_DIR)
    common.mkdir(join(HOME_DIR, 'config'))
    common.mkdir(join(HOME_DIR, 'work'))
    common.mkdir(LOG_DIR)

    common.chown(const.CLOUDIFY_USER, const.CLOUDIFY_GROUP, LOG_DIR)
    common.chown(const.CLOUDIFY_USER, const.CLOUDIFY_GROUP, HOME_DIR)

    config[MGMTWORKER]['home_dir'] = HOME_DIR
    config[MGMTWORKER]['log_dir'] = LOG_DIR


def _deploy_mgmtworker_config():
    logger.info('Configuring Management worker...')

    config[MGMTWORKER]['service_user'] = const.CLOUDIFY_USER
    config[MGMTWORKER]['service_group'] = const.CLOUDIFY_GROUP

    celery_work_dir = join(HOME_DIR, 'work')
    broker_config_dst = join(celery_work_dir, 'broker_config.json')
    deploy(
        src=join(CONFIG_PATH, 'broker_config.json'),
        dst=broker_config_dst
    )

    # The config contains credentials, do not let the world read it
    common.chmod('440', broker_config_dst)
    common.chown(const.CLOUDIFY_USER, const.CLOUDIFY_GROUP, broker_config_dst)


def _configure_logging():
    logger.info('Configuring Management worker logging...')
    logging_config_dir = '/etc/cloudify'
    common.mkdir(logging_config_dir)

    common.copy(
        source=join(CONFIG_PATH, 'logging.conf'),
        destination=join(logging_config_dir, 'logging.conf')
    )


def _prepare_snapshot_permissions():
    # TODO: See if all of this is necessary
    common.sudo(['chgrp', const.CLOUDIFY_GROUP, '/opt/manager'])
    common.sudo(['chmod', 'g+rw', '/opt/manager'])
    common.sudo(
        ['chgrp', '-R', const.CLOUDIFY_GROUP, const.SSL_CERTS_TARGET_DIR]
    )
    common.sudo(
        ['chgrp', const.CLOUDIFY_GROUP, dirname(const.SSL_CERTS_TARGET_DIR)]
    )
    common.sudo(['chmod', '-R', 'g+rw', const.SSL_CERTS_TARGET_DIR])
    common.sudo(['chmod', 'g+rw', dirname(const.SSL_CERTS_TARGET_DIR)])


def _check_worker_running():
    """Use `celery status` to check if the worker is running."""
    work_dir = join(HOME_DIR, 'work')
    celery_path = join(HOME_DIR, 'env', 'bin', 'celery')
    celery_status_cmd = [
        'CELERY_WORK_DIR={0}'.format(work_dir),
        celery_path,
        '--config=cloudify.broker_config',
        'status'
    ]
    logger.info('Verifying celery is operational...')
    for _ in range(3):
        result = common.sudo(celery_status_cmd, ignore_failures=True)
        if result.returncode == 0:
            logger.info('Celery is up')
            return
        sleep(1)
    raise StandardError('Could not validate that celery is running')


def _start_and_verify_mgmtworker():
    systemd.restart(MGMTWORKER)
    systemd.verify_alive(MGMTWORKER)
    _check_worker_running()


def _configure():
    copy_notice(MGMTWORKER)
    _create_paths()
    _deploy_mgmtworker_config()
    systemd.configure(MGMTWORKER)
    set_logrotate(MGMTWORKER)
    _configure_logging()
    _prepare_snapshot_permissions()
    _start_and_verify_mgmtworker()


def install():
    logger.notice('Installing Management Worker...')
    _install()
    _configure()
    logger.notice('Management Worker installed successfully')


def configure():
    logger.notice('Configuring Management Worker...')
    _configure()
    logger.notice('Management Worker configured successfully')
