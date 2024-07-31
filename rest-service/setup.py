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
    'Flask>2,<2.3',
    'PyYAML',
    'SQLAlchemy>=1.4,<2',
    'boto3>1,<2',
    'cachetools>=3,<4',
    'cffi>=1,<2',
    'cloudify-common[dispatcher]',
    'cryptography',
    'distro',
    'email-validator>2',
    'flask-migrate>=4.0.5,<4.0.6',
    'flask-restful>=0.3.10',
    'flask-security>=3.0.0',
    'flask-sqlalchemy>=2.5.1,<2.6',
    'jsonschema',
    'packaging',
    'pika',
    'psutil>5,<6',
    'psycopg2',
    'pydantic<2',
    'python-dateutil>=2.8.1,<3',
    'pytz',
    'requests>=2.32.0,<3.0.0',
    'retrying',
    'wagon>=0.12',
    'werkzeug>=3.0.1,<4',
]


setup(
    name='cloudify-rest-service',
    version='7.1.0.dev1',
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
)
