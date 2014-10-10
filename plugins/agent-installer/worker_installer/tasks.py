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

import time
import os
import jinja2
import urllib2

from cloudify import ctx
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError
from cloudify.celery import celery as celery_client
from cloudify import manager
from cloudify import utils

from worker_installer import init_worker_installer
from worker_installer.utils import is_on_management_worker


PLUGIN_INSTALLER_PLUGIN_PATH = 'plugin_installer.tasks'
AGENT_INSTALLER_PLUGIN_PATH = 'worker_installer.tasks'
WINDOWS_AGENT_INSTALLER_PLUGIN_PATH = 'windows_agent_installer.tasks'
WINDOWS_PLUGIN_INSTALLER_PLUGIN_PATH = 'windows_plugin_installer.tasks'
SCRIPT_PLUGIN_PATH = 'script_runner.tasks'
DEFAULT_WORKFLOWS_PLUGIN_PATH = 'cloudify.plugins.workflows'
CELERY_INCLUDES_LIST = [
    AGENT_INSTALLER_PLUGIN_PATH, PLUGIN_INSTALLER_PLUGIN_PATH,
    WINDOWS_AGENT_INSTALLER_PLUGIN_PATH, WINDOWS_PLUGIN_INSTALLER_PLUGIN_PATH,
    SCRIPT_PLUGIN_PATH, DEFAULT_WORKFLOWS_PLUGIN_PATH
]

AGENT_RESOURCES = {
    'celery_config_path':
    '/packages/templates/{0}-celeryd-cloudify.conf.template',
    'celery_init_path':
    '/packages/templates/{0}-celeryd-cloudify.init.template',
    'agent_package_path':
    '/packages/agents/{0}-agent.tar.gz',
    'disable_requiretty_script_path':
    '/packages/scripts/{0}-agent-disable-requiretty.sh'
}


def get_agent_resource_url(ctx, agent_config, resource):
    """returns an agent's resource url

    the resource will be looked for in the agent's properties.
    If it isn't found, it will look for it in the default location.
    """
    if agent_config.get(resource):
        origin = os.path.join(
            utils.get_manager_file_server_blueprints_root_url(),
            os.path.join(ctx.blueprint.id, agent_config[resource]))
    else:
        resource_path = AGENT_RESOURCES[resource]
        if not len(str(utils.get_manager_file_server_url())) > 0:
            raise NonRecoverableError(
                'MANAGER_FILE_SERVER_URL env var not configured')
        origin = utils.get_manager_file_server_url() + \
            resource_path.format(agent_config['distro'])
    ctx.logger.debug('resource origin: {0}'.format(origin))
    try:
        urllib2.urlopen(origin)
    except NonRecoverableError as ex:
        ctx.logger.warning('resource: {0} is not accessible ({1})'.format(
            origin, str(ex)))
        return
    return origin


def get_celery_includes_list():
    return CELERY_INCLUDES_LIST


def download_resource_on_host(logger, runner, url, destination_path):
    """downloads a resource from the fileserver on the agent's host

    Will try to get the resource. If it fails, will try to curl.
    If both fail, will return the state of the last fabric action.
    """
    logger.debug('attempting to download {0} to {1}'.format(
        url, destination_path))
    logger.debug('checking if wget exists on the host machine')
    r = runner.run('which wget')
    if type(r) is str or r.succeeded:
        logger.debug('wget-ing {0} to {1}'.format(url, destination_path))
        return runner.run('wget -T 30 {0} -O {1}'.format(
            url, destination_path))
    logger.debug('checking if curl exists on the host machine')
    r = runner.run('which curl')
    if type(r) is str or r.succeeded:
        logger.debug('curl-ing {0} to {1}'.format(url, destination_path))
        return runner.run('curl {0} -O {1}'.format(
            url, destination_path))
    logger.warn('could not download resource ({0} (with code {1}) )'.format(
        r.stderr, r.status_code))
    return r.succeeded


@operation
@init_worker_installer
def install(ctx, runner, agent_config, **kwargs):
    agent_package_url = get_agent_resource_url(
        ctx, agent_config, 'agent_package_path')
    if not agent_package_url:
        raise NonRecoverableError('failed to retrieve agent package url')

    ctx.logger.debug("Pinging agent installer target")
    runner.ping()

    ctx.logger.info(
        "installing celery worker {0}".format(agent_config['name']))
    if worker_exists(runner, agent_config):
        ctx.logger.info("Worker for deployment {0} is already installed. "
                        "nothing to do.".format(ctx.deployment_id))
        return

    ctx.logger.info(
        'Installing celery worker [cloudify_agent={0}]'.format(agent_config))
    runner.run('mkdir -p {0}'.format(agent_config['base_dir']))

    ctx.logger.debug(
        'Downloading agent package from: {0}'.format(agent_package_url))
    download_resource_on_host(
        ctx.logger, runner, agent_package_url, '{0}/{1}'.format(
            agent_config['base_dir'], 'agent.tar.gz'))
    # if not r:
    #     raise NonRecoverableError('failed to download agent package')

    ctx.logger.debug('extracting agent package on host')
    runner.run(
        'tar xzvf {0}/agent.tar.gz --strip=2 -C {1}'.format(
            agent_config['base_dir'], agent_config['base_dir']))

    ctx.logger.debug('configuring virtualenv')
    for link in ['archives', 'bin', 'include', 'lib']:
        link_path = '{0}/env/local/{1}'.format(agent_config['base_dir'], link)
        try:
            runner.run('unlink {0}'.format(link_path))
            runner.run('ln -s {0}/env/{1} {2}'.format(
                agent_config['base_dir'], link, link_path))
        except Exception as e:
            ctx.logger.warn('Error processing link: {0} [error={1}] - '
                            'ignoring..'.format(link_path, str(e)))

    create_celery_configuration(
        ctx, runner, agent_config, manager.get_resource)

    runner.run('sudo chmod +x {0}'.format(agent_config['init_file']))

    # This is for fixing virtualenv included in package paths
    runner.run("sed -i '1 s|.*/bin/python.*$|#!{0}/env/bin/python|g' "
               "{0}/env/bin/*".format(agent_config['base_dir']))

    # Remove downloaded agent package
    runner.run('rm {0}/agent.tar.gz'.format(agent_config['base_dir']))

    # Disable requiretty
    if agent_config['disable_requiretty']:
        disable_requiretty_script_url = get_agent_resource_url(
            ctx, agent_config, 'disable_requiretty_script_path')
        if not disable_requiretty_script_url:
            raise NonRecoverableError(
                'failed to retrieve disable-requiretty script url')
        ctx.logger.debug("Removing requiretty in sudoers file")
        disable_requiretty_script = '{0}/disable-requiretty.sh'.format(
            agent_config['base_dir'])

        download_resource_on_host(
            ctx.logger, runner, disable_requiretty_script_url,
            disable_requiretty_script)
        # if not r:
        #     raise NonRecoverableError(
        #         'failed to download disable-requiretty script')

        runner.run('chmod +x {0}'.format(disable_requiretty_script))

        runner.run('sudo {0}'.format(disable_requiretty_script))


@operation
@init_worker_installer
def uninstall(ctx, runner, agent_config, **kwargs):

    ctx.logger.info(
        'Uninstalling celery worker [cloudify_agent={0}]'.format(agent_config))

    files_to_delete = [
        agent_config['init_file'], agent_config['config_file']
    ]
    folders_to_delete = [agent_config['base_dir']]
    delete_files_if_exist(ctx, agent_config, runner, files_to_delete)
    delete_folders_if_exist(ctx, agent_config, runner, folders_to_delete)


def delete_files_if_exist(ctx, agent_config, runner, files):
    missing_files = []
    for file_to_delete in files:
        if runner.exists(file_to_delete):
            runner.run("sudo rm {0}".format(file_to_delete))
        else:
            missing_files.append(file_to_delete)
    if missing_files:
        ctx.logger.debug(
            "Could not find files {0} while trying to uninstall worker {1}"
            .format(missing_files, agent_config['name']))


def delete_folders_if_exist(ctx, agent_config, runner, folders):
    missing_folders = []
    for folder_to_delete in folders:
        if runner.exists(folder_to_delete):
            runner.run('sudo rm -rf {0}'.format(folder_to_delete))
        else:
            missing_folders.append(folder_to_delete)
    if missing_folders:
        ctx.logger.debug(
            'Could not find folders {0} while trying to uninstall worker {1}'
            .format(missing_folders, agent_config['name']))


@operation
@init_worker_installer
def stop(ctx, runner, agent_config, **kwargs):

    ctx.logger.info("stopping celery worker {0}".format(agent_config['name']))

    if runner.exists(agent_config['init_file']):
        runner.run(
            "sudo service celeryd-{0} stop".format(agent_config["name"]))
    else:
        ctx.logger.debug(
            "Could not find any workers with name {0}. nothing to do."
            .format(agent_config["name"]))


@operation
@init_worker_installer
def start(ctx, runner, agent_config, **kwargs):

    ctx.logger.info("starting celery worker {0}".format(agent_config['name']))

    runner.run("sudo service celeryd-{0} start".format(agent_config["name"]))

    _wait_for_started(runner, agent_config)


@operation
@init_worker_installer
def restart(ctx, runner, agent_config, **kwargs):

    ctx.logger.info(
        "restarting celery worker {0}".format(agent_config['name']))

    restart_celery_worker(runner, agent_config)


def get_agent_ip(ctx, agent_config):
    if is_on_management_worker(ctx):
        return utils.get_manager_ip()
    return agent_config['host']


def create_celery_configuration(ctx, runner, agent_config, resource_loader):
    create_celery_includes_file(ctx, runner, agent_config)
    loader = jinja2.FunctionLoader(resource_loader)
    env = jinja2.Environment(loader=loader)
    config_template = env.get_template(
        AGENT_RESOURCES['celery_config_path'].format(agent_config['distro']))
    config_template_values = {
        'includes_file_path': agent_config['includes_file'],
        'celery_base_dir': agent_config['celery_base_dir'],
        'worker_modifier': agent_config['name'],
        'management_ip': utils.get_manager_ip(),
        'broker_ip': '127.0.0.1' if is_on_management_worker(ctx)
        else utils.get_manager_ip(),
        'agent_ip': get_agent_ip(ctx, agent_config),
        'celery_user': agent_config['user'],
        'celery_group': agent_config['user'],
        'worker_autoscale': '{0},{1}'.format(agent_config['max_workers'],
                                             agent_config['min_workers'])
    }

    ctx.logger.debug(
        'Populating celery config jinja2 template with the following '
        'values: {0}'.format(config_template_values))

    config = config_template.render(config_template_values)
    init_template = env.get_template(
        AGENT_RESOURCES['celery_init_path'].format(agent_config['distro']))
    init_template_values = {
        'celery_base_dir': agent_config['celery_base_dir'],
        'worker_modifier': agent_config['name']
    }

    ctx.logger.debug(
        'Populating celery init.d jinja2 template with the following '
        'values: {0}'.format(init_template_values))

    init = init_template.render(init_template_values)

    ctx.logger.debug(
        'Creating celery config and init files [cloudify_agent={0}]'.format(
            agent_config))

    runner.put(agent_config['config_file'], config, use_sudo=True)
    runner.put(agent_config['init_file'], init, use_sudo=True)


def create_celery_includes_file(ctx, runner, agent_config):
    # build initial includes
    includes_list = get_celery_includes_list()
    runner.put(agent_config['includes_file'], 'INCLUDES={0}\n'.format(
        ','.join(includes_list)))

    ctx.logger.debug('Created celery includes file [file=%s, content=%s]',
                     agent_config['includes_file'],
                     includes_list)


def worker_exists(runner, agent_config):
    return runner.exists(agent_config['base_dir'])


def restart_celery_worker(runner, agent_config):
    runner.run("sudo service celeryd-{0} restart".format(
        agent_config['name']))
    _wait_for_started(runner, agent_config)


def _verify_no_celery_error(runner, agent_config):
    celery_error_out = os.path.join(
        agent_config['base_dir'], 'work/celery_error.out')

    # this means the celery worker had an uncaught
    #  exception and it wrote its content
    # to the file above because of our custom exception handler (see celery.py)
    if runner.exists(celery_error_out):
        output = runner.get(celery_error_out)
        runner.run('rm {0}'.format(celery_error_out))
        raise NonRecoverableError(
            'Celery worker failed to start:\n{0}'.format(output))


def _wait_for_started(runner, agent_config):
    _verify_no_celery_error(runner, agent_config)
    worker_name = 'celery.{0}'.format(agent_config['name'])
    inspect = celery_client.control.inspect(destination=[worker_name])
    wait_started_timeout = agent_config['wait_started_timeout']
    timeout = time.time() + wait_started_timeout
    interval = agent_config['wait_started_interval']
    while time.time() < timeout:
        stats = (inspect.stats() or {}).get(worker_name)
        if stats:
            return
        time.sleep(interval)
    _verify_no_celery_error(runner, agent_config)
    celery_log_file = os.path.join(
        agent_config['base_dir'], 'work/celery.log')
    if os.path.exists(celery_log_file):
        with open(celery_log_file, 'r') as f:
            ctx.logger.error(f.read())
    raise NonRecoverableError('Failed starting agent. waited for {0} seconds.'
                              .format(wait_started_timeout))
