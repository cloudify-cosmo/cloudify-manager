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
from worker_installer import with_fabric_runner

from cloudify.decorators import operation
from cloudify import manager
from cloudify import utils


PLUGIN_INSTALLER_PLUGIN_PATH = 'plugin_installer.tasks'
AGENT_INSTALLER_PLUGIN_PATH = 'worker_installer.tasks'

CELERY_CONFIG_PATH = \
    '/packages/agents/templates/celeryd-cloudify.conf.template'

CELERY_INIT_PATH = '/packages/agents/templates/celeryd-cloudify.init.template'

AGENT_PACKAGE_URL = \
    'https://dl.dropboxusercontent.com/u/407576/agent-Ubuntu.tar'


@operation
@with_fabric_runner
def install(ctx, runner, worker_config, **kwargs):

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
        'Downloading agent package from: {0}'.format(AGENT_PACKAGE_URL))

    runner.run('wget -O {0}/agent.tar {1}'.format(worker_config['base_dir'],
                                                  AGENT_PACKAGE_URL))

    runner.run(
        'tar -xvf {0}/agent.tar --strip=4 -C {0} ./opt/agent-Ubuntu/'
        'cloudify.management__worker/'.format(worker_config['base_dir']))

    create_celery_configuration(
        ctx, runner, worker_config, manager.get_resource)

    runner.run('sudo chmod +x {0}'.format(worker_config['init_file']))

    # This is for fixing virtualenv included in package paths
    runner.run("sed -i 's|/opt/agent-Ubuntu/cloudify.management__worker"
               "/env/bin/python|{0}/env/bin/python|g' "
               "{0}/env/bin/*".format(worker_config['base_dir']))


@operation
@with_fabric_runner
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
@with_fabric_runner
def stop(ctx, runner, worker_config, **kwargs):

    ctx.logger.info("stopping celery worker {0}".format(worker_config['name']))

    service_file_path = "/etc/init.d/celeryd-{0}".format(worker_config['name'])

    if runner.exists(service_file_path):
        runner.run(
            "sudo service celeryd-{0} stop".format(worker_config["name"]))
    else:
        ctx.logger.debug(
            "Could not find any workers with name {0}. nothing to do."
            .format(worker_config["name"]))


@operation
@with_fabric_runner
def start(ctx, runner, worker_config, **kwargs):

    ctx.logger.info("starting celery worker {0}".format(worker_config['name']))

    runner.run("sudo service celeryd-{0} start".format(worker_config["name"]))

    _verify_no_celery_error(runner, worker_config)


@operation
@with_fabric_runner
def restart(ctx, runner, worker_config, **kwargs):

    ctx.logger.info(
        "restarting celery worker {0}".format(worker_config['name']))

    restart_celery_worker(runner, worker_config)


def create_celery_configuration(ctx, runner, worker_config, resource_loader):
    create_celery_includes_file(ctx, runner, worker_config)
    loader = jinja2.FunctionLoader(resource_loader)
    env = jinja2.Environment(loader=loader)
    config_template = env.get_template(CELERY_CONFIG_PATH)
    config_template_values = {
        'includes_file_path': worker_config['includes_file'],
        'celery_base_dir': worker_config['celery_base_dir'],
        'worker_modifier': worker_config['name'],
        'management_ip': utils.get_manager_ip(),
        'agent_ip': utils.get_local_ip(),
        'celery_user': worker_config['user'],
        'celery_group': worker_config['user']
    }
    config = config_template.render(config_template_values)
    init_template = env.get_template(CELERY_INIT_PATH)
    init_template_values = {'worker_modifier': worker_config['name']}
    init = init_template.render(init_template_values)
    runner.put(worker_config['config_file'], config, use_sudo=True)
    runner.put(worker_config['init_file'], init, use_sudo=True)


def create_celery_includes_file(ctx, runner, worker_config):
    # build initial includes
    includes_list = [AGENT_INSTALLER_PLUGIN_PATH, PLUGIN_INSTALLER_PLUGIN_PATH]

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


def build_env_string(env):
    string = ""
    for key, value in env.iteritems():
        string = "export {0}=\"{1}\"\n{2}".format(key, value, string)
    return string
