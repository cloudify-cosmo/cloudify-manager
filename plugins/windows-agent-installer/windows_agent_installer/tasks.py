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
import os
import time
from cloudify.constants import LOCAL_IP_KEY, MANAGER_IP_KEY

from cloudify.decorators import operation
from cloudify import utils
from cloudify.exceptions import NonRecoverableError
from windows_agent_installer import init_worker_installer
from windows_agent_installer import SERVICE_FAILURE_RESTART_DELAY_KEY, \
    SERVICE_START_TIMEOUT_KEY, \
    SERVICE_STOP_TIMEOUT_KEY, SERVICE_FAILURE_RESET_TIMEOUT_KEY, \
    SERVICE_STATUS_TRANSITION_SLEEP_INTERVAL_KEY, \
    SERVICE_SUCCESSFUL_CONSECUTVE_STATUS_QUERIES_COUNT_KEY, \
    MAX_WORKERS_KEY, \
    MIN_WORKERS_KEY


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
AGENT_INCLUDES = 'windows_plugin_installer.tasks'


def get_agent_package_url():
    return '{0}{1}'.format(utils.get_manager_file_server_url(),
                           AGENT_PACKAGE_PATH)


def get_manager_ip():
    return utils.get_manager_ip()


@operation
@init_worker_installer
def install(ctx, runner=None, cloudify_agent=None, **kwargs):
    '''

    Installs the cloudify agent service on the machine.
    The agent installation consists of the following:

        1. Download and extract necessary files.
        2. Configure the agent service to auto start on vm launch.
        3. Configure the agent service to restart on failure.


    :param ctx: Invocation context - injected by the @operation
    :param runner: Injected by the @init_worker_installer
    :param cloudify_agent: Injected by the @init_worker_installer
    :return:
    '''

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
                      cloudify_agent[MIN_WORKERS_KEY],
                      cloudify_agent[MAX_WORKERS_KEY],
                      AGENT_INCLUDES))
    runner.run('{0}\\nssm\\nssm.exe install {1} {0}\Scripts\celeryd.exe {2}'
               .format(RUNTIME_AGENT_PATH, AGENT_SERVICE_NAME, params))
    env = '{0}={1} {2}={3}'.format(LOCAL_IP_KEY, cloudify_agent['host'],
                                   MANAGER_IP_KEY, get_manager_ip())
    runner.run('{0}\\nssm\\nssm.exe set {1} AppEnvironment {2}'
               .format(RUNTIME_AGENT_PATH, AGENT_SERVICE_NAME, env))
    runner.run('sc config {0} start= auto'.format(AGENT_SERVICE_NAME))
    runner.run(
        'sc failure {0} reset= {1} actions= restart/{2}' .format(
            AGENT_SERVICE_NAME,
            cloudify_agent['service'][SERVICE_FAILURE_RESET_TIMEOUT_KEY],
            cloudify_agent['service'][SERVICE_FAILURE_RESTART_DELAY_KEY]))


@operation
@init_worker_installer
def start(ctx, runner=None, cloudify_agent=None, **kwargs):
    '''

    Starts the cloudify agent service on the machine.

    :param ctx: Invocation context - injected by the @operation
    :param runner: Injected by the @init_worker_installer
    :param cloudify_agent: Injected by the @init_worker_installer
    :return:
    '''

    ctx.logger.info('Starting agent {0}'.format(cloudify_agent['name']))

    runner.run('sc start {}'.format(AGENT_SERVICE_NAME))

    ctx.logger.info('Waiting for {0} to start...'.format(AGENT_SERVICE_NAME))

    _wait_for_service_status(
        runner,
        cloudify_agent,
        AGENT_SERVICE_NAME,
        'Running',
        cloudify_agent['service'][SERVICE_START_TIMEOUT_KEY])


@operation
@init_worker_installer
def stop(ctx, runner=None, cloudify_agent=None, **kwargs):
    '''

    Stops the cloudify agent service on the machine.

    :param ctx: Invocation context - injected by the @operation
    :param runner: Injected by the @init_worker_installer
    :param cloudify_agent: Injected by the @init_worker_installer
    :return:
    '''

    ctx.logger.info('Stopping agent {0}'.format(cloudify_agent['name']))

    runner.run('sc stop {}'.format(AGENT_SERVICE_NAME))

    ctx.logger.info('Waiting for {0} to stop...'.format(AGENT_SERVICE_NAME))

    _wait_for_service_status(
        runner,
        cloudify_agent,
        AGENT_SERVICE_NAME,
        'Stopped',
        cloudify_agent['service'][SERVICE_STOP_TIMEOUT_KEY])


@operation
@init_worker_installer
def restart(ctx, runner=None, cloudify_agent=None, **kwargs):
    '''

    Restarts the cloudify agent service on the machine.

        1. Stop the service.
        2. Start the service.

    :param ctx: Invocation context - injected by the @operation
    :param runner: Injected by the @init_worker_installer
    :param cloudify_agent: Injected by the @init_worker_installer
    :return:
    '''

    ctx.logger.info('Restarting agent {0}'.format(cloudify_agent['name']))

    stop(ctx=ctx, runner=runner, cloudify_agent=cloudify_agent)
    start(ctx=ctx, runner=runner, cloudify_agent=cloudify_agent)


@operation
@init_worker_installer
def uninstall(ctx, runner=None, cloudify_agent=None, **kwargs):
    '''

    Uninstalls the cloudify agent service from the machine.

        1. Remove the service from the registry.
        2. Delete related files..


    :param ctx: Invocation context - injected by the @operation
    :param runner: Injected by the @init_worker_installer
    :param cloudify_agent: Injected by the @init_worker_installer
    :return:
    '''

    ctx.logger.info('Uninstalling agent {0}'.format(cloudify_agent['name']))

    runner.run('{0} remove {1} confirm'.format('{0}\\nssm\\nssm.exe'
                                               .format(RUNTIME_AGENT_PATH),
                                               AGENT_SERVICE_NAME))

    runner.delete(path=RUNTIME_AGENT_PATH)
    runner.delete(path='C:\\{0}'.format(AGENT_EXEC_FILE_NAME))


def _wait_for_service_status(runner,
                             cloudify_agent,
                             service_name,
                             desired_status,
                             timeout_in_seconds):

    end_time = time.time() + timeout_in_seconds

    successful_consecutive_queries = 0

    while end_time > time.time():

        service_state = runner.service_state(service_name)
        if desired_status.lower() \
           == service_state.lower() and _pid_file_exists():
            successful_consecutive_queries += 1
            if successful_consecutive_queries == cloudify_agent['service'][
                    SERVICE_SUCCESSFUL_CONSECUTVE_STATUS_QUERIES_COUNT_KEY]:
                return
        else:
            successful_consecutive_queries = 0
        time.sleep(
            cloudify_agent['service']
            [SERVICE_STATUS_TRANSITION_SLEEP_INTERVAL_KEY])
    raise NonRecoverableError(
        "Service {0} did not reach {1} state in {2} seconds. "
        "Error was: {3}"
        .format(
            service_name,
            desired_status,
            timeout_in_seconds,
            _read_celery_log()))


def _read_celery_log():
    log_file_path = '{0}\celery.log'\
                    .format(RUNTIME_AGENT_PATH)
    if os.path.exists(log_file_path):
        with open(log_file_path, "r") as myfile:
            return myfile.read()


def _pid_file_exists():
    return os.path.exists('{0}\celery.pid'
                          .format(RUNTIME_AGENT_PATH))
