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

import requests
import json
import config
import time


class WorkflowServiceError(Exception):

    def __init__(self, status_code, json):
        self.status_code = status_code
        self.json = json


class WorkflowClient(object):

    def __init__(self):
        self.workflow_service_base_uri = \
            config.instance().workflow_service_base_uri

    def execute_workflow(self, name, workflow, plan, blueprint_id=None,
                         deployment_id=None, execution_id=None):
        tags = {}
        if deployment_id is not None:
            tags['deployment_id'] = deployment_id  # for workflow events
        response = requests.post(
            '{0}/workflows'.format(self.workflow_service_base_uri),
            json.dumps({
                'radial': workflow,
                'fields': {
                    'plan': plan,
                    'workflow_id': name,
                    'blueprint_id': blueprint_id,
                    'deployment_id': deployment_id,
                    'execution_id': execution_id
                },
                'tags': tags
            }))
        if response.status_code != 201:
            raise WorkflowServiceError(response.status_code, response.json())
        return response.json()

    def validate_workflows(self, plan):
        prepare_plan_participant_workflow = '''define validate
    prepare_plan plan: $plan
        '''
        execution_response = self.execute_workflow(
            'validate', prepare_plan_participant_workflow, plan)
        response = {'state': 'pending'}
        # TODO timeout
        while (response['state'] != 'terminated') and \
              (response['state'] != 'failed'):
            response = self.get_workflow_status(execution_response['id'])
            time.sleep(1)
        # This is good
        if response['state'] == 'terminated':
            return {'status': 'valid'}
        # This is bad
        else:
            return {'status': 'invalid'}

    def get_workflow_status(self, workflow_id):
        response = requests.get('{0}/workflows/{1}'.format(
            self.workflow_service_base_uri, workflow_id))
        if response.status_code != 200:
            raise WorkflowServiceError(response.status_code, response.json())
        return response.json()


def workflow_client():
    if config.instance().test_mode:
        from test.mocks import MockWorkflowClient
        return MockWorkflowClient()
    else:
        return WorkflowClient()
