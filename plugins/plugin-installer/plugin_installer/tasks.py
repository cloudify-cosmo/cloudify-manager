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

import logging
import os
import subprocess
import shlex
import tempfile
import shutil
from os import path

import pip

from cloudify.constants import VIRTUALENV_PATH_KEY, CELERY_WORK_DIR_PATH_KEY
from cloudify.utils import get_cosmo_properties
from cloudify.decorators import operation


logger = logging.getLogger('default')
logger.level = logging.DEBUG

manager_branch = 'master'


@operation
def install(ctx, plugins, **kwargs):
    """
    Installs plugins as celery tasks according to the provided plugins
    details.
    the plugins parameter is expected to be a list where each element is in
    the following format:
            { name: "...", url: "..." } OR { name: "...", folder: "..." }
    The plugin url should be a URL pointing to either a zip or tar.gz file.
    The plugin folder should be a a folder name inside the blueprint
    'plugins' directory containing the plugin.
    """
    global logger
    logger = ctx.logger

    for plugin in plugins:
        ctx.logger.info("Installing plugin {0}".format(plugin['name']))

        if plugin['name'] == 'default_workflows':
            # special handling for the default workflows plugin, as it does not
            # currently sit on the file server and is not under a blueprint
            # context
            plugin['url'] = '/opt/manager/cloudify-manager-{}/workflows'\
                            .format(manager_branch)
            install_celery_plugin(plugin)
            continue

        if "folder" in plugin:

            # convert the folder into a url inside the file server

            management_ip = get_cosmo_properties()["management_ip"]
            if management_ip:
                plugin["url"] = \
                    "http://{0}:53229/blueprints/{1}/plugins/{2}.zip"\
                    .format(management_ip, ctx.blueprint_id, plugin['folder'])

        ctx.logger.info("Installing plugin from URL --> {0}"
                        .format(plugin['url']))
        install_celery_plugin(plugin)


def uninstall(plugin, __cloudify_id, **kwargs):
    logger.debug("uninstalling plugin [%s] in host [%s]",
                 plugin,
                 __cloudify_id)

    uninstall_celery_plugin(plugin['name'])


def get_python():
    return get_prefix_for_command("python")


def get_pip():
    return get_prefix_for_command("pip")


def get_prefix_for_command(command):
    try:
        return os.path.join(os.environ[VIRTUALENV_PATH_KEY], "bin", command)
    except KeyError:
        logger.warning("virtual env does not exist. "
                       "running regular command {0}".format(command))
        return command


def write_to_includes(module_paths, includes_path=None):

    if not includes_path:
        includes_path = "{0}/celeryd-includes"\
                        .format(os.environ[CELERY_WORK_DIR_PATH_KEY])

    if os.path.exists(includes_path):
        with open(includes_path, mode='r') as f:
            includes_definition = f.read()
            includes = includes_definition.split("=")[1].replace("\n", "")
            new_includes = "{0},{1}".format(includes, module_paths)
    else:
        new_includes = module_paths

    with open(includes_path, mode='w') as f:
        f.write("INCLUDES={0}\n".format(new_includes))


def install_celery_plugin(plugin):
    """
    Installs a plugin from a url as a python library.

    ``plugin['url']`` url to zipped version of the python project.

            - needed for pip installation.
    """

    plugin_url = plugin["url"]

    plugin_name = extract_plugin_name(plugin_url)

    module_paths = extract_module_paths(plugin_name)

    # this will install the plugin and
    # its dependencies into the python installation
    command = "{0} install {1}"\
              .format(get_pip(), plugin_url)
    run_command(command)
    logger.debug("installed plugin {0} and "
                 "dependencies into python installation {1}"
                 .format(plugin_name, get_python()))

    write_to_includes(",".join(module_paths))


def extract_module_paths(plugin_name):

    module_paths = []
    files = run_command("{0} show -f {1}"
                        .format(get_pip(), plugin_name)).splitlines()
    for module in files:
        if module.endswith(".py") and "__init__" not in module:
            # the files paths are relative to the package __init__.py file.
            module_paths.append(module.replace("../", "")
                                .replace("/", ".").replace(".py", "").strip())
    return module_paths


def extract_plugin_name(plugin_url):
    previous_cwd = os.getcwd()
    fetch_plugin_from_pip_by_url = not os.path.isdir(plugin_url)
    plugin_dir = plugin_url
    try:
        if fetch_plugin_from_pip_by_url:
            plugin_dir = tempfile.mkdtemp()
            req_set = pip.req.RequirementSet(build_dir=None,
                                             src_dir=None,
                                             download_dir=None)
            req_set.unpack_url(link=pip.index.Link(plugin_url),
                               location=plugin_dir,
                               download_dir=None,
                               only_download=False)
        os.chdir(plugin_dir)
        plugin_name = run_command('{0} {1} {2}'.format(
            get_python(),
            path.join(path.dirname(__file__), 'extract_package_name.py'),
            plugin_dir))
        run_command('{0} install --no-deps {1}'.format(get_pip(), plugin_dir))
        return plugin_name
    finally:
        os.chdir(previous_cwd)
        if fetch_plugin_from_pip_by_url:
            shutil.rmtree(plugin_dir)


def uninstall_celery_plugin(plugin_name):
    """
    Uninstalls a plugin from a url as a python library.

    ``plugin_name`` is the full name of the plugin.

    """

    # this will uninstall the plugin
    command = "{0} uninstall -y {1}".format(get_pip(), plugin_name)
    run_command(command)
    logger.debug("uninstalled plugin {0} from "
                 "python installation {1}"
                 .format(plugin_name, get_python()))


def get_plugin_simple_name(full_plugin_name):
    return full_plugin_name.split(".")[-1:][0]


def run_command(command):
    shlex_split = shlex.split(command)
    p = subprocess.Popen(shlex_split,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    out, err = p.communicate()
    if p.returncode != 0:
        raise RuntimeError("Failed running command {0} [returncode={1}, "
                           "output={2}, error={3}]"
                           .format(command, p.returncode, out, err))
    if out is None:
        raise RuntimeError("Running command {0} returned None!"
                           .format(command))
    return out
