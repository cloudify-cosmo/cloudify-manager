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

from manager_rest.storage_manager import get_storage_manager
from manager_rest.models import Execution


def task_state():
    return Execution.TERMINATED


class MockCeleryClient(object):

    def __enter__(self):
        self.current_instance = MockCeleryClient()
        return self.current_instance

    def __exit__(self, exc_type, exc_val, exc_tb):
        del self.current_instance

    def execute_task(self, task_name, task_queue, task_id=None, kwargs=None):
        get_storage_manager().update_execution_status(task_id,
                                                      task_state(),
                                                      '')
        return MockAsyncResult()

    def get_task_status(self, task_id):
        return 'SUCCESS'

    def get_failed_task_error(self, task_id):
        return RuntimeError('mock error')


class MockAsyncResult(object):

    def get(self, timeout=300, propagate=True):
        return None
