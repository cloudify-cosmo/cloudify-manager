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


class MockWorkflowClient(object):

    def execute_workflow(self, workflow, plan, deployment_id=None):
        return {
            'type': 'workflow_state',
            'id': 'yokimura-yoshomati',
            'state': 'pending',
            'created': datetime.now()
        }

    def validate_workflows(self, plan):
        return {
            'status': 'valid'
        }

    def get_workflow_status(self, workflow_id):
        return {
            'state': 'terminated'
        }
