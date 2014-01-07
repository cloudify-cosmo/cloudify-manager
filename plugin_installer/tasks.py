#/*******************************************************************************
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
# *******************************************************************************/

import logging
import os
import subprocess
import platform
import shlex
import ast
import _ast
from os.path import expanduser
from os import path

from celery.utils.log import get_task_logger
from celery import task

from cosmo.constants import VIRTUALENV_PATH_KEY
import cosmo
from cosmo.events import get_cosmo_properties
from cosmo.constants import COSMO_APP_NAME

logger = get_task_logger(__name__)
logger.level = logging.DEBUG


@task
def install(plugin, __cloudify_id, **kwargs):

    """
    Installs plugin as celery task according to the provided plugins details.
    plugin parameter is expected to be in the following format: { name: "...", url: "..." }
    The plugin's url should be an http url pointing to either a zip or tar.gz file and the compressed file
    should contain a "tasks.py" module with celery tasks.
    """

    logger.debug("installing plugin [%s] in host [%s]", plugin, __cloudify_id)

    management_ip = get_cosmo_properties()["management_ip"]
    if management_ip:
        plugin["url"] = plugin['url'].replace("#{plugin_repository}", "http://{0}:{1}".format(management_ip, "53229"))

    install_celery_plugin_to_dir(plugin)

@task
def verify_plugin(worker_id, plugin_name, operation, throw_on_failure, **kwargs):

    """
    Verifies that a plugin and and a specific operation is registered within the celery worker
    """
    out = run_command("{0} inspect registered -d {1} --no-color".format(get_celery(), worker_id))
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
"""unable to locate plugin {0} operation {1} in celery registered tasks, make sure the plugin has an implementation of
this operation.
Registered plugin operation are: {2}""".format(plugin_name, operation, registered_operations))
    else:
        return False

@task
def get_arguments(plugin_name, operation, **kwargs):
    """
    Gets the arguments of an installed plugin operation
    """
    operation_split = operation.split('.')
    module_name = '.'.join(operation_split[:-1])
    method_name = operation.split(".")[-1]
    cosmo_dir = os.path.abspath(os.path.dirname(cosmo.__file__))
    plugin_dir = os.path.join(cosmo_dir, os.sep.join(plugin_name.split(".")[1:]))
    py_path = _extract_py_path(plugin_dir, module_name, method_name, plugin_name)
    parsed_tasks_file = ast.parse(open(py_path, 'r').read())
    method_description = filter(lambda item: type(item) == _ast.FunctionDef and item.name == method_name,
                                parsed_tasks_file.body)
    if not method_description:
        raise RuntimeError("unable to locate operation {0} inside plugin file {1} [plugin name={2}]"
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
    raise RuntimeError('Unable to locate module containing operation {0}.{1} for plugin {2} tried '
                       '{3} and {4}'.format(module_name, method_name, plugin_name, path1, path2))


def get_pip():
    return get_prefix_for_command("pip")


def get_celery():
    return get_prefix_for_command("celery")


def get_prefix_for_command(command):
    try:
        return os.path.join(os.environ[VIRTUALENV_PATH_KEY], "bin", command)
    except KeyError:
        return command


def install_celery_plugin_to_dir(plugin,
                                 base_dir=os.path.join(expanduser("~"), COSMO_APP_NAME)):

    """
    Installs a plugin from a url to the given base dir.
    NOTE : Plugin dependencies will be installed to the python installation,
           but the plugin itself will not be, this is to avoid conflicts because the plugin is installed to the
           celery dir, which is also sourced to the PYTHONPATH of the system.

    ``plugin['url']`` url to zipped version of the python project.

            - needed for pip installation.

    ``plugin['name']`` is the full name of the plugin. including namespace specification

            - needed for namespace directory structure creation.

    """

    plugin_name = plugin["name"]
    plugin_url = plugin["url"]

    to_dir = create_namespace_path(plugin_name.split(".")[:-1], base_dir)

    # in CentOS (and probably RHEL/Fedora as well) can't simply 'sudo' because of the "you must have a tty to run
    # sudo" error, so using session-command instead.
    is_session_command = platform.dist()[0] == 'centos'
    logger.debug('is_session_command = {0}'.format(is_session_command))
    command_format = "su --session-command='{0}'" if is_session_command else 'sudo {0}'

    # this will install the package and the dependencies into the python installation
    command = "{0} install --process-dependency-links {1}".format(get_pip(), plugin_url)
    run_command(command_format.format(command))
    logger.debug("installed plugin {0} and dependencies into python installation".format(plugin_name))

    # install the package to the target directory. this will also uninstall the plugin package from the python
    # installation. leaving the plugin package just inside the base dir.
    command = "{0} install --no-deps -t {1} {2}".format(get_pip(), to_dir, plugin_url)
    run_command(command_format.format(command))
    logger.debug("installing plugin {0} into {1}".format(plugin_name, to_dir))


def get_plugin_simple_name(full_plugin_name):
    return full_plugin_name.split(".")[-1:][0]


def run_command(command):
    p = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    if p.returncode != 0:
        raise RuntimeError("Failed running command {0} [returncode={1}, "
                           "output={2}, error={3}]".format(command, p.returncode, out, err))
    return out


def create_namespace_path(namespace_parts, base_dir):

    """
    Creates the namespaces path the plugin directory will reside in.
    For example
        input : cloudify.tosca.artifacts.plugin.python_webserver_installer
        input : basedir
        output : a directory path ${basedir}/cloudify/tosca/artifacts/plugin
    In addition, "__init.py__" files will be created in each of the path's sub directories.
    """

    plugin_path = base_dir

    for p in namespace_parts:
        plugin_path = os.path.join(plugin_path, p)
    logger.debug("plugin installation path is {0}".format(plugin_path))

    if not os.path.exists(plugin_path):
        os.makedirs(plugin_path)

    # create __init__.py files in each subfolder
    init_path = base_dir
    for p in namespace_parts:
        init_path = os.path.join(init_path, p)
        init_file = os.path.join(init_path, "__init__.py")
        if not os.path.exists(init_file):
            open(init_file, "w").close()

    return plugin_path

