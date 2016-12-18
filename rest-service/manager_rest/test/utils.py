#########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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

import tarfile
from contextlib import GeneratorContextManager
from functools import partial
from functools import wraps
from os import path, getcwd

from manager_rest.storage import models


def get_resource(resource):

    """
    Gets the path for the provided resource.
    :param resource: resource name relative to /resources.
    """
    import resources
    resources_path = path.dirname(resources.__file__)
    resource_path = path.join(resources_path, resource)
    if not path.exists(resource_path):
        raise RuntimeError("Resource '{0}' not found in: {1}".format(
            resource, resource_path))
    return resource_path


def tar_blueprint(blueprint_path, dest_dir):
    """
    creates a tar archive out of a blueprint dir.

    :param blueprint_path: the path to the blueprint.
    :param dest_dir: destination dir for the path
    :return: the path for the dir.
    """
    blueprint_path = path.expanduser(blueprint_path)
    app_name = path.basename(path.splitext(blueprint_path)[0])
    blueprint_directory = path.dirname(blueprint_path) or getcwd()
    return tar_file(blueprint_directory, dest_dir, app_name)


def tar_file(file_to_tar, destination_dir, tar_name=''):
    """
    tar a file into a desintation dir.
    :param file_to_tar:
    :param destination_dir:
    :param tar_name: optional tar name.
    :return:
    """
    tar_name = tar_name or path.basename(file_to_tar)
    tar_path = path.join(destination_dir, '{0}.tar.gz'.format(tar_name))
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(file_to_tar, arcname=tar_name)
    return tar_path


class validate_execution_transitions(object):

    def __init__(self):
        self._original_valid_transition = models.Execution.VALID_TRANSITIONS.copy()

    @staticmethod
    def _enter(new_transition):
        new_transition = new_transition or {k: set(models.Execution.STATES) - set(k)
                                            for k in models.Execution.STATES}
        models.Execution.VALID_TRANSITIONS.clear()
        models.Execution.VALID_TRANSITIONS.update(new_transition)

    def __enter__(self, new_transition=None):
        self._enter(new_transition)

    def _exit(self):
        models.Execution.VALID_TRANSITIONS.clear()
        models.Execution.VALID_TRANSITIONS.update(self._original_valid_transition)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._exit()

    def __call__(self, func=None, new_transition=None, **kwargs):
        if func is None:
            return partial(self.__call__,
                           func=self.__call__,
                           new_transition=new_transition,
                           **kwargs)

        @wraps(func)
        def _wrapper(*args, **kwargs):
            self._enter(new_transition)
            func(*args, **kwargs)
            self._exit()
        return _wrapper
