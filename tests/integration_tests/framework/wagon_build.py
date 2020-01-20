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

from docker.errors import APIError as DockerAPIError

from integration_tests.framework.docker_interface import DockerInterface
from integration_tests.resources.dockerfiles import centos as dockerfile

# This message is always the last message when a wagon build is finished.
WAGON_BUILD_TIMEOUT = 600
WAGON_BUILD_DOCKER_REPO_NAME = 'cloudifyplatform'
WAGON_BUILD_DOCKER_IMAGE_NAME = 'cloudify-centos-7-wagon-builder'
WAGON_BUILD_DOCKER_TAG_NAME = 'latest'
DOCKER_CONTAINER_BUILD_DIR = '/packaging'


class WagonBuildError(RuntimeError):
    def __init__(self, errors):
        message = "Failed to build wagon: {0}".format(errors)
        super(WagonBuildError, self).__init__(message)
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
    def docker_image_tag(self):
        """The tag of the Docker image that is used to build
        the plugin wagon.
        """
        return WAGON_BUILD_DOCKER_TAG_NAME

    @property
    def docker_image_name_with_tag(self):
        return '{repo}:{version}'.format(
            repo=self.docker_image_name_with_repo,
            version=self.docker_image_tag
        )

    @property
    def docker_image_name_with_repo(self):
        return '{repo}/{image}'.format(
            repo=self.docker_repo_name,
            image=self.docker_image_name)

    @property
    def docker_repo_name(self):
        """The repo of the Docker image that is used to build
        the plugin wagon.
        """
        return WAGON_BUILD_DOCKER_REPO_NAME

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

    def check_if_has_image_locally(self):
        """Check if the docker image already exists."""
        return any(
            self.docker_image_name_with_tag in t
            for t in self.list_image_tags())

    def get_docker_image(self):
        try:
            self.pull_image(
                repository=self.docker_image_name_with_repo,
                tag=self.docker_image_tag)
        except DockerAPIError:
            self.build_image(dockerfile, self.docker_image_name)
        if not self.check_if_has_image_locally():
            raise WagonBuildError('{0} not in {1}'.format(
                self.docker_image_name_with_tag, self.list_image_tags()))

    def prepare_docker_image(self):
        if not self.check_if_has_image_locally():
            self.get_docker_image()

    def build_wagon(self, logger):
        self.prepare_docker_image()
        container = self.run_container(
            self.docker_image_name_with_repo,
            volumes=self.docker_volume_mapping,
            detach=True)
        response = container.wait(timeout=self.wagon_build_time_limit)
        for msg in container.logs(stream=True):
            logger.info(msg)
        if response['StatusCode'] != 0:
            raise WagonBuildError(response)
        container.stop()
        container.remove()
