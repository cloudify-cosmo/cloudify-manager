from ..service_names import PYTHON

from ...config import config
from ...logger import get_logger

from ...utils.common import sudo
from ...utils.install import yum_install, yum_remove
from ...utils.files import copy_notice, remove_notice

logger = get_logger(PYTHON)


def _install():
    yum_install(config[PYTHON]['sources']['pip_source_url'])

    if config[PYTHON]['install_python_compilers']:
        logger.info('Installing Compilers...')
        yum_install('python-devel')
        yum_install('gcc')
        yum_install('gcc-c++')


def _validate_pip_installed():
    logger.info('Validating pip installation...')
    pip_result = sudo(['pip'], ignore_failures=True)
    if pip_result.returncode != 0:
        raise StandardError('Python runtime installation error: '
                            'pip was not installed')


def _configure():
    copy_notice(PYTHON)
    _validate_pip_installed()


def install():
    logger.notice('Installing Python dependencies...')
    _install()
    _configure()
    logger.notice('Python dependencies successfully installed')


def configure():
    logger.notice('Configuring Python dependencies...')
    _configure()
    logger.notice('Python dependencies successfully configured')


def remove():
    remove_notice(PYTHON)
    if config[PYTHON]['remove_on_teardown']:
        logger.notice('Removing Python dependencies...')
        yum_remove('python-pip')
        if config[PYTHON]['install_python_compilers']:
            yum_remove('python-devel')
            yum_remove('gcc')
            yum_remove('gcc-c++')
        logger.notice('Python dependencies successfully removed')
