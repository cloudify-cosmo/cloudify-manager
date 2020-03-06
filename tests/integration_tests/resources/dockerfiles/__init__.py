########
# Copyright (c) 2018 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
from io import StringIO
from tempfile import mkdtemp
from zipfile import ZipFile

import requests


WAGON_BUILD_CONTAINERS = (
    'https://github.com/cloudify-cosmo/'
    'cloudify-wagon-build-containers/archive/master.zip'
)

RESOURCES = os.path.abspath(
    os.path.join(
        os.path.dirname(
            os.path.realpath(__file__)), '..'))


def get_dockerfile_from_git(platform):
    directory = mkdtemp()
    containers_zip = os.path.join(directory, 'containers.zip')
    with requests.get(WAGON_BUILD_CONTAINERS, stream=True) as resp:
        resp.raise_for_status()
        with open(containers_zip, 'wb') as f:
            for part in resp.iter_content(chunk_size=8192):
                if not part:
                    continue
                f.write(part)
    zipped_containers = ZipFile(containers_zip)
    zipped_containers.extractall(directory)
    return os.path.join(
        directory, 'cloudify-wagon-build-containers-master', platform)


def get_dockerfile_from_resources(directory):
    return os.path.join(RESOURCES, 'dockerfiles', directory)


class DockerfileIO(StringIO):

    @property
    def name(self):
        return 'Dockerfile'


centos = get_dockerfile_from_git('centos')
agent_host = get_dockerfile_from_resources('cloudify_agent')
