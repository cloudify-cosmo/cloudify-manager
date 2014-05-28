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

import winrm
from cloudify.decorators import operation
from cloudify import utils
from cloudify import context
from functools import wraps


AGENT_PATH = 'c:\cloudify'
AGENT_SERVICE_DIR = '{}\scripts'.format(AGENT_PATH)
PYTHON_PATH = '{}\python.exe'.format(AGENT_SERVICE_DIR)

# AGENT_URL = 'http://{0}:53229/packages/agents/windows-agent.exe'
AGENT_URL = 'http://download.thinkbroadband.com/5MB.zip'
AGENT_INSTALLER_PATH = 'c:\\'
AGENT_EXEC_PATH = 'C:\\windows-agent.exe'
AGENT_SERVICE_NAME = 'CloudifyAgent'
AGENT_SERVICE_HANDLER = '{}\\nssm.exe'.format(AGENT_SERVICE_DIR)

# CELERY_SERVICE_HANDLER = 'celery_service.py'
CELERY_SERVICE_HANDLER = 'CeleryService.py'
CELERY_SERVICE_PATH = AGENT_SERVICE_DIR + '\\' + CELERY_SERVICE_HANDLER
CELERY_LOGFILE_PATH = AGENT_PATH + '\celery.log'
# CELERY_PIDFILE_PATH = AGENT_PATH + '\celery.pid'

DEFAULT_WINRM_PORT = '5985'
DEFAULT_WINRM_URI = 'wsman'
DEFAULT_WINRM_PROTOCOL = 'http'

TEST_HOST_URL = 'http://54.195.158.137:5985/wsman'
TEST_HOST_USER = 'Administrator'
TEST_HOST_PWD = 'y4=c9WGxns)'

PLUGIN_INSTALLER_PLUGIN_PATH = 'plugin_installer.tasks'
CELERY_INCLUDES_LIST = [
    PLUGIN_INSTALLER_PLUGIN_PATH
]

AGENT_PACKAGE_PATH = '/packages/agents/windows-agent.exe'


def get_agent_package_url():
    """
    Returns the agent package url the package will be downloaded from.
    """
    return '{0}{1}'.format(utils.get_manager_file_server_url(),
                           AGENT_PACKAGE_PATH)


# def session(func):
#     @wraps(func)
#     def execution_handler(*args, **kwargs):
#         ctx.logger.debug('openning winRM session: {}...'.format(host_url))
#         session = winrm.Session(host_url, auth=(user, pwd))
#         func(*args, **kwargs)
#         return session

#     return execution_handler


def get_machine_ip(ctx):
    if 'ip' in ctx.properties:
        return ctx.properties['ip']
    if 'ip' in ctx.runtime_properties:
        return ctx.runtime_properties['ip']
    raise ValueError(
        'ip property is not set for node: {0}. This is mandatory'
        ' for installing agent via ssh.'.format(ctx.node_id))


def _find_type_in_kwargs(cls, all_args):
    result = [v for v in all_args if isinstance(v, cls)]
    if not result:
        return None
    if len(result) > 1:
        raise RuntimeError(
            "Expected to find exactly one instance of {0} in "
            "kwargs but found {1}".format(cls, len(result)))
    return result[0]


def session(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        ctx = _find_type_in_kwargs(context.CloudifyContext,
                                   kwargs.values() + list(args))
        if not ctx:
            raise RuntimeError('CloudifyContext not found in invocation args')
        if ctx.properties and 'worker_config' in ctx.properties:
            agent_config = ctx.properties['worker_config']
        else:
            agent_config = {
                'protocol': DEFAULT_WINRM_PROTOCOL,
                'port': DEFAULT_WINRM_PORT,
                'uri': DEFAULT_WINRM_URI,
            }
        machine_ip = get_machine_ip(ctx)
        winrm_url = '{}://{}:{}/{}'.format(
            agent_config['protocol'] or DEFAULT_WINRM_PROTOCOL,
            machine_ip,
            agent_config['port'] or DEFAULT_WINRM_PORT,
            agent_config['uri'] or DEFAULT_WINRM_URI)
        agent_config['session'] = winrm.Session(winrm_url, auth=(
            agent_config['user'], agent_config['password']))
        kwargs['worker_config'] = agent_config
        return func(*args, **kwargs)

        # agent_config['protocol'] = DEFAULT_WINRM_PROTOCOL
        # agent_config['port'] = DEFAULT_WINRM_PORT
        # agent_config['uri'] = DEFAULT_WINRM_URI

        # TODO: check if it's possible to use winrm password-less-ly
    return wrapper


# def _winrm_client(ctx):
#         """
#         returns a winRM client

#         :param string host_url: host's winrm url
#         :param string user: Windows user
#         :param string pwd: Windows password
#         :rtype: `winrm client`
#         """
#         machine_ip = get_machine_ip(ctx)
#         # create default worker_config dict
#         try:
#             agent_config = ctx.properties['worker_config']
#         except IndexError:
#             agent_config = {
#                 'protocol': DEFAULT_WINRM_PROTOCOL,
#                 'port': DEFAULT_WINRM_PORT,
#                 'uri': DEFAULT_WINRM_URI,
#             }
#         except:
#             # TODO: handle exception
#             raise

#         # agent_config['protocol'] = DEFAULT_WINRM_PROTOCOL
#         # agent_config['port'] = DEFAULT_WINRM_PORT
#         # agent_config['uri'] = DEFAULT_WINRM_URI

#         winrm_url = '{}://{}:{}/{}'.format(
#             agent_config['protocol'] or DEFAULT_WINRM_PROTOCOL,
#             machine_ip,
#             agent_config['port'] or DEFAULT_WINRM_PORT,
#             agent_config['uri'] or DEFAULT_WINRM_URI)

#         # TODO: check if it's possible to use winrm password-less-ly
#         ctx.logger.debug('creating winrm session: {}...'.format(machine_ip))
#         return winrm.Session(winrm_url, auth=(
#             agent_config['user'], agent_config['password']))


def execute(ctx, session, command, blocker=True):
    """
    executes a command above a winRM session

    :param session: a winrm session
    :param string command: command to execute
    :param bool blocker: is the command a blocker upon failure
    :rtype: `pywinrm response`
    """
    # powershell -noexit "& 'PATH_TO_POWER_SHELL_SCRIPT.ps1 '
    # -gettedServerName 'HOST'"
    def _chk(response, blocker=True):
        """
        handles command execution output

        :param response: pywinrm response object
        :param bool blocker: is the command a blocker upon failure
        :rtype: `None`
        """
        r = response
        if r.status_code == 0:
            ctx.logger.debug('command executed successfully')
            if not len(r.std_out) == 0:
                ctx.logger.debug('OUTPUT: {}'.format(r.std_out))
        else:
            ctx.logger.debug('command execution failed! white executing: {0}'
                             ' (with code: {1})'.format(
                                 command, r.status_code))
            if not len(r.std_err) == 0:
                ctx.logger.debug('ERROR: {}'.format(r.std_err))
            else:
                ctx.logger.debug('ERROR: ', 'unknown error')
            if blocker:
                raise AgentInstallerError

    ctx.logger.debug('executing: {}'.format(command))
    response = session.run_cmd(command)
    _chk(response, blocker)
    return response


def download(ctx, session):
    """
    downloads the windows agent using powershell's Downloadfile method

    :param session: a winrm session
    """
    ctx.logger.debug('downloading windows agent...')
    return execute(ctx, session,
        '''@powershell -Command "(new-object System.Net.WebClient).Downloadfile('{0}', '{1}')"''' # NOQA
            .format(get_agent_package_url(), AGENT_EXEC_PATH))


@operation
@session
def install(ctx, **kwargs):
    """
    installs the agent

    :param string params: a string of celery params to pass
     to the installer
    :rtype: `bool` - True if installation is successful
    """
    # session = _winrm_client(ctx)
    download(ctx, session)
    ctx.logger.debug('extracting agent...')
    execute(ctx, session, '{} -o"{}" -y'.format(AGENT_EXEC_PATH,
                                                AGENT_INSTALLER_PATH))
    ctx.logger.debug('installing agent...')
    params = ('--broker=amqp://guest:guest@${0}:5672// '
              '--include=plugin_installer.tasks '
              '--events '
              '--app=cloudify '
              '--loglevel=debug '
              '-Q cloudify.agent '
              '-n celery.cloudify.agent '
              '--logfile={1}'.format(
                  utils.get.manager_ip(), CELERY_LOGFILE_PATH))
    execute(ctx, session, '{0} install {1} "{2}\\celeryd.exe" "{3}"'.format(
        AGENT_SERVICE_HANDLER, AGENT_SERVICE_NAME,
        AGENT_SERVICE_DIR, params))
    execute(ctx, session, 'sc config {} start=auto'.format(
        AGENT_SERVICE_NAME))
    execute(ctx, session, 'sc failure {} reset=60 actions=restart/5000'.format(
        AGENT_SERVICE_NAME))

    # def _service_handler(self, action):
    # """
    # handles the celery service

    # :param string action: action to perform (install, remove)
    # :rtype: `None`
    # """
    # return self.execute('{} {} {}'.format(
    #     PYTHON_PATH, CELERY_SERVICE_PATH, action))

    # install service using python service installer
    # self._service_handler('install')

    # install service using windows task scheduler
    # print('creating agent scheduled task...')
    # self.execute('schtasks /Create /RU Administrator /RP y4=c9WGxns) /TN "Cloudify Agent" /XML c:\cloudify\cloudify_agent_task.xml /NP /F') # NOQA
    # print('running task...')
    # self.execute('schtasks /Run /U Administrator /RP y4=c9WGxns) /TN "Cloudify Agent"') # NOQA

    # print 'deleting agent installer...'
    # self.execute('del /q {}'.format(AGENT_EXEC_PATH))
    return True


@operation
@session
def start(ctx, session, **kwargs):
    """
    starts the agent
    """
    # session = _winrm_client(ctx)
    ctx.logger.debug('starting agent...')
    execute(ctx, session, 'sc start {}'.format(AGENT_SERVICE_NAME))


@operation
@session
def restart(ctx, session, **kwargs):
    """
    restarts the agent
    """
    # session = _winrm_client(ctx)
    ctx.logger.debug('restarting agent...')
    execute(ctx, session, 'sc stop {}'.format(AGENT_SERVICE_NAME))
    execute(ctx, session, 'sc start {}'.format(AGENT_SERVICE_NAME))


@operation
@session
def uninstall(ctx, session, blocker, **kwargs):
    """
    uninstalls the agent
    """
    # session = _winrm_client(ctx)
    ctx.logger.debug('uninstalling agent service...')
    # install service using nssm
    execute(ctx, session, 'sc stop {}'.format(
        AGENT_SERVICE_NAME), blocker=blocker)
    execute(ctx, session, '{0} remove {1} confirm'.format(
        AGENT_SERVICE_HANDLER, AGENT_SERVICE_NAME), blocker=blocker)
    # self._service_handler('remove')
    # ctx.logger.debug('deleting agent files...')
    # self.execute('del /q {}'.format(AGENT_PATH))


@operation
def reinstall(ctx, **kwargs):
    """
    reinstalls the agent
    """
    ctx.logger.debug('reinstalling agent')
    uninstall()
    install()


class AgentInstallerError(Exception):
    pass


if __name__ == '__main__':
    # create http session with host (can use _get_mgmt_ip from plugins_common)
    # session = _winrm_client(TEST_HOST_URL, TEST_HOST_USER, TEST_HOST_PWD)
    # agent = WindowsAgentHandler(session)
    # agent.download(AGENT_URL, AGENT_EXEC_PATH)
    reinstall(blocker=False)
    # agent.uninstall()
