from os.path import join

from ..service_names import SYNCTHING

from ...config import config
from ...logger import get_logger
from ...utils.common import mkdir, untar
from ...utils.files import get_local_source_path

logger = get_logger(SYNCTHING)

HOME_DIR = join('/opt', SYNCTHING)


def _install_syncthing():
    syncthing_source_url = config[SYNCTHING]['sources']['syncthing_source_url']
    syncthing_package = get_local_source_path(syncthing_source_url)
    mkdir(HOME_DIR)
    untar(syncthing_package, destination=HOME_DIR)


def install():
    logger.notice('Installing Syncthing...')
    _install_syncthing()
    logger.notice('Syncthing installed successfully')
