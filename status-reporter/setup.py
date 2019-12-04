#########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
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

from setuptools import setup, find_packages


setup(
    name='cloudify-status-reporter',
    version='5.0.5.dev1',
    author='Cloudify',
    author_email='cosmo-admin@cloudify.co',
    packages=find_packages(),
    license='LICENSE',
    description='Service for reporting the status of a Cloudify component.',
    entry_points={
        'console_scripts': [
            'cloudify_manager_reporter = '
            'status_reporter.manager_reporter:main',
            'cloudify_rabbitmq_reporter = '
            'status_reporter.rabbitmq_reporter:main',
            'cloudify_postgresql_reporter = '
            'status_reporter.postgresql_reporter:main'
        ]
    },
    install_requires=[
        'requests>=2.7.0,<3.0.0',
        'ruamel.yaml==0.15.94',
        'cloudify-common==5.0.5.dev1',
        'dbus-python==1.2.4'
    ]
)
