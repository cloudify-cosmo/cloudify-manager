import sys
import getpass
from tempfile import mkdtemp
from os.path import join, isfile, expanduser, dirname

from ..service_names import SANITY, MANAGER

from ...utils import common
from ...config import config
from ...logger import get_logger
from ...utils.network import wait_for_port
from ...constants import CLOUDIFY_HOME_DIR
from ...utils.files import get_local_source_path

logger = get_logger(SANITY)

AUTHORIZED_KEYS_PATH = expanduser('~/.ssh/authorized_keys')


def _create_ssh_key():
    logger.info('Creating SSH key for sanity...')
    key_path = join(mkdtemp(), 'ssh_key')
    common.run(['ssh-keygen', '-t', 'rsa', '-f', key_path, '-q', '-N', ''])
    new_path = join(CLOUDIFY_HOME_DIR, 'ssh_key')
    common.move(key_path, new_path)
    common.chmod('600', new_path)
    common.chown('cfyuser', 'cfyuser', new_path)
    logger.debug('Created SSH key: {0}'.format(new_path))
    _add_ssh_key_to_authorized(key_path)
    return new_path


def _add_ssh_key_to_authorized(ssh_key_path):
    public_ssh = '{0}.pub'.format(ssh_key_path)
    if isfile(AUTHORIZED_KEYS_PATH):
        logger.debug('Adding sanity SSH key to current authorized_keys...')
        common.run(
            ['cat {0} >> {1}'.format(public_ssh, AUTHORIZED_KEYS_PATH)],
            shell=True
        )
        common.remove(public_ssh)
    else:
        logger.debug('Setting sanity SSH key as authorized_keys...')
        common.move(public_ssh, AUTHORIZED_KEYS_PATH)
    common.remove(dirname(ssh_key_path))


def _remove_sanity_ssh():
    # This removes the last line from the file
    common.run(["sed -i '$ d' {0}".format(AUTHORIZED_KEYS_PATH)], shell=True)


def _upload_blueprint():
    logger.info('Uploading sanity blueprint...')
    sanity_source_url = config[SANITY]['sources']['sanity_source_url']
    sanity_blueprint = get_local_source_path(sanity_source_url)
    common.run(['cfy', 'blueprints', 'upload', sanity_blueprint, '-n',
                'no-monitoring-singlehost-blueprint.yaml', '-b', SANITY],
               stdout=sys.stdout)


def _deploy_app(ssh_key_path):
    logger.info('Deploying sanity app...')
    manager_ip = config[MANAGER]['private_ip']
    ssh_user = getpass.getuser()
    common.run(['cfy', 'deployments', 'create', '-b', SANITY, SANITY,
                '-i', 'server_ip={0}'.format(manager_ip),
                '-i', 'agent_user={0}'.format(ssh_user),
                '-i', 'agent_private_key_path={0}'.format(ssh_key_path)],
               stdout=sys.stdout)


def _install_sanity():
    logger.info('Installing sanity app...')
    common.run(['cfy', 'executions', 'start', 'install', '-d', SANITY],
               stdout=sys.stdout)


def _verify_sanity():
    wait_for_port(8080)


def _clean_old_sanity():
    logger.debug('Removing remnants of old sanity installation if exists...')
    common.remove('/opt/mgmtworker/work/deployments/default_tenant/sanity')


def _run_sanity(ssh_key_path):
    _clean_old_sanity()
    _upload_blueprint()
    _deploy_app(ssh_key_path)
    _install_sanity()


def _clean_sanity():
    logger.info('Removing sanity...')
    common.run(['cfy', 'executions', 'start', 'uninstall', '-d', SANITY],
               stdout=sys.stdout)
    common.run(['cfy', 'deployments', 'delete', SANITY],
               stdout=sys.stdout)
    common.run(['cfy', 'blueprints', 'delete', SANITY],
               stdout=sys.stdout)


def install():
    logger.notice('Running Sanity...')
    ssh_key_path = _create_ssh_key()
    _run_sanity(ssh_key_path)
    _verify_sanity()
    _clean_sanity()
    _remove_sanity_ssh()
    logger.notice('Sanity completed successfully')
