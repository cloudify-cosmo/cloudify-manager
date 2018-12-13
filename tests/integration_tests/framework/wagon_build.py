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

from integration_tests.framework.docker_interface import DockerInterface
from integration_tests.resources.dockerfiles import centos as dockerfile

# This message is always the last message when a wagon build is finished.
WAGON_BUILD_TIMEOUT = 600
WAGON_BUILD_DOCKER_IMAGE_NAME = 'wagonbuilder:latest'
DOCKER_CONTAINER_BUILD_DIR = '/build'


class WagonBuildError(RuntimeError):
    def __init__(self, errors):
        super(WagonBuildError, self).__init__("Failed to build wagon.")
        self.errors = errors


class WagonBuilderMixin(DockerInterface):

    @property
    def wagon_build_time_limit(self):
        """Max time it should take to build the wagon."""
        return WAGON_BUILD_TIMEOUT

    @property
    def docker_image_name(self):
        """The name of the Docker image that is used to build
        the plugin wagon.
        """
        return WAGON_BUILD_DOCKER_IMAGE_NAME

    @property
    def plugin_root_directory(self):
        """ Path to the plugin root directory."""
        raise NotImplementedError('Implemented by subclass.')

    @property
    def docker_target_folder(self):
        """Where to mount the docker local folder on the docker container.
        """
        return DOCKER_CONTAINER_BUILD_DIR

    @property
    def docker_volume_mapping(self):
        """A volume mapping for mounting a local directory in a container.
        The wagon will be here at the end of the build.
        """
        return {
            self.plugin_root_directory: {
                'bind': self.docker_target_folder,
                'mode': 'rw'
            }
        }

    @property
    def wagon_builder_image_exists(self):
        """Check if the docker image already exists."""
        return self.docker_image_name in self.docker_images

    def build_docker_image(self):
        """Build the wagon builder docker image."""
        return self.build_image(dockerfile, self.docker_image_name)

    def build_wagon(self):
        if not self.wagon_builder_image_exists:
            self.build_docker_image()
        container = self.run_container(self.docker_image_name,
                                       volumes=self.docker_volume_mapping,
                                       detach=True)
        response = container.wait(timeout=self.wagon_build_time_limit)
        if response['StatusCode'] != 0:
            raise WagonBuildError(response)
