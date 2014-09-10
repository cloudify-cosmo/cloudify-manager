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
import shutil
import tempfile
import sys
from os import path

import pip

from cloudify.utils import LocalCommandRunner


__author__ = 'elip'


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
        return LocalCommandRunner().run('cmd.exe /c "{0} {1} {2}"'.format(
            sys.executable,
            path.join(path.dirname(__file__), 'extract_package_name.py'),
            plugin_dir)).std_out
    finally:
        os.chdir(previous_cwd)
        if fetch_plugin_from_pip_by_url:
            shutil.rmtree(plugin_dir)


def extract_module_paths(module_name):

    module_paths = []
    files = LocalCommandRunner()\
        .run('cmd /c "{0}\Scripts\pip.exe show -f {1}"'
             .format(sys.prefix, module_name)).std_out.splitlines()
    for module in files:
        if module.endswith(".py") and "__init__" not in module:
            if module.endswith("-script.py"):
                last_dir_occurence = module.rfind("\\")
                if last_dir_occurence != -1:
                    script_name =\
                        module[last_dir_occurence+1:-len("-script.py")]
                    exe_file = "{0}\\{1}.exe".format(
                        module[:last_dir_occurence], script_name)
                    if exe_file in files:
                        # file is a console script "entry_point"
                        pass

            # the files paths are relative to the package __init__.py file.
            module_paths.append(
                module.replace("..\\", "").replace("\\", ".")
                .replace(".py", "")
                .strip())
    return ','.join(module_paths)
