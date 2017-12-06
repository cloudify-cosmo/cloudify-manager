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

from os.path import join, basename

from .. import CONFIG, LOG_DIR_KEY

from ..service_names import LOGSTASH

from ... import constants
from ...config import config
from ...logger import get_logger

from ...utils import common
from ...utils.systemd import systemd
from ...utils.logrotate import set_logrotate
from ...utils.files import replace_in_file, get_local_source_path
from ...utils.files import remove_files, deploy, copy_notice, remove_notice

HOME_DIR = join('/opt', LOGSTASH)
LOGSTASH_CONF_DIR = join('/etc', LOGSTASH)
LOG_DIR = join(constants.BASE_LOG_DIR, LOGSTASH)
REMOTE_CONFIG_PATH = join(LOGSTASH_CONF_DIR, 'conf.d')
UNIT_OVERRIDE_PATH = '/etc/systemd/system/logstash.service.d'
INIT_D_FILE = '/etc/init.d/logstash'

CONFIG_PATH = join(constants.COMPONENTS_DIR, LOGSTASH, CONFIG)

logger = get_logger(LOGSTASH)


def _install_plugin(name, plugin_url):
    """Install plugin.

    :param name: Plugin name
    :type name: str
    :param plugin_url: Plugin file location
    :type plugin_url: str

    """
    logger.info('Installing {} plugin...'.format(name))
    plugin_path = get_local_source_path(plugin_url)

    # Use /dev/urandom to get entropy faster while installing plugins
    common.run([
        'sudo', '-u', LOGSTASH,
        'sh', '-c',
        (
            'export JRUBY_OPTS=-J-Djava.security.egd=file:/dev/urandom; '
            '/opt/logstash/bin/plugin install {0}'.format(plugin_path)
        )
    ])


def _install_postgresql_jdbc_driver(sources):
    """Install driver used by the jdbc plugin to write data to postgresql."""

    logger.info('Installing PostgreSQL JDBC driver...')
    jdbc_driver_url = sources['postgresql_jdbc_driver_url']
    jar_path = join(HOME_DIR, 'vendor', 'jar')
    jdbc_path = join(jar_path, 'jdbc')
    common.mkdir(jdbc_path)
    common.chown(LOGSTASH, LOGSTASH, jar_path)
    driver_path = get_local_source_path(jdbc_driver_url)
    common.run([
        'sudo', '-u', LOGSTASH,
        'cp',
        driver_path,
        join(jdbc_path, basename(jdbc_driver_url)),
    ])


def _deploy_logstash_config():
    logger.info('Deploying Logstash configuration...')
    config[LOGSTASH][LOG_DIR_KEY] = LOG_DIR  # Used in config files

    deploy(
        join(CONFIG_PATH, 'logstash.conf'),
        join(REMOTE_CONFIG_PATH, 'logstash.conf')
    )
    common.chown(LOGSTASH, LOGSTASH, REMOTE_CONFIG_PATH)


def _deploy_systemd_unit_override():
    logger.debug('Creating systemd unit override...')
    common.mkdir(UNIT_OVERRIDE_PATH)
    deploy(
        join(CONFIG_PATH, 'restart.conf'),
        join(UNIT_OVERRIDE_PATH, 'restart.conf')
    )


def _create_log_dir():
    common.mkdir(LOG_DIR)
    common.chown(LOGSTASH, LOGSTASH, LOG_DIR)


def _edit_init_d_file():
    # Due to a bug in the handling of configuration files,
    # configuration files with the same name cannot be deployed.
    # Since the logrotate config file is called `logstash`,
    # we change the name of the logstash env vars config file
    # from logstash to cloudify-logstash to be consistent with
    # other service env var files.
    replace_in_file(
        'sysconfig/\$name',
        'sysconfig/cloudify-$name',
        INIT_D_FILE)
    common.chmod('755', INIT_D_FILE)
    common.chown('root', 'root', INIT_D_FILE)


def _deploy_logstash_sysconfig():
    deploy(
        join(CONFIG_PATH, 'cloudify-logstash'),
        '/etc/sysconfig/cloudify-logstash'
    )


def _start_and_validate_logstash():
    logger.debug('Checking logstash config...')
    common.sudo(['/sbin/chkconfig', 'logstash', 'on'])
    logger.info('Starting Logstash service...')
    systemd.restart(LOGSTASH, append_prefix=False)
    systemd.verify_alive(LOGSTASH, append_prefix=False)


def _configure():
    _create_log_dir()
    _deploy_systemd_unit_override()
    _deploy_logstash_config()
    _edit_init_d_file()
    _deploy_logstash_sysconfig()
    set_logrotate(LOGSTASH)
    copy_notice(LOGSTASH)
    _start_and_validate_logstash()


def install():
    logger.notice('Installing Logstash...')
    _configure()
    logger.notice('Logstash successfully installed')


def configure():
    logger.notice('Configuring Logstash...')
    _configure()
    logger.notice('Logstash successfully configured')


def remove():
    logger.notice('Removing Logstash...')
    remove_notice(LOGSTASH)
    systemd.remove(LOGSTASH)
    remove_files([HOME_DIR, LOG_DIR, UNIT_OVERRIDE_PATH, LOGSTASH_CONF_DIR])
    logger.notice('Logstash successfully removed')
