import os
import subprocess

from ... import constants
from ...config import config
from ...logger import get_logger

from ...utils import common
from ...utils.files import replace_in_file
from ...utils.users import create_service_user
from ...utils.logrotate import setup_logrotate
from ...utils.sudoers import add_entry_to_sudoers
from ...utils.network import is_url, curl_download

logger = get_logger('Manager')


def _create_cloudify_user():
    create_service_user(
        user=constants.CLOUDIFY_USER,
        group=constants.CLOUDIFY_GROUP,
        home=constants.CLOUDIFY_HOME_DIR
    )
    common.mkdir(constants.CLOUDIFY_HOME_DIR)


def _create_sudoers_file_and_disable_sudo_requiretty():
    common.remove(constants.CLOUDIFY_SUDOERS_FILE, ignore_failure=True)
    common.sudo(['touch', constants.CLOUDIFY_SUDOERS_FILE])
    common.chmod('440', constants.CLOUDIFY_SUDOERS_FILE)
    entry = 'Defaults:{user} !requiretty'.format(user=constants.CLOUDIFY_USER)
    description = 'Disable sudo requiretty for {0}'.format(
        constants.CLOUDIFY_USER
    )
    add_entry_to_sudoers(entry, description)


def _configure_security_properties():
    if config['manager']['security']['ssl_enabled']:
        logger.info('SSL is enabled, setting rest port to 443 and '
                    'rest protocol to https...')
        external_rest_port = 443
        external_rest_protocol = 'https'
    else:
        logger.info('SSL is disabled, setting rest port '
                    'to 80 and rest protocols to http...')
        external_rest_port = 80
        external_rest_protocol = 'http'
    config['external_rest_port'] = external_rest_port
    config['external_rest_protocol'] = external_rest_protocol


def _download_manager_single_tar():
    single_tar_path = config['packages']['manager_resources_package']
    if is_url(single_tar_path):
        logger.debug('Resource package is a URL. Downloading...')
        return curl_download(single_tar_path)
    else:
        logger.debug('Resource package is a local file. Checking if exists...')
        if not os.path.isfile(single_tar_path):
            raise StandardError('Could not locate local resources package')
        return single_tar_path


def _extract_single_tar(local_single_tar_path):
    common.mkdir(constants.CLOUDIFY_SOURCES_PATH)
    common.untar(
        local_single_tar_path,
        constants.CLOUDIFY_SOURCES_PATH,
        skip_old_files=True
    )


def _normalize_agent_names():
    def splitext(filename):
        # not using os.path.splitext as it would return .gz instead of
        # .tar.gz
        if filename.endswith('.tar.gz'):
            return '.tar.gz'
        elif filename.endswith('.exe'):
            return '.exe'
        else:
            raise StandardError(
                'Unknown agent format for {0}. '
                'Must be either tar.gz or exe'.format(filename))

    def normalize_agent_name(filename):
        # this returns the normalized name of an agent upon which our agent
        # installer retrieves agent packages for installation.
        # e.g. Ubuntu-trusty-agent_3.4.0-m3-b392.tar.gz returns
        # ubuntu-trusty-agent
        return filename.split('_', 1)[0].lower()

    logger.debug('Moving agent packages...')
    common.mkdir(constants.AGENT_ARCHIVES_PATH)
    agents_path = os.path.join(constants.CLOUDIFY_SOURCES_PATH, 'agents')

    for agent_file in os.listdir(agents_path):
        agent_id = normalize_agent_name(agent_file)
        agent_extension = splitext(agent_file)
        common.move(
            os.path.join(agents_path, agent_file),
            os.path.join(constants.AGENT_ARCHIVES_PATH,
                         agent_id + agent_extension)
        )


def _set_ip_config():
    if not config['agent']['broker_ip']:
        config['agent']['broker_ip'] = config['manager']['private_ip']

    config['internal_rest_host'] = config['manager']['private_ip']
    config['external_rest_host'] = config['manager']['public_ip']

    config['file_server_url'] = 'https://{0}:{1}/resources'.format(
        config['internal_rest_host'],
        constants.INTERNAL_REST_PORT
    )


def _set_selinux_permissive():
    """This sets SELinux to permissive mode both for the current session
    and systemwide.
    """
    selinux_state = subprocess.check_output('getenforce').rstrip('\n\r')
    logger.info('Checking whether SELinux in enforced...')
    if selinux_state == 'Enforcing':
        logger.debug('SELinux is enforcing, setting permissive state...')
        common.sudo(['setenforce', 'permissive'])
        replace_in_file(
            'SELINUX=enforcing',
            'SELINUX=permissive',
            '/etc/selinux/config')
    else:
        logger.debug('SELinux is not enforced.')


def run():
    _set_ip_config()
    _create_cloudify_user()
    _create_sudoers_file_and_disable_sudo_requiretty()
    _configure_security_properties()
    _set_selinux_permissive()
    setup_logrotate()
    local_archive_path = _download_manager_single_tar()
    _extract_single_tar(local_archive_path)
    _normalize_agent_names()
