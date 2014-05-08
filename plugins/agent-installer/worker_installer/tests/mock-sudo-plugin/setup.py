#########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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

__author__ = 'idanmo'

from setuptools import setup

PLUGINS_COMMON_VERSION = "3.0b1"
PLUGINS_COMMON_BRANCH = "master"
PLUGINS_COMMON = "https://github.com/cloudify-cosmo" \
                 "/cloudify-plugins-common/tarball/{0}" \
    .format(PLUGINS_COMMON_BRANCH)

setup(
    name='mock-sudo-plugin',
    version='1.0',
    author='idanmo',
    author_email='idan@gigaspaces.com',
    packages=['sudo_plugin'],
    license='LICENSE',
    description='Plugin for running simple bash scripts',
    install_requires=[
        "cloudify-plugins-common"
    ],
    dependency_links=["{0}#egg=cloudify-plugins-common-{1}"
                      .format(PLUGINS_COMMON, PLUGINS_COMMON_VERSION)])
