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
import ast
import _ast
from os.path import expanduser

from celery.utils.log import get_task_logger
from celery import task

import cosmo
from cosmo.events import get_cosmo_properties

logger = get_task_logger(__name__)
logger.level = logging.DEBUG

COSMO_APP_NAME = "cosmo"

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
def verify_plugin(worker_id, plugin_name, operation, **kwargs):
    out = run_command("celery inspect registered -d {0} --no-color".format(worker_id))
    lines = out.splitlines()
    registered_tasks = list()
    operation_name = operation.split(".")[-1]
    for line in lines:
        processed_line = line.strip()
        if processed_line.startswith("*"):
            task = processed_line[1:].strip()
            if task.startswith(plugin_name) and task.endswith("." + operation_name):
                cosmo_dir = os.path.abspath(os.path.dirname(cosmo.__file__))
                plugin_dir = os.path.join(cosmo_dir, os.sep.join(plugin_name.split(".")[1:-1]))
                taskspy_path = os.path.join(plugin_dir, "tasks.py")
                parsed_tasks_file = ast.parse(open(taskspy_path, 'r').read())
                method_description = filter(lambda item: type(item) == _ast.FunctionDef and item.name == operation_name,
                                            parsed_tasks_file.body)
                if not method_description:
                    raise RuntimeError("unable to locate operation {0} inside plugin file {1} [plugin name={2}]"
                                       .format(operation_name, taskspy_path, plugin_name))
                return map(lambda arg: arg.id, method_description[0].args.args)
            else:
                registered_tasks.append(task)
    return False


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

    # this will install the package and the dependencies into the python installation
    run_command("sudo pip install {0}".format(plugin_url))
    logger.debug("installed plugin {0} and dependencies into python installation".format(plugin_name))

    # install the package to the target directory. this will also uninstall the plugin package from the python
    # installation. leaving the plugin package just inside the base dir.
    run_command("sudo pip install --no-deps -t {0} {1}".format(to_dir, plugin_url))
    logger.debug("installing plugin {0} into {1}".format(plugin_name, to_dir))


def get_plugin_simple_name(full_plugin_name):
    return full_plugin_name.split(".")[-1:][0]


def run_command(command):
    p = subprocess.Popen(command.split(" "), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    if p.returncode != 0:
        raise RuntimeError("Failed running command {0} [returncode={1}, "
                           "output={2}, error={3}]".format(command, out, err, p.returncode))
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

    path = base_dir

    for p in namespace_parts:
        path = os.path.join(path, p)
    logger.debug("plugin installation path is {0}".format(path))

    if not os.path.exists(path):
        os.makedirs(path)

    # create __init__.py files in each subfolder
    init_path = base_dir
    for p in namespace_parts:
        init_path = os.path.join(init_path, p)
        init_file = os.path.join(init_path, "__init__.py")
        if not os.path.exists(init_file):
            open(init_file, "w").close()

    return path

