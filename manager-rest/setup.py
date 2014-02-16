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

__author__ = 'dank'

from setuptools import setup

DSL_PARSER_VERSION = '0.3'
DSL_PARSER_BRANCH = 'feature/CLOUDIFY-2475-dynamic-management-plugins-and-worker-per-deployment'
DSL_PARSER = 'https://github.com/CloudifySource/cosmo-plugin-dsl-parser/'\
             'tarball/{0}#egg=cosmo-plugin-dsl-parser-{1}'\
             .format(DSL_PARSER_BRANCH, DSL_PARSER_VERSION)

setup(
    name='cloudify-manager-rest',
    version='0.3',
    author='Dan Kilman',
    author_email='dank@gigaspaces.com',
    packages=['manager_rest'],
    license='LICENSE',
    description='Cloudify manager rest server',
    zip_safe=False,
    install_requires=[
        'six',
        'Flask',
        'flask-restful==0.2.5',
        'flask-restful-swagger',
        'cosmo-plugin-dsl-parser',
        'requests',
        'bernhard',
        'gunicorn==18.0',
        'PyYAML==3.10',
        'elasticsearch==0.4.4'
    ],
    tests_require=['nose'],
    dependency_links=[DSL_PARSER]
)
