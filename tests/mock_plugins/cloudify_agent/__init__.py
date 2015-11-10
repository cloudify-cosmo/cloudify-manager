########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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


import abc
import sys

from cloudify.exceptions import NonRecoverableError
from cloudify.workflows import tasks


class PluginInstaller(object):

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def install(self, plugins):
        pass

    @abc.abstractmethod
    def uninstall(self, plugins):
        pass

VIRTUALENV = sys.prefix


def mock_verify_worker_alive(name, *args):
    if 'non_existent' in name:
        raise NonRecoverableError('AGENT_ALIVE_FAIL')


# This is needed because in this
# environment, all tasks are sent to
# the management worker, and handled by
# different consumers. The original method
# asserts that tasks are being sent to
# different workers
tasks.verify_worker_alive = mock_verify_worker_alive
