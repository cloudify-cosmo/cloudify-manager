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

import os
import urllib2
import tarfile
import zipfile
import shutil
import subprocess
from subprocess import CalledProcessError
from cosmo.celery import celery, get_cosmo_properties
from celery.utils.log import get_task_logger
from os.path import expanduser


TAR_GZ_SUFFIX = "tar.gz"
ZIP_SUFFIX = "zip"
PLUGIN_FILE_PREFIX = "plugin"
REQUIREMENTS_FILE = "requirements.txt"
TASKS_MODULE = "tasks.py"

logger = get_task_logger(__name__)


@celery.task
def install(plugin, __cloudify_id, **kwargs):
    """
    Installs plugin as celery task according to the provided plugins details.
    plugin parameter is expected to be in the following format: { name: "...", url: "..." }
    The plugin's url should be an http url pointing to either a zip or tar.gz file and the compressed file
    should contain a "tasks.py" module with celery tasks.
    """

    logger.debug("installing plugin [%s] in host [%s]", plugin, __cloudify_id)

    name = plugin["name"]
    url = plugin["url"]

    management_ip = get_cosmo_properties()["management_ip"]
    if management_ip != None:
        url = url.replace("#{plugin_repository}", "http://{0}:{1}".format(management_ip, "53229"))

    extract = None
    plugin_file = None

    if url.endswith(TAR_GZ_SUFFIX):
        extract = extract_targz
        plugin_file = "{0}.{1}".format(PLUGIN_FILE_PREFIX, TAR_GZ_SUFFIX)
    elif url.endswith(ZIP_SUFFIX):
        extract = extract_zip
        plugin_file = "{0}.{1}".format(PLUGIN_FILE_PREFIX, ZIP_SUFFIX)
    else:
        raise RuntimeError("archive extension not supported - supported extensions: {0}".format([TAR_GZ_SUFFIX, ZIP_SUFFIX]))

    plugin_path = create_plugin_path(name)
    plugin_file_path = os.path.join(plugin_path, plugin_file)
    # from this stage - on failure remove the created plugin path
    try:
        # TODO: download_plugin can be invoked as a celery subtask (asynchronous)
        download_plugin(url, plugin_file_path)
        extract(plugin_file_path, plugin_path)
        if not os.path.exists(os.path.join(plugin_path, TASKS_MODULE)):
            raise RuntimeError("plugin does not contain a '{0}' module".format(TASKS_MODULE))
        os.remove(plugin_file_path)

        requirements_file = os.path.join(plugin_path, REQUIREMENTS_FILE)
        if os.path.exists(requirements_file):
            logger.info('installing packages from requirements.txt file')
            os.chdir(plugin_path)
            command = ["sudo", "pip", "--default-timeout=120", "install", "-r", requirements_file]
            p = subprocess.Popen(command)
            out, err = p.communicate()
            print("command={0}, output={1}, err={2}".format(command, out, err))
            if p.returncode != 0:
                raise RuntimeError("unable to install requirements.txt [returncode={0}]".format(p.returncode))
    except (CalledProcessError, Exception) as error:
        subprocess.Popen(["sudo", "rm", "-rf", plugin_path])
        raise error


@celery.task
def verify_plugin(worker_id, plugin_name, **kwargs):
    p = subprocess.Popen(["celery", "inspect", "registered", "-d", worker_id, "--no-color"], stdout=subprocess.PIPE)
    out, err = p.communicate()

    if p.returncode != 0:
        raise RuntimeError("unable to get celery worker registered tasks [returncode={0}]".format(p.returncode))

    lines = out.splitlines()
    registered_tasks = list()
    for line in lines:
        processed_line = line.strip()
        if processed_line.startswith("*"):
            task = processed_line[1:].strip()
            if task.startswith(plugin_name):
                return True
            else:
                registered_tasks.append(task)
    return False


def download_plugin(url, path):
    """
    Downloads plugin from the provided url and saves as path.
    """
    try:
        response = urllib2.urlopen(url)
        with open(path, "w") as f: f.write(response.read())
    except ValueError as error:
        if not os.path.exists(url):
            raise error
        shutil.copyfile(url, path)


def create_plugin_path(name):
    """
    Creates a path the plugin will be stored in. "cloudify.plugins.host.installer" would be stored in:
    "app/cloudify/plugins/host/installer". In addition, "__init.py__" files will be created in each of the
    path's sub directories.
    An exception will be raised if the plugin's directory already exists.
    """
    home_dir = expanduser("~")
    cosmo_path = os.path.join(home_dir, "cosmo")
    path = cosmo_path
    path_values = name.split(".")

    for p in path_values:
        path = os.path.join(path, p)

    if os.path.exists(path):
        raise RuntimeError("plugin [{0}] is already installed".format(name))

    os.makedirs(path)

    # create __init__.py files in each subfolder
    init_path = cosmo_path
    for p in path_values:
        init_path = os.path.join(init_path, p)
        init_file = os.path.join(init_path, "__init__.py")
        if not os.path.exists(init_file):
            open(init_file, "w").close()

    return path


def extract_zip(zipfile_path, destination_path):
    zfile = zipfile.ZipFile(zipfile_path, mode='r')
    for f in zfile.namelist():
        zfile.extract(f, destination_path)


def extract_targz(targzfile_path, destination_path):
    tfile = tarfile.open(targzfile_path, "r:gz")
    tfile.extractall(destination_path)


def test():
    plugin = {"name": "cloudify.python-webserver", "url": "http://localhost/python-webserver.tar.gz"}
    install(plugin)

