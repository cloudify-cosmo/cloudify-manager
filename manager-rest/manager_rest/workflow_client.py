__author__ = 'dan'

import requests
import json
import config


class WorkflowClient(object):

    def __init__(self):
        self.workflow_service_base_uri = config.instance().workflow_service_base_uri

    def execute_workflow(self, workflow, plan):
        response = requests.post('{0}/workflows'.format(self.workflow_service_base_uri),
                                 json.dumps({
                                     'radial': workflow,
                                     'fields': {'plan': plan}
                                 }))
        # TODO: handle error code
        return response.json()

    def validate_workflows(self, plan):
        response = requests.put('{0}/workflows/validate'.format(self.workflow_service_base_uri),
                                json.dumps({'fields': {'plan': plan}}))
        # TODO: handle error code
        return response.json()

    def get_workflow_status(self, workflow_id):
        response = requests.get('{0}/workflows/{1}'.format(self.workflow_service_base_uri, workflow_id))
        # TODO: handle error code
        return response.json()


def workflow_client():
    if config.instance().test_mode:
        from test.mocks import MockWorkflowClient
        return MockWorkflowClient()
    else:
        return WorkflowClient()
