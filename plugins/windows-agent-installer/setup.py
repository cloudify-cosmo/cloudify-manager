#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

__author__ = 'nirc'

from setuptools import setup


setup(
    name='cloudify-windows-agent-installer-plugin',
    version='3.1a4',
    author='nirc',
    author_email='nirc@gigaspaces.com',
    packages=['windows_agent_installer'],
    license='LICENSE',
    description='Plugin for installing a Cloudify agent on a windows machine',
    install_requires=[
        'cloudify-plugins-common==3.1a4',
        'pywinrm==0.0.2dev',
    ],
    tests_require=[
        'nose',
        'python-novaclient==2.17.0',
        'python-neutronclient==2.3.4',
        'mock'
    ]
)
