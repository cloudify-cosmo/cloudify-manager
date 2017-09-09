from os.path import join

from .service_names import DEV, RESTSERVICE, MGMTWORKER, AMQPINFLUX

from .. import constants
from ..config import config
from ..logger import get_logger

from ..utils import common
from ..utils.install import pip_install
from ..utils.files import get_local_source_path


logger = get_logger(DEV)


def _install_packages(packages, venv, pip_constraints):
    sources = config[DEV]
    # this allows to upgrade modules if necessary.
    logger.info(
        'Installing Optional Packages in {0} venv...'.format(venv)
    )

    for package in packages:
        if sources[package]:
            pip_install(sources[package], venv, pip_constraints)


def _install_cloudify_manager_pip_packages(pip_constraints):
    rest_venv = config[RESTSERVICE]['venv']
    mgmtworker_venv = config[MGMTWORKER]['venv']

    cloudify_manager_url = config[DEV]['cloudify_manager_source_url']
    if not cloudify_manager_url:
        return

    logger.info('Downloading cloudify-manager Repository...')
    manager_repo = get_local_source_path(cloudify_manager_url)

    logger.info('Extracting Manager Repository...')
    tmp_dir = common.untar(manager_repo, unique_tmp_dir=True)
    rest_service_dir = join(tmp_dir, 'rest-service')
    resources_dir = join(tmp_dir, 'resources', 'rest-service', 'cloudify')
    workflows_dir = join(tmp_dir, 'workflows')
    riemann_dir = join(tmp_dir, 'plugins', 'riemann-controller')

    logger.info('Installing Management Worker Plugins...')
    pip_install(riemann_dir, mgmtworker_venv, pip_constraints)
    pip_install(workflows_dir, mgmtworker_venv, pip_constraints)

    logger.info('Installing REST Service...')
    pip_install(rest_service_dir, rest_venv, pip_constraints)

    logger.info('Deploying Required Manager Resources...')
    common.move(resources_dir, constants.MANAGER_RESOURCES_HOME)

    common.remove(tmp_dir)


def _install_optional_pip_packages(pip_constraints):
    rest_venv = config[RESTSERVICE]['venv']
    mgmtworker_venv = config[MGMTWORKER]['venv']
    amqpinflux_venv = config[AMQPINFLUX]['venv']

    mgmtworker_packages = [
        'rest_client_source_url',
        'plugins_common_source_url',
        'script_plugin_source_url',
        'agent_source_url'
    ]
    rest_packages = mgmtworker_packages + ['dsl_parser_source_url']
    amqpinflux_packages = ['amqpinflux_source_url']

    _install_packages(mgmtworker_packages, mgmtworker_venv, pip_constraints)
    _install_packages(rest_packages, rest_venv, pip_constraints)
    _install_packages(amqpinflux_packages, amqpinflux_venv, pip_constraints)


def _get_pip_constraints():
    if config[DEV]['pip_constraints']:
        return get_local_source_path(config[DEV]['pip_constraints'])
    return None


def run():
    pip_constraints = _get_pip_constraints()

    _install_optional_pip_packages(pip_constraints)
    _install_cloudify_manager_pip_packages(pip_constraints)
