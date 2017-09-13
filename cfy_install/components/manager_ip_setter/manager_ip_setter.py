from os.path import join

from ..service_names import MANAGER, MANAGER_IP_SETTER

from ... import constants
from ...config import config
from ...logger import get_logger

from ...utils import common, sudoers
from ...utils.systemd import systemd


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
        'update-provider-context.py': 'Run update provider context script',
        'create-internal-ssl-certs.py':
            'Run the scripts that recreates internal SSL certs'
    }

    for script, description in scripts_to_deploy.items():
        sudoers.deploy_sudo_command_script(
            script,
            description,
            component=MANAGER_IP_SETTER,
            render=False
        )


def install_manager_ip_setter():
    common.mkdir(MANAGER_IP_SETTER_DIR)
    deploy_cert_script()
    deploy_sudo_scripts()


def install():
    # Always install the ip setter, but only
    # install the scripts if flag is true
    install_manager_ip_setter()
    if config[MANAGER]['set_manager_ip_on_boot']:
        systemd.configure(MANAGER_IP_SETTER)
    else:
        logger.info('Set manager ip on boot is disabled.')
