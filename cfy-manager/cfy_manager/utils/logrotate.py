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

from os.path import join, isfile, isdir

from .files import deploy
from .common import chown, mkdir, chmod, remove, move

from ..logger import get_logger
from ..constants import COMPONENTS_DIR

LOGROTATED_PATH = '/etc/logrotate.d'

logger = get_logger('logrotate')


def set_logrotate(service_name):
    """Deploys a logrotate config for a service.

    Note that this is not idempotent in the sense that if a logrotate
    file is already copied to /etc/logrotate.d, it will copy it again
    and override it. This is done as such so that if a service deploys
    its own logrotate configuration, we will override it.
    """
    logger.debug('Deploying logrotate config...')
    src = join(COMPONENTS_DIR, service_name, 'config', 'logrotate')
    dst = join(LOGROTATED_PATH, service_name)

    deploy(src, dst)
    chmod('644', dst)
    chown('root', 'root', dst)


def setup_logrotate():
    if not isfile('/etc/cron.hourly/logrotate'):
        logger.info('Deploying logrotate hourly cron job...')
        move('/etc/cron.daily/logrotate', '/etc/cron.hourly/logrotate')

    if not isdir(LOGROTATED_PATH):
        mkdir(LOGROTATED_PATH)
        chown('root', 'root', LOGROTATED_PATH)


def remove_logrotate(service_name):
    logger.debug('Removing logrotate config...')
    config_file_destination = join(LOGROTATED_PATH, service_name)
    remove(config_file_destination)
