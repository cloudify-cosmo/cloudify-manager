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

__author__ = "idanmo"

from setuptools import setup
import os
import sys

PIP_WITH_SUDO = "PIP_SUDO"
use_sudo = PIP_WITH_SUDO in os.environ and os.environ[PIP_WITH_SUDO].lower() == "true"


def pip_install(url, use_sudo=False):
    sudo = "sudo " if use_sudo else ""
    os.system("{0}pip install {1} -q --timeout 60".format(sudo, url))

os.chdir(sys.path[0])

# The following plugins are installed using pip because their installation is required to be flat (not egg)
# as these plugins are copied from python lib in tests runtime.
pip_install("https://github.com/CloudifySource/cosmo-plugin-plugin-installer/archive/0.1.0.zip", use_sudo)
pip_install("https://github.com/CloudifySource/cosmo-plugin-riemann-configurer/archive/0.1.1.zip", use_sudo)

setup(
    name='cloudify-workflows',
    version='0.1.0',
    author='Idan Moyal',
    author_email='idan@gigaspaces.com',
    packages=['tests'],
    license='LICENSE',
    description='Cloudify workflow python tests',
    install_requires=[
        "celery",
        "bernhard",
        "nose"
    ],
)