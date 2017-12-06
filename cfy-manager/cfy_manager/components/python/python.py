#########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

from .. import SOURCES

from ..service_names import PYTHON

from ...config import config
from ...logger import get_logger
from ...exceptions import ValidationError

from ...utils.common import sudo
from ...utils.install import yum_install, yum_remove
from ...utils.files import copy_notice, remove_notice

logger = get_logger(PYTHON)


def _install():
    yum_install(config[PYTHON][SOURCES]['pip_source_url'])

    if config[PYTHON]['install_python_compilers']:
        logger.info('Installing Compilers...')
        yum_install('python-devel')
        yum_install('gcc')
        yum_install('gcc-c++')


def _validate_pip_installed():
    logger.info('Validating pip installation...')
    pip_result = sudo(['pip'], ignore_failures=True)
    if pip_result.returncode != 0:
        raise ValidationError(
            'Python runtime installation error: pip was not installed'
        )


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
