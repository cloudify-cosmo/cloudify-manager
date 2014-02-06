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

__author__ = 'dank'

from setuptools import setup

REST_CLIENT_VERSION = '0.3'
REST_CLIENT_BRANCH = 'develop'
REST_CLIENT =\
    "https://github.com/CloudifySource/cosmo-manager-rest-client/tarball/{0}"\
    .format(REST_CLIENT_BRANCH)

version = '0.3'

setup(
    name='cloudify-hello-world-sanity',
    version=version,
    author='dank',
    author_email='dank@gigaspaces.com',
    license='LICENSE',
    description='Sanity test executor for cloudify-hello-world',
    install_requires=[
        'PyYAML==3.10',
        'path.py==5.1',
        'sh==1.09',
        'requests==2.2.1',
        'cosmo-manager-rest-client'
    ],
    dependency_links=["{0}#egg=cosmo-manager-rest-client-{1}"
                      .format(REST_CLIENT, REST_CLIENT_VERSION)]
)
