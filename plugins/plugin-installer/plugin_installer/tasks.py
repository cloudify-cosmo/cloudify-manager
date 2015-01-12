########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import os
import tempfile
import shutil
import pip

from os import path
from cloudify import utils
from cloudify.constants import VIRTUALENV_PATH_KEY
from cloudify.constants import CELERY_WORK_DIR_PATH_KEY
from cloudify.exceptions import NonRecoverableError
from cloudify.utils import LocalCommandRunner
from cloudify.utils import setup_default_logger
from cloudify.decorators import operation


logger = setup_default_logger('plugin_installer.tasks')
manager_branch = 'master'


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
    name = plugin['name']
    logger.info('Installing {0}'.format(name))
    url = get_url(blueprint_id, plugin)
    logger.debug('Installing {0} from {1}'.format(name, url))
    install_package(url)
    module_paths = extract_module_paths(url)
    update_includes(module_paths)


def update_includes(module_paths, includes_path=None):

    if not includes_path:
        includes_path = '{0}/celeryd-includes'\
                        .format(os.environ[CELERY_WORK_DIR_PATH_KEY])

    if os.path.exists(includes_path):
        with open(includes_path, mode='r') as f:
            includes_definition = f.read()
            includes = includes_definition.split('=')[1].replace('\n', '')
            new_includes = '{0},{1}'.format(includes, ','.join(module_paths))
    else:
        new_includes = ','.join(module_paths)

    with open(includes_path, mode='w') as f:
        f.write('INCLUDES={0}\n'.format(new_includes))


def install_package(url):

    """
    Installs a package onto the worker's virtualenv.

    :param url: A URL to the package archive.
    """

    command = '{0} install {1}'.format(_pip(), url)
    LocalCommandRunner(
        host=utils.get_local_ip()
    ).run(command)


def extract_module_paths(url):

    plugin_name = extract_plugin_name(url)

    module_paths = []
    files = LocalCommandRunner(host=utils.get_local_ip()).run(
        '{0} show -f {1}'.format(
            _pip(),
            plugin_name)).std_out.splitlines()
    for module in files:
        if module.endswith('.py') and '__init__' not in module:
            # the files paths are relative to the package __init__.py file.
            module_paths.append(module.replace('../', '')
                                .replace('/', '.').replace('.py', '').strip())
    return module_paths


def extract_plugin_name(plugin_url):
    previous_cwd = os.getcwd()
    fetch_plugin_from_pip_by_url = not os.path.isdir(plugin_url)
    plugin_dir = plugin_url
    try:
        plugin_dir = tempfile.mkdtemp()
        # check pip version and unpack plugin_url accordingly
        if is_pip6_or_higher():
            pip.download.unpack_url(link=pip.index.Link(plugin_url),
                                    location=plugin_dir,
                                    download_dir=None,
                                    only_download=False)
        else:
            req_set = pip.req.RequirementSet(build_dir=None,
                                             src_dir=None,
                                             download_dir=None)
            req_set.unpack_url(link=pip.index.Link(plugin_url),
                               location=plugin_dir,
                               download_dir=None,
                               only_download=False)
        runner = LocalCommandRunner(host=utils.get_local_ip())
        os.chdir(plugin_dir)
        plugin_name = runner.run(
            '{0} {1} {2}'.format(_python(),
                                 path.join(
                                     path.dirname(__file__),
                                     'extract_package_name.py'),
                                 plugin_dir)).std_out
        runner.run('{0} install --no-deps {1}'.format(_pip(), plugin_dir))
        return plugin_name
    finally:
        os.chdir(previous_cwd)
        if fetch_plugin_from_pip_by_url:
            shutil.rmtree(plugin_dir)


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


def _python():
    return _virtualenv('python')


def _pip():
    return _virtualenv('pip')


def _virtualenv(command):
    return os.path.join(os.environ[VIRTUALENV_PATH_KEY],
                        'bin',
                        command)


def is_pip6_or_higher(pip_version=None):
    major, minor, micro = parse_pip_version(pip_version)

    if int(major) >= 6:
        return True
    else:
        return False


def parse_pip_version(pip_version=None):
    if not pip_version:
        try:
            pip_version = pip.__version__
        except AttributeError as e:
            raise NonRecoverableError('Failed to get pip version: ', str(e))

    if not pip_version:
        raise NonRecoverableError('Failed to get pip version')

    if not isinstance(pip_version, basestring):
        raise NonRecoverableError('Invalid pip version: {0} is not a string'
                                  .format(pip_version))

    if not pip_version.__contains__("."):
        raise NonRecoverableError('Unknown formatting of pip version: "{0}", '
                                  'expected dot-delimited numbers (e.g. '
                                  '"1.5.4", "6.0")'.format(pip_version))

    version_parts = pip_version.split('.')
    major = version_parts[0]
    minor = version_parts[1]
    micro = ''
    if len(version_parts) > 2:
        micro = version_parts[2]

    if not str(major).isdigit():
        raise NonRecoverableError('Invalid pip version: "{0}", major version '
                                  'is "{1}" while expected to be a number'
                                  .format(pip_version, major))

    if not str(minor).isdigit():
        raise NonRecoverableError('Invalid pip version: "{0}", minor version '
                                  'is "{1}" while expected to be a number'
                                  .format(pip_version, minor))

    return major, minor, micro
