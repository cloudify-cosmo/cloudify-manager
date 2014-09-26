#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

import os
import time

from cloudify import utils
from cloudify import constants
from cloudify.celery import celery as celery_client
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError

from windows_agent_installer import constants as win_constants
from windows_agent_installer import init_worker_installer
from windows_agent_installer import constants as win_const


# This is the folder under which the agent is
# extracted to inside the current directory.
# It is set in the packaging process so it
# must be hardcoded here.
AGENT_FOLDER_NAME = 'CloudifyAgent'

# This is where we download the agent to.
AGENT_EXEC_FILE_NAME = 'CloudifyAgent.exe'

# nssm will install celery and use this name to identify the service
AGENT_SERVICE_NAME = 'CloudifyAgent'

# location of the agent package on the management machine,
# relative to the file server root.
AGENT_PACKAGE_PATH = '/packages/agents/CloudifyWindowsAgent.exe'

# Path to the agent. We are using global (not user based) paths
# because of virtualenv relocation issues on windows.
RUNTIME_AGENT_PATH = 'C:\CloudifyAgent'

# Agent includes list, Mandatory
AGENT_INCLUDES = 'script_runner.tasks,windows_plugin_installer.tasks,'\
                 'cloudify.plugins.workflows'


def get_agent_package_url():
    return '{0}{1}'.format(utils.get_manager_file_server_url(),
                           AGENT_PACKAGE_PATH)


def get_manager_ip():
    return utils.get_manager_ip()


def create_env_string(cloudify_agent):
    env = {
        constants.CELERY_WORK_DIR_PATH_KEY:
        RUNTIME_AGENT_PATH,
        constants.LOCAL_IP_KEY:
        cloudify_agent['host'],
        constants.MANAGER_IP_KEY:
        get_manager_ip(),
        constants.MANAGER_FILE_SERVER_BLUEPRINTS_ROOT_URL_KEY:
        utils.get_manager_file_server_blueprints_root_url(),
        constants.MANAGER_FILE_SERVER_URL_KEY:
        utils.get_manager_file_server_url(),
        constants.MANAGER_REST_PORT_KEY:
        utils.get_manager_rest_service_port()
    }
    env_string = ''
    for key, value in env.iteritems():
        env_string = '{0} {1}={2}' \
            .format(env_string, key, value)
    return env_string.strip()


@operation
@init_worker_installer
def install(ctx, runner=None, cloudify_agent=None, **kwargs):

    """
    Installs the cloudify agent service on the machine.
    The agent installation consists of the following:

        1. Download and extract necessary files.
        2. Configure the agent service to auto start on vm launch.
        3. Configure the agent service to restart on failure.


    :param ctx: Invocation context - injected by the @operation
    :param runner: Injected by the @init_worker_installer
    :param cloudify_agent: Injected by the @init_worker_installer
    """

    ctx.logger.info('Installing agent {0}'.format(cloudify_agent['name']))

    agent_exec_path = 'C:\{0}'.format(AGENT_EXEC_FILE_NAME)

    runner.download(get_agent_package_url(), agent_exec_path)
    ctx.logger.debug('Extracting agent to C:\\ ...')

    runner.run('{0} -o{1} -y'.format(agent_exec_path, RUNTIME_AGENT_PATH))

    params = ('--broker=amqp://guest:guest@{0}:5672// '
              '--events '
              '--app=cloudify '
              '-Q {1} '
              '-n celery.{1} '
              '--logfile={2}\celery.log '
              '--pidfile={2}\celery.pid '
              '--autoscale={3},{4} '
              '--include={5} '
              .format(get_manager_ip(),
                      cloudify_agent['name'],
                      RUNTIME_AGENT_PATH,
                      cloudify_agent[win_constants.MIN_WORKERS_KEY],
                      cloudify_agent[win_constants.MAX_WORKERS_KEY],
                      AGENT_INCLUDES))
    runner.run('{0}\\nssm\\nssm.exe install {1} {0}\Scripts\celeryd.exe {2}'
               .format(RUNTIME_AGENT_PATH, AGENT_SERVICE_NAME, params))
    env = create_env_string(cloudify_agent)
    runner.run('{0}\\nssm\\nssm.exe set {1} AppEnvironmentExtra {2}'
               .format(RUNTIME_AGENT_PATH, AGENT_SERVICE_NAME, env))
    runner.run('sc config {0} start= auto'.format(AGENT_SERVICE_NAME))
    runner.run(
        'sc failure {0} reset= {1} actions= restart/{2}'.format(
            AGENT_SERVICE_NAME,
            cloudify_agent['service'][
                win_const.SERVICE_FAILURE_RESET_TIMEOUT_KEY
            ],
            cloudify_agent['service'][
                win_const.SERVICE_FAILURE_RESTART_DELAY_KEY
            ]))

    ctx.logger.info('Creating parameters file from {0}'.format(params))
    runner.put(params, '{0}\AppParameters'.format(RUNTIME_AGENT_PATH))


@operation
@init_worker_installer
def start(ctx, runner=None, cloudify_agent=None, **kwargs):

    """
    Starts the cloudify agent service on the machine.

    :param ctx: Invocation context - injected by the @operation
    :param runner: Injected by the @init_worker_installer
    :param cloudify_agent: Injected by the @init_worker_installer
    """

    ctx.logger.info('Starting agent {0}'.format(cloudify_agent['name']))

    runner.run('sc start {}'.format(AGENT_SERVICE_NAME))

    ctx.logger.info('Waiting for {0} to start...'.format(AGENT_SERVICE_NAME))
    _wait_for_started(runner, cloudify_agent)


@operation
@init_worker_installer
def stop(ctx, runner=None, cloudify_agent=None, **kwargs):

    """
    Stops the cloudify agent service on the machine.

    :param ctx: Invocation context - injected by the @operation
    :param runner: Injected by the @init_worker_installer
    :param cloudify_agent: Injected by the @init_worker_installer
    """

    ctx.logger.info('Stopping agent {0}'.format(cloudify_agent['name']))
    runner.run('sc stop {}'.format(AGENT_SERVICE_NAME))

@operation
@init_worker_installer
def restart(ctx, runner=None, cloudify_agent=None, **kwargs):

    """
    Restarts the cloudify agent service on the machine.

        1. Stop the service.
        2. Start the service.

    :param ctx: Invocation context - injected by the @operation
    :param runner: Injected by the @init_worker_installer
    :param cloudify_agent: Injected by the @init_worker_installer
    """

    ctx.logger.info('Restarting agent {0}'.format(cloudify_agent['name']))

    stop(ctx=ctx, runner=runner, cloudify_agent=cloudify_agent)
    start(ctx=ctx, runner=runner, cloudify_agent=cloudify_agent)


@operation
@init_worker_installer
def uninstall(ctx, runner=None, cloudify_agent=None, **kwargs):

    """
    Uninstalls the cloudify agent service from the machine.

        1. Remove the service from the registry.
        2. Delete related files..


    :param ctx: Invocation context - injected by the @operation
    :param runner: Injected by the @init_worker_installer
    :param cloudify_agent: Injected by the @init_worker_installer
    """

    ctx.logger.info('Uninstalling agent {0}'.format(cloudify_agent['name']))

    runner.run('{0} remove {1} confirm'.format('{0}\\nssm\\nssm.exe'
                                               .format(RUNTIME_AGENT_PATH),
                                               AGENT_SERVICE_NAME))

    runner.delete(path=RUNTIME_AGENT_PATH)
    runner.delete(path='C:\\{0}'.format(AGENT_EXEC_FILE_NAME))


def _verify_no_celery_error(runner):
    celery_error_out = os.path.join(
        RUNTIME_AGENT_PATH, win_constants.CELERY_ERROR_FILE)

    # this means the celery worker had an uncaught
    # exception and it wrote its content
    # to the file above because of our custom
    # exception handler (see celery.py)
    if runner.exists(celery_error_out):
        output = runner.get(celery_error_out)
        runner.delete(path=celery_error_out)
        raise NonRecoverableError(output)


def _wait_for_started(runner, cloudify_agent):
    _verify_no_celery_error(runner)
    worker_name = 'celery.{0}'.format(cloudify_agent['name'])
    inspect = celery_client.control.inspect(destination=[worker_name])
    wait_started_timeout = cloudify_agent[
        win_constants.AGENT_START_TIMEOUT_KEY
    ]
    timeout = time.time() + wait_started_timeout
    interval = cloudify_agent[win_constants.AGENT_START_INTERVAL_KEY]
    while time.time() < timeout:
        stats = (inspect.stats() or {}).get(worker_name)
        if stats:
            return
        time.sleep(interval)
    _verify_no_celery_error(runner)
    raise NonRecoverableError('Failed starting agent. waited for {0} seconds.'
                              .format(wait_started_timeout))
