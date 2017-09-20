from os.path import join
from zipfile import ZipFile
from tempfile import mkdtemp

from .. import SOURCES

from ..service_names import CONSUL

from ...config import config
from ...logger import get_logger
from ...utils import common
from ...utils.files import get_local_source_path, remove_files

HOME_DIR = join('/opt', CONSUL)
CONSUL_BINARY = join(HOME_DIR, CONSUL)
CONFIG_DIR = '/etc/consul.d'

logger = get_logger(CONSUL)


def _install():
    common.mkdir(HOME_DIR)
    common.mkdir(CONFIG_DIR)

    consul_source_url = config[CONSUL][SOURCES]['consul_source_url']
    consul_package = get_local_source_path(consul_source_url)

    temp_dir = mkdtemp()
    config.add_temp_path_to_clean(temp_dir)

    with ZipFile(consul_package) as consul_archive:
        consul_archive.extractall(temp_dir)

    common.move(join(temp_dir, CONSUL), CONSUL_BINARY)
    common.chmod('+x', CONSUL_BINARY)


def _verify():
    logger.info('Verifying consul is installed')
    result = common.run([CONSUL_BINARY, 'version'])
    if 'Consul' not in result.aggr_stdout:
        raise StandardError('Could not verify consul installation')


def install():
    logger.notice('Installing Consul...')
    _install()
    _verify()
    logger.notice('Consul successfully installed')


def configure():
    logger.notice('Configuring Consul...')
    _verify()
    logger.notice('Consul successfully configured')


def remove():
    logger.notice('Removing Cloudify Consul...')
    remove_files([HOME_DIR, CONFIG_DIR])
    logger.notice('Consul successfully removed')
