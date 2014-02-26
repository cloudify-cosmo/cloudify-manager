#/***************************************************************************
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
from os.path import dirname
import subprocess
import shlex
import ast
import _ast
from os import path

from celery.utils.log import get_task_logger
from cloudify.constants import VIRTUALENV_PATH_KEY, CELERY_WORK_DIR_PATH_KEY
from cloudify.utils import get_cosmo_properties
from cloudify.decorators import operation


logger = get_task_logger(__name__)
logger.level = logging.DEBUG


@operation
def install(ctx, plugin, **kwargs):
    """
    Installs plugin as celery task according to the provided plugins details.
    plugin parameter is expected to be in the following format:
            { name: "...", url: "..." } OR { name: "...", folder: "..." }
    The plugin url should be a URL pointing to either a zip or tar.gz file.
    The plugin folder should be a a folder name inside the blueprint 'plugins' directory containing the plugin.
    """

    ctx.logger.debug("installing plugin [%s] ", plugin)

    if "folder" in plugin:

        # convert the folder into a url inside the file server

        management_ip = get_cosmo_properties()["management_ip"]
        if management_ip:
            plugin["url"] = "http://{0}:53229/{1}/{2}.zip"\
                .format(management_ip, ctx.blueprint_id, plugin['folder'])

    install_celery_plugin(plugin)


def uninstall(plugin, __cloudify_id, **kwargs):
    logger.debug("uninstalling plugin [%s] in host [%s]",
                 plugin,
                 __cloudify_id)

    uninstall_celery_plugin(plugin['name'])


@operation
def verify_plugin(worker_id, plugin_name, operation, throw_on_failure,
                  **kwargs):
    """
    Verifies that a plugin and and a specific operation is registered
    within the celery worker
    """
    out = run_command("{0} inspect registered -d {1} --no-color"
                      .format(get_celery(), worker_id))
    lines = out.splitlines()
    registered_operations = []
    for line in lines:
        processed_line = line.strip()
        if processed_line.startswith("*"):
            task_name = processed_line[1:].strip()
            if task_name.startswith(plugin_name):
                registered_operations.append(task_name)
                if task_name == plugin_name + "." + operation:
                    return True
    #Could not locate registered plugin and the specified operation
    if throw_on_failure:
        raise RuntimeError(
            """
Unable to locate plugin {0} operation {1} in celery registered tasks,
make sure the plugin has an implementation of
this operation.
Registered plugin operation are:
{2}""".format(plugin_name, operation, registered_operations))
    else:
        return False


@operation
def get_arguments(plugin_name, operation, **kwargs):
    """
    Gets the arguments of an installed plugin operation
    """
    operation_split = operation.split('.')
    module_name = '.'.join(operation_split[:-1])
    method_name = operation.split(".")[-1]
    cosmo_dir = dirname(dirname(os.path.abspath(__file__)))
    plugin_dir = os.path.join(cosmo_dir, plugin_name)
    py_path = _extract_py_path(plugin_dir, module_name,
                               method_name, plugin_name)
    parsed_tasks_file = ast.parse(open(py_path, 'r').read())
    method_description = filter(lambda item: type(item) ==
                                _ast.FunctionDef and item.name == method_name,
                                parsed_tasks_file.body)
    if not method_description:
        raise RuntimeError("unable to locate operation {0} "
                           "inside plugin file {1} [plugin name={2}]"
                           .format(method_name, py_path, plugin_name))
    return map(lambda arg: arg.id, method_description[0].args.args)


def _extract_py_path(plugin_dir, module_name, method_name, plugin_name):
    module_path = module_name.replace('.', '/')
    path1 = path.join(plugin_dir, module_path + '.py')
    if path.isfile(path1):
        return path1
    if module_path != '':
        module_path += '/'
    path2 = path.join(plugin_dir, module_path + '__init__.py')
    if path.isfile(path2):
        return path2
    raise RuntimeError('Unable to locate module containing operation {0}. '
                       '{1} for plugin {2} tried '
                       '{3} and {4}'
                       .format(module_name,
                               method_name,
                               plugin_name,
                               path1,
                               path2))


def get_python():
    return get_prefix_for_command("python")


def get_pip():
    return get_prefix_for_command("pip")


def get_celery():
    return get_prefix_for_command("celery")


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
    command = "{0} install --process-dependency-links {1}"\
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
        if module.endswith(".py") and not "__init__" in module:
            # the files paths are relative to the package __init__.py file.
            module_paths.append(module.replace("../", "")
                                .replace("/", ".").replace(".py", "").strip())
    return module_paths


def extract_plugin_name(plugin_url):

    before = set(run_command("{0} freeze".format(get_pip())).splitlines())

    run_command("{0} install --no-deps {1}".format(get_pip(), plugin_url))

    after = set(run_command("{0} freeze".format(get_pip())).splitlines())

    diff = after.difference(before)

    if len(diff) != 1:
        raise RuntimeError("Cannot extract plugin name for plugin {0}. "
                           "Newly installed libs are : {1}"
                           .format(plugin_url, diff))

    return diff.pop().split("==")[0]


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
