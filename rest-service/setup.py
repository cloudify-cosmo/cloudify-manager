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

import os

from setuptools import setup, find_packages

install_requires = [
    'Flask==0.10.1',
    'flask-restful==0.2.5',
    'flask-restful-swagger==0.12',
    'flask-sqlalchemy==2.1',
    'flask-security==1.7.5',
    'flask-migrate==2.0.3',
    'ldappy',
    'supervise==1.1.1',
    'cloudify-dsl-parser==4.3.4',
    'requests>=2.7.0,<3.0.0',
    'gunicorn==18.0',
    'PyYAML==3.10',
    'elasticsearch==1.6.0',
    'celery==3.1.17',
    'psutil==3.3.0',
    'jsonpickle==0.9.2',
    'wagon[venv]==0.6.3',
    'python-dateutil==2.5.3',
    'voluptuous==0.9.3',
    'toolz==0.8.2',
    'pyrabbit==1.1.0',
]


if os.environ.get('REST_SERVICE_BUILD'):
    # since psycopg2 installation require postgres,
    # we're adding it only to the build process,
    # where we know there is postgresql..
    # tests will use pg8000, which doesn't require postgres
    install_requires.append('psycopg2==2.6.2')


setup(
    name='cloudify-rest-service',
    version='4.3.4',
    author='Gigaspaces',
    author_email='cosmo-admin@gigaspaces.com',
    packages=find_packages(
        include='manager_rest*', exclude=('manager_rest.test*',)
    ),
    package_data={'manager_rest': ['VERSION']},
    license='LICENSE',
    description='Cloudify manager rest service',
    zip_safe=False,
    install_requires=install_requires,
    extras_require={
        'dbus': ['dbus-python==1.2.4'],
        },
    )
