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

__author__ = 'elip'

from setuptools import setup


COSMO_CELERY_VERSION = '0.3'
COSMO_CELERY_BRANCH = 'develop'
COSMO_CELERY = \
    "https://github.com/CloudifySource/cosmo-celery-common/tarball/{0}"\
    .format(COSMO_CELERY_BRANCH)


setup(
    name='cosmo-plugin-agent-installer',
    version='0.3',
    author='elip',
    author_email='elip@gigaspaces.com',
    packages=['worker_installer'],
    license='LICENSE',
    description='Plugin for installing a Cloudify agent on a machine',
    install_requires=[
        'cosmo-celery-common',
        'fabric==1.8.3',
        'jinja2==2.7.2'
    ],
    tests_require=[
        "nose",
        "python-vagrant"
    ],
    dependency_links=["{0}#egg=cosmo-celery-common-{1}".format(
        COSMO_CELERY, COSMO_CELERY_VERSION)]
)
