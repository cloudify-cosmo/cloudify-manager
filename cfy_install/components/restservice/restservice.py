import os
import json
import random
import string
import base64
import urllib2
import subprocess
from os.path import join, islink, isdir

from .. import (
    SOURCES,
    CONFIG,
    SCRIPTS,
    HOME_DIR_KEY,
    LOG_DIR_KEY,
    VENV,
    SERVICE_USER,
    SERVICE_GROUP,
    SECURITY,
    ENDPOINT_IP
)

from ..service_names import RESTSERVICE, MANAGER, RABBITMQ, POSTGRESQL, AGENT

from ... import constants
from ...config import config
from ...logger import get_logger
from ...exceptions import BootstrapError, NetworkError

from ...utils import common, sudoers
from ...utils.systemd import systemd
from ...utils.install import yum_install, yum_remove
from ...utils.network import get_auth_headers, wait_for_port
from ...utils.files import deploy, remove_notice, copy_notice
from ...utils.logrotate import set_logrotate, remove_logrotate
from ...utils.files import ln, write_to_tempfile, remove_files, write_to_file


HOME_DIR = '/opt/manager'
REST_VENV = join(HOME_DIR, 'env')
LOG_DIR = join(constants.BASE_LOG_DIR, 'rest')
CONFIG_PATH = join(constants.COMPONENTS_DIR, RESTSERVICE, CONFIG)
SCRIPTS_PATH = join(constants.COMPONENTS_DIR, RESTSERVICE, SCRIPTS)

logger = get_logger(RESTSERVICE)


def _random_alphanumeric(result_len=31):
    """
    :return: random string of unique alphanumeric characters
    """
    ascii_alphanumeric = string.ascii_letters + string.digits
    return ''.join(random.sample(ascii_alphanumeric, result_len))


def _make_paths():
    common.mkdir(HOME_DIR)
    common.mkdir(LOG_DIR)
    common.chown(constants.CLOUDIFY_USER, constants.CLOUDIFY_GROUP, LOG_DIR)

    # Used in the service templates
    config[RESTSERVICE][HOME_DIR_KEY] = HOME_DIR
    config[RESTSERVICE][LOG_DIR_KEY] = LOG_DIR
    config[RESTSERVICE][VENV] = REST_VENV


def _deploy_sudo_commands():
    sudoers.deploy_sudo_command_script(
        script='/usr/bin/systemctl',
        description='Run systemctl'
    )
    sudoers.deploy_sudo_command_script(
        script='/usr/sbin/shutdown',
        description='Perform shutdown (reboot)'
    )
    sudoers.deploy_sudo_command_script(
        'set-manager-ssl.py',
        'Script for setting manager SSL',
        component=RESTSERVICE,
        render=False
    )


def _configure_dbus():
    # link dbus-python-1.1.1-9.el7.x86_64 to the venv for `cfy status`
    # (module in pypi is very old)
    site_packages = 'lib64/python2.7/site-packages'
    dbus_relative_path = join(site_packages, 'dbus')
    dbuslib = join('/usr', dbus_relative_path)
    dbus_glib_bindings = join('/usr', site_packages, '_dbus_glib_bindings.so')
    dbus_bindings = join('/usr', site_packages, '_dbus_bindings.so')
    if isdir(dbuslib):
        dbus_venv_path = join(REST_VENV, dbus_relative_path)
        if not islink(dbus_venv_path):
            ln(source=dbuslib, target=dbus_venv_path, params='-sf')
            ln(source=dbus_bindings, target=dbus_venv_path, params='-sf')
        if not islink(join(REST_VENV, site_packages)):
            ln(source=dbus_glib_bindings, target=join(
                    REST_VENV, site_packages), params='-sf')
    else:
        logger.warn('Could not find dbus install, cfy status will not work')


def _install():
    source_url = config[RESTSERVICE][SOURCES]['restservice_source_url']
    yum_install(source_url)

    _configure_dbus()


def _deploy_rest_configuration():
    logger.info('Deploying REST Service Configuration file...')
    conf_path = join(HOME_DIR, 'cloudify-rest.conf')
    deploy(join(CONFIG_PATH, 'cloudify-rest.conf'), conf_path)
    common.chown(constants.CLOUDIFY_USER, constants.CLOUDIFY_GROUP, conf_path)


def _deploy_authorization_configuration():
    logger.info('Deploying REST authorization configuration file...')
    conf_path = join(HOME_DIR, 'authorization.conf')
    deploy(join(CONFIG_PATH, 'authorization.conf'), conf_path)
    common.chown(constants.CLOUDIFY_USER, constants.CLOUDIFY_GROUP, conf_path)


def _pre_create_snapshot_paths():
    for resource_dir in (
            'blueprints',
            'deployments',
            'uploaded-blueprints',
            'snapshots',
            'plugins'
    ):
        path = join(constants.MANAGER_RESOURCES_HOME, resource_dir)
        common.mkdir(path)


def _deploy_security_configuration():
    logger.info('Deploying REST Security configuration file...')

    # Generating random hash salt and secret key
    security_configuration = {
        'hash_salt': base64.b64encode(os.urandom(32)),
        'secret_key': base64.b64encode(os.urandom(32)),
        'encoding_alphabet': _random_alphanumeric(),
        'encoding_block_size': 24,
        'encoding_min_length': 5
    }
    security_configuration.update(config[MANAGER][SECURITY])
    config[RESTSERVICE][SECURITY] = security_configuration

    # Pre-creating paths so permissions fix can work correctly in mgmtworker
    _pre_create_snapshot_paths()
    common.chown(
        constants.CLOUDIFY_USER,
        constants.CLOUDIFY_GROUP,
        constants.MANAGER_RESOURCES_HOME
    )
    rest_security_path = join(HOME_DIR, 'rest-security.conf')
    write_to_file(security_configuration, rest_security_path, json_dump=True)
    common.chown(
        constants.CLOUDIFY_USER,
        constants.CLOUDIFY_GROUP,
        rest_security_path
    )


def _allow_creating_cluster():
    systemd_run = '/usr/bin/systemd-run'
    journalctl = '/usr/bin/journalctl'

    create_cluster_node = join(HOME_DIR, 'env', 'bin', 'create_cluster_node')
    cluster_unit_name = 'cloudify-ha-cluster'

    cmd = '{0} --unit {1} {2} --config *'.format(
        systemd_run,
        cluster_unit_name,
        create_cluster_node
    )
    sudoers.allow_user_to_sudo_command(cmd, description='Start a cluster')

    cmd = '{0} --unit {1}*'.format(journalctl, cluster_unit_name)
    sudoers.allow_user_to_sudo_command(cmd, description='Read cluster logs')


def _calculate_worker_count():
    gunicorn_config = config[RESTSERVICE]['gunicorn']
    worker_count = gunicorn_config['worker_count']
    max_worker_count = gunicorn_config['max_worker_count']
    if not worker_count:
        # Calculate number of processors
        nproc = int(subprocess.check_output('nproc'))
        worker_count = nproc * 2 + 1

    if worker_count > max_worker_count:
        worker_count = max_worker_count

    gunicorn_config['worker_count'] = worker_count


def _configure_restservice():
    config[RESTSERVICE][SERVICE_USER] = constants.CLOUDIFY_USER
    config[RESTSERVICE][SERVICE_GROUP] = constants.CLOUDIFY_GROUP
    _calculate_worker_count()
    _deploy_rest_configuration()
    _deploy_security_configuration()
    _deploy_authorization_configuration()
    _allow_creating_cluster()


def _create_db_tables_and_add_defaults():
    # TODO: Separate into its own component
    logger.info('Creating SQL tables and adding default values...')
    script_name = 'create_tables_and_add_defaults.py'
    script_path = join(SCRIPTS_PATH, script_name)

    # A dictionary with all the information necessary for the script to run
    args_dict = {
        'hash_salt': config[RESTSERVICE][SECURITY]['hash_salt'],
        'secret_key': config[RESTSERVICE][SECURITY]['secret_key'],
        'admin_username': config[MANAGER][SECURITY]['admin_username'],
        'admin_password': config[MANAGER][SECURITY]['admin_password'],
        'amqp_host': config[RABBITMQ][ENDPOINT_IP],
        'amqp_username': config[RABBITMQ]['username'],
        'amqp_password': config[RABBITMQ]['password'],
        'postgresql_host': config[POSTGRESQL]['host'],
        'provider_context': {'cloudify': {'cloudify_agent': config[AGENT]}},
        'authorization_file_path': join(HOME_DIR, 'authorization.conf'),
        'db_migrate_dir': join(
            constants.MANAGER_RESOURCES_HOME,
            'cloudify',
            'migrations'
        )
    }

    # The script won't have access to the config, so we dump the relevant args
    # to a JSON file, and pass its path to the script
    args_json_path = write_to_tempfile(args_dict, json_dump=True)

    # Directly calling with this python bin, in order to make sure it's run
    # in the correct venv
    python_path = join(HOME_DIR, 'env', 'bin', 'python')
    result = common.sudo([python_path, script_path, args_json_path])

    _log_results(result)


def _log_results(result):
    """Log stdout/stderr output from the script
    """
    if result.aggr_stdout:
        output = result.aggr_stdout.split('\n')
        output = [line.strip() for line in output if line.strip()]
        for line in output[:-1]:
            logger.debug(line)
        logger.info(output[-1])
    if result.aggr_stderr:
        output = result.aggr_stderr.split('\n')
        output = [line.strip() for line in output if line.strip()]
        for line in output:
            logger.error(line)


def _verify_restservice():
    """To verify that the REST service is working, GET the blueprints list.

    There's nothing special about the blueprints endpoint, it's simply one
    that also requires the storage backend to be up, so if it works, there's
    a good chance everything is configured correctly.
    """
    rest_port = config[RESTSERVICE]['port']
    url = 'http://{0}:{1}/api/v2.1/blueprints'.format('127.0.0.1', rest_port)

    wait_for_port(rest_port)
    req = urllib2.Request(url, headers=get_auth_headers())

    try:
        response = urllib2.urlopen(req)
    # keep an erroneous HTTP response to examine its status code, but still
    # abort on fatal errors like being unable to connect at all
    except urllib2.HTTPError as e:
        response = e
    except urllib2.URLError as e:
        raise NetworkError(
            'REST service returned an invalid response: {0}'.format(e))
    if response.code == 401:
        raise NetworkError(
            'Could not connect to the REST service: '
            '401 unauthorized. Possible access control misconfiguration'
        )
    if response.code != 200:
        raise NetworkError(
            'REST service returned an unexpected response: '
            '{0}'.format(response.code)
        )

    try:
        json.load(response)
    except ValueError as e:
        raise BootstrapError(
            'REST service returned malformed JSON: {0}'.format(e))


def _start_restservice():
    systemd.restart(RESTSERVICE)
    systemd.verify_alive(RESTSERVICE)

    logger.info('Verifying Rest service is working as expected...')
    _verify_restservice()


def _configure():
    copy_notice(RESTSERVICE)
    _make_paths()
    set_logrotate(RESTSERVICE)
    _deploy_sudo_commands()
    _configure_restservice()
    systemd.configure(RESTSERVICE, tmpfiles=True)
    _create_db_tables_and_add_defaults()
    _start_restservice()


def install():
    logger.notice('Installing Rest Service...')
    _install()
    _configure()
    logger.notice('Rest Service successfully installed')


def configure():
    logger.notice('Configuring Rest Service...')
    _configure()
    logger.notice('Rest Service successfully configured')


def remove():
    logger.notice('Removing Restservice...')
    remove_notice(RESTSERVICE)
    remove_logrotate(RESTSERVICE)
    systemd.remove(RESTSERVICE)
    remove_files([HOME_DIR, LOG_DIR])
    yum_remove('cloudify-rest-service')
    logger.notice('Rest Service successfully installed')
