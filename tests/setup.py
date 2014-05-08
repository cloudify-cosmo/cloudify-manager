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

REST_CLIENT_VERSION = '3.0b1'
REST_CLIENT_BRANCH = '3.0b1'
REST_CLIENT = 'https://github.com/cloudify-cosmo/cloudify-rest-client' \
              '/tarball/{0}#egg=cloudify-rest-client-{1}'.format(
                  REST_CLIENT_BRANCH, REST_CLIENT_VERSION)

PLUGINS_COMMON_VERSION = "3.0b1"
PLUGINS_COMMON_BRANCH = "3.0b1"
PLUGINS_COMMON = "https://github.com/cloudify-cosmo/cloudify-plugins-common" \
                 "/tarball/{0}#egg=cloudify-plugins-common-{1}".format(
                     PLUGINS_COMMON_BRANCH, PLUGINS_COMMON_VERSION)

setup(
    name='cloudify-tests',
    version='3.0b1',
    author='Idan Moyal',
    author_email='idan@gigaspaces.com',
    packages=['plugins'],
    license='LICENSE',
    description='Cloudify workflow python tests',
    zip_safe=False,
    install_requires=[
        "cloudify-plugins-common",
        "cloudify-rest-client",
        "pika==0.9.13",
        "bernhard==0.1.0",
        'elasticsearch==1.0.0'
    ],
    test_requires=[
        "nose"
    ],
    dependency_links=[PLUGINS_COMMON,
                      REST_CLIENT]
)
