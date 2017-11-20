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
