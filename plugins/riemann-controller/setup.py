#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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


from setuptools import setup


setup(
    name='cloudify-riemann-controller-plugin',
    version='3.1a1',
    author='Gigaspaces',
    author_email='cosmo-admin@gigaspaces.com',
    packages=['riemann_controller',
              'riemann_controller.resources'],
    package_data={'riemann_controller.resources': [
        'manager.config',
        'deployment.config'
    ]},
    license='LICENSE',
    description='Plugin for creating riemann configuration'
                ' based on blueprint policies and starting '
                ' a riemann core with generated configuration',
    install_requires=[
        'cloudify-plugins-common==3.1a1',
        'jinja2==2.7.2',
        'bernhard==0.1.1'
    ],
)
