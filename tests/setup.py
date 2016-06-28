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
    version='3.5a1',
    author='Gigaspaces',
    author_email='cosmo-admin@gigaspaces.com',
    packages=[
        'mock_plugins',
        'mock_plugins.cloudify_agent',
        'mock_plugins.cloudify_agent.installer',
        'mock_plugins.cloudmock',
        'mock_plugins.connection_configurer_mock',
        'mock_plugins.context_plugin',
        'mock_plugins.get_attribute',
        'mock_plugins.mock_agent_plugin',
        'mock_plugins.mock_workflows',
        'mock_plugins.target_aware_mock',
        'mock_plugins.testmockoperations',
        'testenv',
        'testenv.processes'
    ],
    description='Cloudify Integration Tests',
    zip_safe=False,
    install_requires=[
        'cloudify-dsl-parser==3.5a1',
        'cloudify-rest-client==3.5a1',
        'cloudify-plugins-common==3.5a1',
        'cloudify-diamond-plugin==1.3.3',
        'cloudify-script-plugin==1.4',
        'pika==0.9.14',
        'elasticsearch==1.6.0',
        'celery==3.1.17',
        'fasteners==0.13.0'
    ],
    entry_points={
        'nose.plugins.0.10': [
            'suitesplitter = testenv.suite_splitter:SuiteSplitter',
        ]
    },
)
