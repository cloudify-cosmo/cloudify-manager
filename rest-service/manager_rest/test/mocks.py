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

__author__ = 'dan'

from datetime import datetime
from manager_rest.storage_manager import get_storage_manager
from manager_rest.models import Execution


def get_workflow_status(wfid):
    return Execution.TERMINATED


class MockWorkflowClient(object):

    @staticmethod
    def execute_workflow(name, workflow,
                         blueprint_id, deployment_id,
                         execution_id):
        return {
            'type': 'workflow_state',
            'id': 'yokimura-yoshomati',
            'state': 'pending',
            'error': None,
            'created': datetime.now()
        }

    def cancel_workflow(self, workflow_id):
        return self.execute_workflow(None, None, None, None, None)


class MockCeleryClient(object):

    def execute_task(self, task_name, task_queue, task_id=None, kwargs=None):
        get_storage_manager().update_execution_status(task_id,
                                                      Execution.TERMINATED,
                                                      '')
        return MockAsyncResult()

    def get_task_status(self, task_id):
        return 'SUCCESS'

    def get_failed_task_error(self, task_id):
        return RuntimeError('mock error')


class MockAsyncResult(object):

    def get(self, timeout=300, propagate=True):
        return None
