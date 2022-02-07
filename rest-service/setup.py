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
    'flask-restful-swagger>=0.20.0',
    'flask-sqlalchemy>2.3.1,<2.5',
    'flask-security',
    'flask-login>=0.4.1,<0.5',
    'flask-migrate>2.2,<2.6',
    'cloudify-common==6.3.1.dev1',
    'requests>=2.7.0,<3',
    'gunicorn',
    'pyyaml',
    'psutil>=5.7,<5.8',
    'virtualenv>=15.1.0,<16',
    'wagon>=0.9.1',
    'python-dateutil>=2.8.1,<3',
    'voluptuous>=0.9.3,<0.10',
    'pika>=1.1.0,<1.2.0',
    'cffi>=1.14,<1.15',
    'cryptography>=3.3,<3.4',
    'psycopg2',
    'pytz',
    'packaging>=17,<18',
    'jsonschema>=3,<4',
    'SQLAlchemy>=1.4,<2',
    'cachetools>=3,<4',
    'email-validator>1,<2',
    'werkzeug>1,<2',
    'itsdangerous>1,<2',
]


setup(
    name='cloudify-rest-service',
    version='6.3.1.dev1',
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
    entry_points={
        'console_scripts': [
            'update-plugin-imports = '
            'manager_rest.shell.update_plugin_imports:main',
            'substitute-import-lines = '
            'manager_rest.shell.substitute_import_lines:main',
        ]
    },
    extras_require={
        'dbus': ['dbus-python==1.2.4'],
    }
)
