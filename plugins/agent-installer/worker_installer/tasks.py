#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

__author__ = 'elip'

import os
import jinja2
from worker_installer import init_worker_installer
from worker_installer.utils import is_on_management_worker
from cloudify.decorators import operation
from cloudify import manager
from cloudify import utils


PLUGIN_INSTALLER_PLUGIN_PATH = 'plugin_installer.tasks'
AGENT_INSTALLER_PLUGIN_PATH = 'worker_installer.tasks'
CELERY_INCLUDES_LIST = [
    AGENT_INSTALLER_PLUGIN_PATH, PLUGIN_INSTALLER_PLUGIN_PATH
]

CELERY_CONFIG_FILE = 'celeryd-cloudify.conf.template'
CELERY_INIT_FILE = 'celeryd-cloudify.init.template'
DISABLE_REQUIRETTY_FILE = 'agent-disable-requiretty.sh'
CELERY_CONFIG_PATH = '/packages/templates/{0}-celeryd-cloudify.conf.template'
CELERY_INIT_PATH = '/packages/templates/{0}-celeryd-cloudify.init.template'
AGENT_PACKAGE_PATH = '/packages/agents/{0}-agent.tar.gz'
DISABLE_REQUIRETTY_SCRIPT_URL =\
    '/packages/scripts/{0}-agent-disable-requiretty.sh'

SUPPORTED_DISTROS = ('Ubuntu', 'debian', 'centos')


def get_agent_package_url(distro):
    """
    Returns the agent package url the package will be downloaded from.
    """
    return '{0}{1}'.format(utils.get_manager_file_server_url(),
                           AGENT_PACKAGE_PATH.format(distro))


def get_disable_requiretty_script_url(distro):
    """
    Returns the disable requiretty script url the script will be downloaded
    from.
    """
    return '{0}{1}'.format(utils.get_manager_file_server_url(),
                           DISABLE_REQUIRETTY_SCRIPT_URL.format(distro))


def get_celery_includes_list():
    return CELERY_INCLUDES_LIST


@operation
@init_worker_installer
def install(ctx, runner, worker_config, **kwargs):

    if worker_config['distro'] not in SUPPORTED_DISTROS:
        ctx.logger.error('distro {} not supported '
                         'when installing agent'.format(
                             worker_config['distro']))
        raise RuntimeError('unsupported distribution')
    agent_package_url = get_agent_package_url(worker_config['distro'])

    ctx.logger.debug("Pinging agent installer target")
    runner.ping()

    ctx.logger.info(
        "installing celery worker {0}".format(worker_config['name']))

    if worker_exists(runner, worker_config):
        ctx.logger.info("Worker for deployment {0} "
                        "is already installed. nothing to do."
                        .format(ctx.deployment_id))
        return

    ctx.logger.info(
        'Installing celery worker [worker_config={0}]'.format(worker_config))

    runner.run('mkdir -p {0}'.format(worker_config['base_dir']))

    ctx.logger.debug(
        'Downloading agent package from: {0}'.format(
            agent_package_url))

    runner.run('wget -T 30 -O {0}/{1}-agent.tar.gz {2}'.format(
        worker_config['base_dir'], worker_config['distro'], agent_package_url))

    runner.run(
        'tar xzvf {0}/{1}-agent.tar.gz --strip=2 -C {2}'.format(
            worker_config['base_dir'], worker_config['distro'],
            worker_config['base_dir']))

    for link in ['archives', 'bin', 'include', 'lib']:
        link_path = '{0}/env/local/{1}'.format(worker_config['base_dir'], link)
        try:
            runner.run('unlink {0}'.format(link_path))
            runner.run('ln -s {0}/env/{1} {2}'.format(
                worker_config['base_dir'], link, link_path))
        except Exception as e:
            ctx.logger.warn('Error process link: {0} [error={1}] - '
                            'ignoring..'.format(link_path, str(e)))

    create_celery_configuration(
        ctx, runner, worker_config, manager.get_resource)

    runner.run('sudo chmod +x {0}'.format(worker_config['init_file']))

    # This is for fixing virtualenv included in package paths
    runner.run("sed -i '1 s|.*/bin/python.*$|#!{0}/env/bin/python|g' "
               "{0}/env/bin/*".format(worker_config['base_dir']))

    # Remove downloaded agent package
    runner.run('rm {0}/{1}-agent.tar.gz'.format(
        worker_config['base_dir'], worker_config['distro']))

    # Disable requiretty
    if worker_config['disable_requiretty']:
        ctx.logger.debug("Removing requiretty in sudoers file")
        disable_requiretty_script = '{0}/disable-requiretty.sh'.format(
            worker_config['base_dir'])
        runner.run('wget -T 30 -O {0} {1}'.format(
            disable_requiretty_script, get_disable_requiretty_script_url(
                worker_config['distro'])))

        runner.run('chmod +x {0}'.format(disable_requiretty_script))

        runner.run('sudo {0}'.format(disable_requiretty_script))


@operation
@init_worker_installer
def uninstall(ctx, runner, worker_config, **kwargs):

    ctx.logger.info(
        'Uninstalling celery worker [worker_config={0}]'.format(worker_config))

    files_to_delete = [
        worker_config['init_file'], worker_config['config_file']
    ]
    folders_to_delete = [worker_config['base_dir']]
    delete_files_if_exist(ctx, worker_config, runner, files_to_delete)
    delete_folders_if_exist(ctx, worker_config, runner, folders_to_delete)


def delete_files_if_exist(ctx, worker_config, runner, files):
    missing_files = []
    for file_to_delete in files:
        if runner.exists(file_to_delete):
            runner.run("sudo rm {0}".format(file_to_delete))
        else:
            missing_files.append(file_to_delete)
    if missing_files:
        ctx.logger.debug(
            "Could not find files {0} while trying to uninstall worker {1}"
            .format(missing_files, worker_config['name']))


def delete_folders_if_exist(ctx, worker_config, runner, folders):
    missing_folders = []
    for folder_to_delete in folders:
        if runner.exists(folder_to_delete):
            runner.run('sudo rm -rf {0}'.format(folder_to_delete))
        else:
            missing_folders.append(folder_to_delete)
    if missing_folders:
        ctx.logger.debug(
            'Could not find folders {0} while trying to uninstall worker {1}'
            .format(missing_folders, worker_config['name']))


@operation
@init_worker_installer
def stop(ctx, runner, worker_config, **kwargs):

    ctx.logger.info("stopping celery worker {0}".format(worker_config['name']))

    if runner.exists(worker_config['init_file']):
        runner.run(
            "sudo service celeryd-{0} stop".format(worker_config["name"]))
    else:
        ctx.logger.debug(
            "Could not find any workers with name {0}. nothing to do."
            .format(worker_config["name"]))


@operation
@init_worker_installer
def start(ctx, runner, worker_config, **kwargs):

    ctx.logger.info("starting celery worker {0}".format(worker_config['name']))

    runner.run("sudo service celeryd-{0} start".format(worker_config["name"]))

    _verify_no_celery_error(runner, worker_config)


@operation
@init_worker_installer
def restart(ctx, runner, worker_config, **kwargs):

    ctx.logger.info(
        "restarting celery worker {0}".format(worker_config['name']))

    restart_celery_worker(runner, worker_config)


def get_agent_ip(ctx, worker_config):
    if is_on_management_worker(ctx):
        return utils.get_manager_ip()
    return worker_config['host']


def create_celery_configuration(ctx, runner, worker_config, resource_loader):
    create_celery_includes_file(ctx, runner, worker_config)
    loader = jinja2.FunctionLoader(resource_loader)
    env = jinja2.Environment(loader=loader)
    config_template = env.get_template(CELERY_CONFIG_PATH.format(
        worker_config['distro']))
    config_template_values = {
        'includes_file_path': worker_config['includes_file'],
        'celery_base_dir': worker_config['celery_base_dir'],
        'worker_modifier': worker_config['name'],
        'management_ip': utils.get_manager_ip(),
        'broker_ip': '127.0.0.1' if is_on_management_worker(ctx)
        else utils.get_manager_ip(),
        'agent_ip': get_agent_ip(ctx, worker_config),
        'celery_user': worker_config['user'],
        'celery_group': worker_config['user'],
        'worker_autoscale': '{0},{1}'.format(worker_config['max_workers'],
                                             worker_config['min_workers'])
    }

    ctx.logger.debug(
        'Populating celery config jinja2 template with the following '
        'values: {0}'.format(config_template_values))

    config = config_template.render(config_template_values)
    init_template = env.get_template(CELERY_INIT_PATH.format(
        worker_config['distro']))
    init_template_values = {
        'celery_base_dir': worker_config['celery_base_dir'],
        'worker_modifier': worker_config['name']
    }

    ctx.logger.debug(
        'Populating celery init.d jinja2 template with the following '
        'values: {0}'.format(init_template_values))

    init = init_template.render(init_template_values)

    ctx.logger.debug(
        'Creating celery config and init files [worker_config={0}]'.format(
            worker_config))

    runner.put(worker_config['config_file'], config, use_sudo=True)
    runner.put(worker_config['init_file'], init, use_sudo=True)


def create_celery_includes_file(ctx, runner, worker_config):
    # build initial includes
    includes_list = get_celery_includes_list()

    runner.put(worker_config['includes_file'],
               'INCLUDES={0}\n'.format(','.join(includes_list)))

    ctx.logger.debug('Created celery includes file [file=%s, content=%s]',
                     worker_config['includes_file'],
                     includes_list)


def worker_exists(runner, worker_config):
    return runner.exists(worker_config['base_dir'])


def restart_celery_worker(runner, worker_config):
    runner.run("sudo service celeryd-{0} restart".format(
        worker_config['name']))
    _verify_no_celery_error(runner, worker_config)


def _verify_no_celery_error(runner, worker_config):
    celery_error_out = os.path.join(
        worker_config['base_dir'], 'work/celery_error.out')

    # this means the celery worker had an uncaught
    #  exception and it wrote its content
    # to the file above because of our custom exception handler (see celery.py)
    if runner.exists(celery_error_out):
        output = runner.get(celery_error_out)
        runner.run('rm {0}'.format(celery_error_out))
        raise RuntimeError(
            'Celery worker failed to start:\n{0}'.format(output))
