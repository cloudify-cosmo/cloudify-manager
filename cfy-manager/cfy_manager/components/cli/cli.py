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

from os.path import join, expanduser

from .. import SECURITY

from ..service_names import CLI, MANAGER

from ...config import config
from ...logger import get_logger

from ...utils import common


logger = get_logger(CLI)


def _set_colors(is_root):
    """ Makes sure colors are enabled by default in cloudify logs via CLI """

    home_dir = '/root' if is_root else expanduser('~')
    sed_cmd = 's/colors: false/colors: true/g'
    config_path = join(home_dir, '.cloudify', 'config.yaml')
    cmd = "/usr/bin/sed -i -e '{0}' {1}".format(sed_cmd, config_path)

    # Adding sudo manually, because common.sudo doesn't work well with sed
    cmd = "sudo {0}".format(cmd) if is_root else cmd
    common.run([cmd], shell=True)


def _configure():
    username = config[MANAGER][SECURITY]['admin_username']
    password = config[MANAGER][SECURITY]['admin_password']

    use_cmd = ['cfy', 'profiles', 'use', 'localhost',
               '--skip-credentials-validation']
    set_cmd = [
        'cfy', 'profiles', 'set', '-u', username,
        '-p', password, '-t', 'default_tenant'
    ]
    logger.info('Setting CLI for default user...')
    common.run(use_cmd)
    common.run(set_cmd)
    _set_colors(is_root=False)

    logger.info('Setting CLI for root user...')
    for cmd in (use_cmd, set_cmd):
        root_cmd = ['sudo', '-u', 'root'] + cmd
        common.run(root_cmd)
    _set_colors(is_root=True)


def install():
    logger.notice('Configuring Cloudify CLI...')
    _configure()
    logger.notice('Cloudify CLI successfully configured')


def configure():
    logger.notice('Configuring Cloudify CLI...')
    _configure()
    logger.notice('Cloudify CLI successfully configured')


def remove():
    pass
