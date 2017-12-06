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

from ..service_names import MANAGER, MANAGER_IP_SETTER

from ... import constants
from ...config import config
from ...logger import get_logger

from ...utils import common, sudoers
from ...utils.systemd import systemd
from ...utils.files import remove_files


MANAGER_IP_SETTER_DIR = join('/opt/cloudify', MANAGER_IP_SETTER)

logger = get_logger(MANAGER_IP_SETTER)


def deploy_cert_script():
    logger.debug('Deploying certificate creation script')
    cert_script_path_src = join(constants.BASE_DIR, 'utils', 'certificates.py')
    cert_script_path_dst = join(MANAGER_IP_SETTER_DIR, 'certificates.py')

    common.copy(cert_script_path_src, cert_script_path_dst)
    common.chmod('550', cert_script_path_dst)
    common.chown('root', constants.CLOUDIFY_GROUP, cert_script_path_dst)


def deploy_sudo_scripts():
    scripts_to_deploy = {
        'manager-ip-setter.sh': 'Run manager IP setter script',
        'update-provider-context.py': 'Run update provider context script'
    }

    for script, description in scripts_to_deploy.items():
        sudoers.deploy_sudo_command_script(
            script,
            description,
            component=MANAGER_IP_SETTER,
            render=False
        )


def _install():
    common.mkdir(MANAGER_IP_SETTER_DIR)
    deploy_cert_script()
    deploy_sudo_scripts()


def _configure():
    if config[MANAGER]['set_manager_ip_on_boot']:
        systemd.configure(MANAGER_IP_SETTER)
    else:
        logger.info('Set manager ip on boot is disabled.')


def install():
    logger.notice('Installing Manager IP Setter...')
    _install()
    _configure()
    logger.notice('Manager IP Setter successfully installed')


def configure():
    logger.notice('Configuring Manager IP Setter...')
    _configure()
    logger.notice('Manager IP Setter successfully configured')


def remove():
    logger.notice('Removing Manager IP Setter...')
    remove_files([MANAGER_IP_SETTER_DIR])
    systemd.remove(MANAGER_IP_SETTER)
    logger.notice('Manager IP Setter successfully removed')
