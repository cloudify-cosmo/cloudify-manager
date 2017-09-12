from os.path import join
from zipfile import ZipFile
from tempfile import mkdtemp

from ..service_names import CONSUL

from ...config import config
from ...logger import get_logger

from ...utils import common
from ...utils.files import get_local_source_path


HOME_DIR = join('/opt', CONSUL)
CONSUL_BINARY = join(HOME_DIR, 'consul')
CONFIG_DIR = '/etc/consul.d'

logger = get_logger(CONSUL)


def _install_consul():
    logger.info('Installing consul...')

    common.mkdir(HOME_DIR)
    common.mkdir(CONFIG_DIR)

    consul_source_url = config[CONSUL]['sources']['consul_source_url']
    consul_package = get_local_source_path(consul_source_url)

    temp_dir = mkdtemp()
    try:
        with ZipFile(consul_package) as consul_archive:
            consul_archive.extractall(temp_dir)

        common.move(join(temp_dir, 'consul'), CONSUL_BINARY)
        common.chmod('+x', CONSUL_BINARY)
    finally:
        common.remove(temp_dir)


def _verify_consul():
    result = common.run([CONSUL_BINARY, 'version'])
    if 'Consul' not in result.aggr_stdout:
        raise StandardError('Could not verify consul installation')


def run():
    _install_consul()
    _verify_consul()
    logger.info('Consul installed successfully')
