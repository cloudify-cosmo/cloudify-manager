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

from os.path import join

from .. import CONFIG, SERVICE_USER, SERVICE_GROUP

from ..service_names import RIEMANN

from ... import constants
from ...config import config
from ...logger import get_logger

from ...utils import common, files
from ...utils.systemd import systemd
from ...utils.logrotate import set_logrotate, remove_logrotate
from ...utils.users import (create_service_user,
                            delete_service_user,
                            delete_group)

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
    common.chmod('770', HOME_DIR)
    common.chown(RIEMANN, RIEMANN, LOG_DIR)


def _deploy_riemann_config():
    logger.info('Deploying Riemann config...')
    files.deploy(
        src=join(constants.COMPONENTS_DIR, RIEMANN, CONFIG, 'main.clj'),
        dst=join(CONFIG_PATH, 'main.clj')
    )
    common.chown(RIEMANN, RIEMANN, CONFIG_PATH)


def _start_and_verify_service():
    logger.info('Starting Riemann service...')
    systemd.configure(RIEMANN)
    systemd.restart(RIEMANN)
    systemd.verify_alive(RIEMANN)


def _create_user():
    create_service_user(RIEMANN, RIEMANN, home=constants.CLOUDIFY_HOME_DIR)

    # Used in the service template
    config[RIEMANN][SERVICE_USER] = RIEMANN
    config[RIEMANN][SERVICE_GROUP] = RIEMANN


def _configure():
    files.copy_notice(RIEMANN)
    _create_user()
    _create_paths()
    set_logrotate(RIEMANN)
    _deploy_riemann_config()
    _start_and_verify_service()


def install():
    logger.notice('Installing Riemann...')
    _configure()
    logger.notice('Riemann successfully installed')


def configure():
    logger.notice('Configuring Riemann...')
    _configure()
    logger.notice('Riemann successfully configured')


def remove():
    logger.notice('Removing Riemann...')
    files.remove_notice(RIEMANN)
    systemd.remove(RIEMANN)
    remove_logrotate(RIEMANN)
    delete_service_user(RIEMANN)
    delete_group(RIEMANN)
    files.remove_files([
        HOME_DIR,
        CONFIG_PATH,
        LOG_DIR,
    ])
    logger.notice('Riemann successfully removed')
