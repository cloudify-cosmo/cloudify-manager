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

from cloudify.decorators import operation
from cloudify import utils

from windows_agent_installer import init_worker_installer


# This is the folder under which the agent is extracted to inside the current directory.
# It is set in the packaging process so it must be hardcoded here.
AGENT_FOLDER_NAME = 'Cloudify'

# This is where we download the agent to.
AGENT_EXEC_FILE_NAME = 'windows-agent.exe'

# nssm will install celery and use this name to identify the service
AGENT_SERVICE_NAME = 'CloudifyAgent'

# location of the agent package on the management machine, relative to the file server root.
AGENT_PACKAGE_PATH = '/packages/agents/windows-agent.exe'



def get_agent_package_url():
    return '{0}{1}'.format(utils.get_manager_file_server_url(),
                           AGENT_PACKAGE_PATH)

@operation
@init_worker_installer
def install(ctx, runner, cloudify_agent, **kwargs):

    ctx.logger.info('Installing agent {0}'
                    .format(cloudify_agent['name']))

    agent_exec_path = '{0}\{1}'.format(cloudify_agent['base_dir'], AGENT_EXEC_FILE_NAME)

    runner.download(get_agent_package_url(), agent_exec_path)
    ctx.logger.debug('Extracting agent to {0}...'.format())

    runner.run('{0} -o{1} -y'.format(agent_exec_path,
                                     cloudify_agent['base_dir']))

    # be consistent with linux naming convention

    runtime_agent_path = '{0}\{1}\env'.format(cloudify_agent['base_dir'],
                                              'cloudify.{0}'.format(cloudify_agent['name']))
    install_time_agent_path = '{0}\{1}'.format(cloudify_agent['base_dir'], AGENT_FOLDER_NAME)

    runner.run('Move-Item {0} {1}'.format(install_time_agent_path,
                                          runtime_agent_path))

    params = ('--broker=amqp://guest:guest@${0}:5672// '
              '--events '
              '--app=cloudify '
              '-Q {1} '
              '-n {1} '
              .format(utils.get_manager_ip()), cloudify_agent['name'])
    runner.run('{0}\scripts\\nssm.exe install {1} {0}\scripts\celeryd.exe {2}'
               .format(runtime_agent_path, AGENT_SERVICE_NAME, params))
    runner.run('sc config {0} start=auto'.format(AGENT_SERVICE_NAME))
    runner.run('sc failure {0} reset=60 actions=restart/5000'.format(AGENT_SERVICE_NAME))

    return True


@operation
@init_worker_installer
def start(ctx, runner, cloudify_agent, **kwargs):

    ctx.logger.info('Starting agent {0}'.format(cloudify_agent['name']))

    runner.run('sc start {}'.format(AGENT_SERVICE_NAME))



@operation
@init_worker_installer
def stop(ctx, runner, cloudify_agent, **kwargs):

    ctx.logger.info('Starting agent {0}'.format(cloudify_agent['name']))

    runner.run('sc stop {}'.format(AGENT_SERVICE_NAME))


@operation
@init_worker_installer
def restart(ctx, runner, cloudify_agent, **kwargs):

    ctx.logger.info('Restarting agent {0}'.format(cloudify_agent['name']))

    runner.run('sc stop {}'.format(AGENT_SERVICE_NAME))
    runner.run('sc start {}'.format(AGENT_SERVICE_NAME))


@operation
@init_worker_installer
def uninstall(ctx, runner, cloudify_agent, **kwargs):

    ctx.logger.info('Uninstalling agent {0}'.format(cloudify_agent['name']))

    runtime_agent_path = '{0}\{1}\env'.format(cloudify_agent['base_dir'],
                                              'cloudify.{0}'.format(cloudify_agent['name']))

    runner.run('sc stop {}'.format(AGENT_SERVICE_NAME))
    runner.run('{0} remove {1} confirm'.format('{0}\scripts\\nssm.exe'.format(runtime_agent_path),
                                               AGENT_SERVICE_NAME))