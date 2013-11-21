__author__ = 'dan'

from datetime import datetime


class MockWorkflowClient(object):

    def execute_workflow(self, workflow, plan):
        return {
            'type': 'workflow_state',
            'id': 'yokimura-yoshomati',
            'state': 'pending',
            'created': datetime.now()
        }