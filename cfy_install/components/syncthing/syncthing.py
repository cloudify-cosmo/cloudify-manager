from os.path import join, exists

from .. import SOURCES

from ..service_names import SYNCTHING

from ...config import config
from ...logger import get_logger

from ...utils.common import mkdir, untar, sudo
from ...utils.files import get_local_source_path, remove_files

logger = get_logger(SYNCTHING)

HOME_DIR = join('/opt', SYNCTHING)
CLUSTER_DELETE_SCRIPT = '/opt/cloudify/delete_cluster.py'


def _install():
    syncthing_source_url = config[SYNCTHING][SOURCES]['syncthing_source_url']
    syncthing_package = get_local_source_path(syncthing_source_url)
    mkdir(HOME_DIR)
    untar(syncthing_package, destination=HOME_DIR)


def install():
    logger.notice('Installing Syncthing...')
    _install()
    logger.notice('Syncthing successfully installed')


def configure():
    pass


def remove():
    logger.notice('Removing Syncthing...')
    if exists(CLUSTER_DELETE_SCRIPT):
        sudo([
            '/usr/bin/env', 'python', CLUSTER_DELETE_SCRIPT,
            '--component', SYNCTHING
        ])
    remove_files([HOME_DIR])
    logger.notice('Syncthing successfully removed')
