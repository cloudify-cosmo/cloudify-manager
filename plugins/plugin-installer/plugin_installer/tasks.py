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
    extracted_plugin_dir = None
    try:
        name = plugin['name']
        logger.info('Installing {0}'.format(name))
        url, install_args = get_url_and_args(blueprint_id, plugin)
        logger.debug('Installing {0} from {1} with args: {2}'
                     .format(name, url, install_args))

        extracted_plugin_dir = extract_plugin_dir(url)

        install_package(extracted_plugin_dir, install_args)
        module_paths = extract_module_paths(extracted_plugin_dir)
        update_includes(module_paths)
    finally:
        if extracted_plugin_dir:
            shutil.rmtree(extracted_plugin_dir)


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


def install_package(extracted_plugin_dir, install_args):

    """
    Installs a package onto the worker's virtualenv.

    :param extracted_plugin_dir:The directory containing the extracted plugin.
                                If the plugin's source property is a URL, this
                                is the directory the plugin was unpacked to.
    :param install_args:       Arguments passed to pip install.
                                e.g.: -r requirements.txt
    """

    previous_cwd = os.getcwd()

    try:
        os.chdir(extracted_plugin_dir)

        command = '{0} install . {1}'.format(_pip(), install_args)
        LocalCommandRunner(host=utils.get_local_ip()).run(command)
    finally:
        os.chdir(previous_cwd)


def extract_module_paths(plugin_dir):

    plugin_name = extract_plugin_name(plugin_dir)

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


def extract_plugin_name(plugin_dir):
    previous_cwd = os.getcwd()

    try:
        os.chdir(plugin_dir)
        runner = LocalCommandRunner(host=utils.get_local_ip())
        plugin_name = runner.run(
            '{0} {1} {2}'.format(_python(),
                                 path.join(
                                     path.dirname(__file__),
                                     'extract_package_name.py'),
                                 plugin_dir)).std_out
        return plugin_name
    finally:
        os.chdir(previous_cwd)


def extract_plugin_dir(plugin_url):
    plugin_dir = None

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

    except Exception as e:
        if plugin_dir and os.path.exists(plugin_dir):
            shutil.rmtree(plugin_dir)
        raise NonRecoverableError('Failed to download and unpack plugin from '
                                  '{0}: {1}'.format(plugin_url, str(e)))

    return plugin_dir


def get_url_and_args(blueprint_id, plugin_dict):

    source = plugin_dict.get('source') or ''
    if source:
        source = source.strip()
    else:
        raise NonRecoverableError('Plugin source is not defined')

    install_args = plugin_dict.get('install_arguments') or ''
    install_args = install_args.strip()

    # validate source url
    if '://' in source:
        split = source.split('://')
        schema = split[0]
        if schema not in ['http', 'https']:
            # invalid schema
            raise NonRecoverableError('Invalid schema: {0}'.format(schema))
        else:
            # in case of a URL, return source and args as is.
            return source, install_args

    else:
        # Else, assume its a relative path from <blueprint_home>/plugins
        # to a directory containing the plugin archive.
        # in this case, the archived plugin is expected to reside on the
        # manager file server as a zip file.
        blueprints_root = utils.get_manager_file_server_blueprints_root_url()
        if not blueprints_root:
            raise NonRecoverableError('blueprints root "{0}" is empty'
                                      .format(blueprints_root))

        blueprint_plugins_url = '{0}/{1}/plugins'.format(blueprints_root,
                                                         blueprint_id)

        blueprint_plugins_url_as_zip = '{0}/{1}.zip'.\
                                       format(blueprint_plugins_url, source)
        return blueprint_plugins_url_as_zip, install_args


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
