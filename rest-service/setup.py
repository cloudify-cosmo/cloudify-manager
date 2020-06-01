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

from setuptools import setup, find_packages

install_requires = [
    'Flask>1,<2',
    'flask-restful>0.3.5,<0.4.0',
    'flask-restful-swagger==0.20.1',
    'flask-sqlalchemy>2.3.1,<2.5.0',
    'flask-security==3.0.0',
    'flask-login==0.4.1',
    'flask-migrate>2.2.0,<2.6.0',
    'cloudify-common==5.1.0.dev1',
    'requests>=2.7.0,<3.0.0',
    'gunicorn==18.0',
    'PyYAML==3.12',
    'psutil==3.3.0',
    'virtualenv==15.1.0',
    'wagon>=0.9.1',
    'python-dateutil==2.5.3',
    'voluptuous==0.9.3',
    'toolz==0.8.2',
    'pika==0.11.2',
    'cryptography==2.5.0',
    'psycopg2==2.7.4',
    'pytz==2018.4',
    'packaging==17.1',
    'jsonschema==3.0.0',
    'SQLAlchemy==1.2.18',
    'cachetools==3.1.0',
    'email-validator>1.0.0,<2.0.0'
]


setup(
    name='cloudify-rest-service',
    version='5.1.0.dev1',
    author='Cloudify',
    author_email='cosmo-admin@cloudify.co',
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
    }
)
