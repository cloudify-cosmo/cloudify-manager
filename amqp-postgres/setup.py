########
# Copyright (c) 2018 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
############


from setuptools import setup

setup(
    name='cloudify-amqp-postgres',
    version='4.4',
    author='Cloudify',
    author_email='cosmo-admin@gigaspaces.com',
    packages=['amqp_postgres'],
    entry_points={
        'console_scripts': [
            'cloudify-amqp-postgres = amqp_postgres.main:main',
        ]
    },
    install_requires=[
        'pika==0.11.2',
        'psycopg2-binary==2.7.4',
        'cloudify-common==4.4',
        'cloudify-rest-service==4.4'
    ],
)
