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

__author__ = 'dank'

from setuptools import setup


PLUGINS_COMMON_VERSION = "3.0"
PLUGINS_COMMON_BRANCH = "develop"
PLUGINS_COMMON = "https://github.com/cloudify-cosmo/cloudify-plugins-common" \
                 "/tarball/{0}#egg=cloudify-plugins-common-{1}".format(
                     PLUGINS_COMMON_BRANCH, PLUGINS_COMMON_VERSION)


setup(
    name='cloudify-workflows',
    version='3.0',
    author='elip',
    author_email='elip@gigaspaces.com',
    packages=['workflows'],
    license='LICENSE',
    description='Default cloudify workflows',
    install_requires=[
        'cloudify-plugins-common',
    ],
    tests_require=[
        "nose",
    ],
    dependency_links=[PLUGINS_COMMON]
)
