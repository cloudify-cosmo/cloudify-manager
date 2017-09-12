from ..service_names import PYTHON

from ...config import config
from ...logger import get_logger

from ...utils.common import sudo
from ...utils.deploy import copy_notice
from ...utils.install import yum_install

logger = get_logger(PYTHON)


def _install_python_requirements():
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


def run():
    logger.notice('Installing Python dependencies...')
    copy_notice(PYTHON)
    _install_python_requirements()
    _validate_pip_installed()
    logger.notice('Python dependencies installed successfully')
