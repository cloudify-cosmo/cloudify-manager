#########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
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
from os.path import join

from setuptools import setup, find_packages


# This makes sure to include all the config/scripts directories
# in the python package
def package_files(directory):
    paths = []
    for (path, directories, filenames) in os.walk(directory):
        for filename in filenames:
            if filename.endswith('.pyc'):
                continue
            paths.append(join('..', path, filename))
    return paths


extra_files = package_files('cfy_manager')
extra_files.append(join('..', 'config.yaml'))


setup(
    name='cloudify-manager-install',
    version='4.3.dev1',
    author='Cloudify',
    author_email='cosmo-admin@cloudify.co',
    packages=find_packages(),
    license='LICENSE',
    description='Local install of a cloudify manager',
    entry_points={
        'console_scripts': [
            'cfy_install = cfy_manager.main:install',
            'cfy_remove = cfy_manager.main:remove',
            'cfy_config = cfy_manager.main:configure'
        ]
    },
    zip_safe=False,
    package_data={'': extra_files},
    install_requires=[
        'PyYAML==3.10',
        'Jinja2==2.7.2',
        'argh==0.26.2'
    ]
)
