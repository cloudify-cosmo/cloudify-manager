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

from setuptools import setup

setup(
    name='cloudify-integration-tests',
    version='4.2',
    author='Gigaspaces',
    author_email='cosmo-admin@gigaspaces.com',
    packages=[
        'integration_tests',
        'integration_tests_plugins',
    ],
    description='Cloudify Integration Tests',
    zip_safe=False,
    install_requires=[
        'pika==0.11.2',
        'elasticsearch==1.6.0',
        'celery==3.1.17',
        'fasteners==0.13.0',
        'sh==1.11',
        'pg8000==1.10.6',
        'awscli==1.11.14',
        'docl',
    ],
    entry_points={
        'nose.plugins.0.10': [
            'suitesplitter = integration_tests.framework.'
            'suite_splitter:SuiteSplitter',
        ]
    },
)
