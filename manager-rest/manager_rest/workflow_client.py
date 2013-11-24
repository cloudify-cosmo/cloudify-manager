__author__ = 'dan'

import requests
import json


class WorkflowClient(object):

    def __init__(self):
        from server import app
        self.workflow_service_base_uri = app.config['WORKFLOW_SERVICE_BASE_URI']

    def execute_workflow(self, workflow, plan):
        response = requests.post('{0}/workflows'.format(self.workflow_service_base_uri),
                                 json.dumps({
                                     'radial': workflow,
                                     'fields': {'plan': plan}
                                 }))
        # TODO: handle error code
        return response.json()


def workflow_client():
    from server import app
    if app.config['Testing']:
        from test.mocks import MockWorkflowClient
        return MockWorkflowClient()
    else:
        return WorkflowClient()