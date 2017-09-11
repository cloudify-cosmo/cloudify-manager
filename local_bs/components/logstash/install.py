from os.path import join, basename

from ..service_names import LOGSTASH

from ... import constants
from ...config import config
from ...logger import get_logger

from ...utils import common
from ...utils.deploy import deploy
from ...utils.systemd import systemd
from ...utils.install import yum_install
from ...utils.deploy import copy_notice
from ...utils.logrotate import set_logrotate
from ...utils.files import replace_in_file, get_local_source_path

HOME_DIR = join('/opt', LOGSTASH)
LOG_DIR = join(constants.BASE_LOG_DIR, LOGSTASH)
REMOTE_CONFIG_PATH = '/etc/logstash/conf.d'
UNIT_OVERRIDE_PATH = '/etc/systemd/system/logstash.service.d'
INIT_D_FILE = '/etc/init.d/logstash'

CONFIG_PATH = join(constants.COMPONENTS_DIR, LOGSTASH, 'config')

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
        'sudo', '-u', 'logstash',
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
    common.chown('logstash', 'logstash', jar_path)
    driver_path = get_local_source_path(jdbc_driver_url)
    common.run([
        'sudo', '-u', 'logstash',
        'cp',
        driver_path,
        join(jdbc_path, basename(jdbc_driver_url)),
    ])


def _install_plugins(sources):
    _install_plugin(
        name='logstash-filter-json_encode',
        plugin_url=sources['logstash_filter_json_encode_plugin_url']
    )
    _install_plugin(
        name='logstash-output-jdbc',
        plugin_url=sources['logstash_output_jdbc_plugin_url']
    )
    _install_postgresql_jdbc_driver(sources)


def _install_logstash(sources):
    """Install logstash as a systemd service."""
    logger.info('Installing Logstash...')
    copy_notice(LOGSTASH)

    yum_install(sources['logstash_source_url'])

    _install_plugins(sources)

    common.mkdir(LOG_DIR)
    common.chown('logstash', 'logstash', LOG_DIR)

    logger.debug('Creating systemd unit override...')
    common.mkdir(UNIT_OVERRIDE_PATH)
    common.copy(
        join(CONFIG_PATH, 'restart.conf'),
        join(UNIT_OVERRIDE_PATH, 'restart.conf')
    )


def _configure_logstash():
    logger.info('Deploying Logstash configuration...')
    config[LOGSTASH]['log_dir'] = LOG_DIR  # Used in config files

    deploy(
        join(CONFIG_PATH, 'logstash.conf'),
        join(REMOTE_CONFIG_PATH, 'logstash.conf')
    )
    common.chown(LOGSTASH, LOGSTASH, REMOTE_CONFIG_PATH)

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

    logger.debug('Deploying Logstash sysconfig...')
    deploy(
        join(CONFIG_PATH, 'cloudify-logstash'),
        '/etc/sysconfig/cloudify-logstash'
    )

    set_logrotate(LOGSTASH)
    common.sudo(['/sbin/chkconfig', 'logstash', 'on'])


def run():
    sources = config[LOGSTASH]['sources']
    _install_logstash(sources)
    _configure_logstash()

    logger.info('Starting Logstash service...')
    systemd.restart(LOGSTASH, append_prefix=False)
    systemd.verify_alive(LOGSTASH, append_prefix=False)
