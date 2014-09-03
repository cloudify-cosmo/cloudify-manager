# ***************************************************************************
# * Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
# *
# * Licensed under the Apache License, Version 2.0 (the "License");
# * you may not use this file except in compliance with the License.
# * You may obtain a copy of the License at
# *
# *       http://www.apache.org/licenses/LICENSE-2.0
# *
# * Unless required by applicable law or agreed to in writing, software
# * distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.
# ***************************************************************************/
import os
import sys

from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError
from cloudify.utils import get_manager_ip, LocalCommandRunner
from windows_plugin_installer import plugin_utils

# Hard coded path for now - agents are always installed to this path.
NSSM_PATH = 'C:\CloudifyAgent\\nssm\\nssm.exe'

# Holds the AppParameters set for the service
APP_PARAMETERS_FILE_PATH = 'C:\CloudifyAgent\AppParameters'


def read_app_parameters():
    if not os.path.exists(APP_PARAMETERS_FILE_PATH):
        raise NonRecoverableError(
            '{0} does not exist'
            .format(APP_PARAMETERS_FILE_PATH))
    with open(name=APP_PARAMETERS_FILE_PATH, mode='r') as f:
        app_parameters = f.read().strip()
        if not app_parameters:
            raise NonRecoverableError(
                '{0} is blank'
                .format(APP_PARAMETERS_FILE_PATH))
        return app_parameters


def write_app_parameters(app_parameters):
    if not os.path.exists(APP_PARAMETERS_FILE_PATH):
        raise NonRecoverableError(
            '{0} does not exist'
            .format(APP_PARAMETERS_FILE_PATH))
    os.remove(APP_PARAMETERS_FILE_PATH)
    with open(name=APP_PARAMETERS_FILE_PATH, mode='w') as f:
        f.write(app_parameters)


def _update_includes(module_paths):

    # Read current AppParameters
    app_parameters = read_app_parameters()

    new_app_parameters = add_module_paths_to_includes(
        module_paths,
        app_parameters)
    LocalCommandRunner().run('cmd /c "{0} set CloudifyAgent AppParameters {1}"'
                             .format(NSSM_PATH, new_app_parameters))

    # Write new AppParameters
    write_app_parameters(new_app_parameters)


def add_module_paths_to_includes(module_paths, app_parameters):

    includes = app_parameters.split('--include=')[1].split()[0]
    new_includes = '{0},{1}'.format(includes, module_paths)

    return app_parameters.replace(includes, new_includes)


@operation
def install(ctx, plugins, **kwargs):

    '''

    Installs plugins as celery tasks according to the provided plugins details.

    the plugins parameter is expected to be a list where each element is in
    one of the following formats:

        1. { name: "...", url: "..." }
        The plugin url should be a URL pointing to either a zip or tar.gz file.

        2. { name: "...", folder: "..." }
        The plugin folder should be a a folder name
        inside the blueprint 'plugins' directory containing the plugin.

    :param ctx: Invocation context - injected by the @operation
    :param plugins: An iterable of plugins to install.
    :return:
    '''

    for plugin in plugins:
        ctx.logger.info("Installing plugin {0}".format(plugin['name']))

        if "folder" in plugin:

            # convert the folder into a url inside the file server
            management_ip = get_manager_ip()
            if management_ip:
                plugin["url"] = 'http://{0}:53229/blueprints/{1}/plugins/{2}.zip'\
                                .format(
                    management_ip,
                    ctx.blueprint_id,
                    plugin['folder'])

        ctx.logger.info("Installing plugin from {0}".format(plugin['url']))
        install_celery_plugin(plugin['url'])


def install_celery_plugin(plugin_url):

    '''

    Installs celery tasks into the cloudify agent.

        1. Installs the plugin into the current python installation directory.
        2  Adds the python files into the agent includes directive.

    :param plugin_url: URL to an archive of the plugin.
    :return:
    '''

    command = 'cmd /c "{0}\Scripts\pip.exe install {1}"'\
              .format(sys.prefix, plugin_url)
    LocalCommandRunner().run(command)

    plugin_name = plugin_utils.extract_plugin_name(plugin_url)

    module_paths = plugin_utils.extract_module_paths(plugin_name)

    _update_includes(module_paths)
