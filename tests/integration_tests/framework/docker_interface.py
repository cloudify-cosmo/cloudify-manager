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

import docker


class DockerInterface(object):

    @staticmethod
    def get_docker_client(docker_base_url=None, docker_port='2375'):
        """Get a Docker Py client.
        docker.get_env does not work,
        because we do not specify the port in our DOCKER_HOST env variable.
        """
        docker_base_url = \
            docker_base_url or '{0}:{1}'.format(
                os.getenv('DOCKER_HOST'), docker_port)
        return docker.DockerClient(base_url=docker_base_url)

    @property
    def docker_client(self):
        return self.get_docker_client()

    @property
    def docker_images(self):
        return [image.tags for image in self.docker_client.images.list()]

    def build_image(self, dockerfile_object, image_name):
        return self.docker_client.images.build(fileobj=dockerfile_object,
                                               tag=image_name)

    def run_container(self, image_name, **kwargs):
        """Start building the wagon."""
        return self.docker_client.containers.run(image_name, **kwargs)
