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

from setuptools import setup


setup(
    name='cloudify-workflows',
    version='4.4.dev1',
    author='elip',
    author_email='elip@gigaspaces.com',
    packages=[
        'cloudify_system_workflows',
        'cloudify_system_workflows.snapshots'
    ],
    license='LICENSE',
    description='Various Cloudify Workflows',
    install_requires=[
        'cloudify-plugins-common==4.4.dev1',
        'elasticsearch==1.6.0',
        'retrying==1.3.3',
        'psycopg2==2.7',
        'cryptography==2.1.4',
    ]
)
