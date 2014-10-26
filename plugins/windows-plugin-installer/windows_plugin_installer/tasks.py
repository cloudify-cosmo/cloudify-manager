#########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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
import sys

from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError
from cloudify import utils
from windows_plugin_installer import plugin_utils

# Hard coded path for now - agents are always installed to this path.
NSSM_PATH = 'C:\CloudifyAgent\\nssm\\nssm.exe'

# Holds the AppParameters set for the service
APP_PARAMETERS_FILE_PATH = 'C:\CloudifyAgent\AppParameters'


logger = utils.setup_default_logger('plugin_installer.tasks')


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
    utils.LocalCommandRunner().run(
        'cmd /c "{0} set CloudifyAgent AppParameters {1}"'
        .format(NSSM_PATH, new_app_parameters))

    # Write new AppParameters
    write_app_parameters(new_app_parameters)


def add_module_paths_to_includes(module_paths, app_parameters):

    includes = app_parameters.split('--include=')[1].split()[0]
    new_includes = '{0},{1}'.format(includes, module_paths)

    return app_parameters.replace(includes, new_includes)


@operation
def install(ctx, plugins, **kwargs):

    """
    Installs the given plugins.
    Each method decorated with the 'cloudify.decorators.operation'
    will be registered as a task.

    :param ctx: Invocation context. See class CloudifyContext @context.py
    :param plugins: A collection of plugins to install.
    """

    global logger
    logger = ctx.logger

    for plugin in plugins:
        install_plugin(ctx.blueprint.id, plugin)


def install_plugin(blueprint_id, plugin):
    logger.info('Installing plugin {0}'.format(plugin['name']))
    url = get_url(blueprint_id, plugin)
    install_celery_plugin(url)


def install_celery_plugin(plugin_url):

    """

    Installs celery tasks into the cloudify agent.

        1. Installs the plugin into the current python installation directory.
        2  Adds the python files into the agent includes directive.

    :param plugin_url: URL to an archive of the plugin.
    :return:
    """

    command = 'cmd /c "{0}\Scripts\pip.exe install {1}"'\
              .format(sys.prefix, plugin_url)
    utils.LocalCommandRunner(logger).run(command)

    plugin_name = plugin_utils.extract_plugin_name(plugin_url)

    module_paths = plugin_utils.extract_module_paths(plugin_name)

    _update_includes(module_paths)


def get_url(blueprint_id, plugin):

    source = plugin['source']
    if '://' in source:
        split = source.split('://')
        schema = split[0]
        if schema in ['http', 'https']:
            # in case of a URL, return as is.
            return source
        # invalid schema
        raise NonRecoverableError('Invalid schema: {0}'.format(schema))

    # Else, assume its a relative path from <blueprint_home>/plugins
    # to a directory containing the plugin project.
    # in this case, the archived plugin will reside in the manager file server.

    blueprint_plugins_url = '{0}/{1}/plugins'.format(
        utils.get_manager_file_server_blueprints_root_url(),
        blueprint_id
    )
    return '{0}/{1}.zip'.format(blueprint_plugins_url, source)
