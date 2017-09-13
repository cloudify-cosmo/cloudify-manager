import os
import subprocess
from os.path import join

from ..service_names import MANAGER

from ... import constants
from ...config import config
from ...logger import get_logger

from ...utils import common
from ...utils.users import create_service_user
from ...utils.logrotate import setup_logrotate
from ...utils.sudoers import add_entry_to_sudoers
from ...utils.files import replace_in_file, get_local_source_path

logger = get_logger(MANAGER)


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


def _extract_single_tar():
    logger.info('Extracting Cloudify manager resources archive...')
    single_tar_url = config[MANAGER]['sources']['manager_resources_package']
    local_single_tar_path = get_local_source_path(single_tar_url)
    common.mkdir(constants.CLOUDIFY_SOURCES_PATH)
    common.untar(
        local_single_tar_path,
        constants.CLOUDIFY_SOURCES_PATH,
        skip_old_files=True
    )


def _normalize_agent_names():
    logger.info('Copying agent packages...')

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


def _create_manager_resources_dirs():
    resources_root = constants.MANAGER_RESOURCES_HOME
    common.mkdir(resources_root)
    common.mkdir(join(resources_root, 'cloudify_agent'))
    common.mkdir(join(resources_root, 'packages', 'scripts'))
    common.mkdir(join(resources_root, 'packages', 'templates'))


def _install():
    _extract_single_tar()
    _normalize_agent_names()


def _configure():
    _create_cloudify_user()
    _create_sudoers_file_and_disable_sudo_requiretty()
    _set_selinux_permissive()
    setup_logrotate()
    _create_manager_resources_dirs()


def install():
    logger.notice('Installing Cloudify Manager resources...')
    _install()
    _configure()
    logger.notice('Cloudify Manager resources installed successfully')


def configure():
    logger.notice('Configuring Cloudify Manager resources...')
    _configure()
    logger.notice('Cloudify Manager resources configured...')
