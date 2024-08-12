########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
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
import sys

from setuptools import setup, find_packages

install_requires = [
    'cryptography==43.0.0',
    'packaging',
    'psycopg2',
    'python-dateutil',
    'pytz',
    'retrying',
]

if sys.version_info.major == 3 and sys.version_info.minor == 6:
    install_requires += [
        'cloudify-agent[fabric,kerberos]',  # Exclude celery for python 3.6
        'cloudify-common[dispatcher,snmp]',
    ]
else:
    install_requires += [
        'cloudify-agent[celery,fabric,kerberos]',
        'cloudify-common[dispatcher,snmp]',
    ]

setup(
    name='cloudify-mgmtworker',
    version='7.1.0.dev1',
    author='Cloudify',
    author_email='cosmo-admin@cloudify.co',
    packages=find_packages(),
    license='LICENSE',
    description='Cloudify Management Worker',
    install_requires=install_requires,
)
