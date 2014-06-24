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

import os

from manager_rest import config
from manager_rest import manager_exceptions

from manager_rest.celery_client import celery_client as client

# used by integration tests
env_workflows_queue = os.environ.get('CLOUDIFY_WORKFLOWS_QUEUE')


class WorkflowClient(object):

    @staticmethod
    def execute_workflow(name,
                         workflow,
                         deployment_id,
                         blueprint_id,
                         execution_id,
                         kwargs=None):
        task_name = '{}.{}'.format(workflow['plugin'], workflow['operation'])
        if env_workflows_queue:
            # used by integration tests
            task_queue = env_workflows_queue
        else:
            task_queue = '{}_workflows'.format(deployment_id)

        # merge parameters - parameters passed directly to execution request
        # override workflow parameters from the original plan. any
        # parameters without a default value in the blueprint must
        # appear in the execution request parameters.
        # note that extra parameters in the execution requests (i.e.
        # parameters not defined in the original workflow plan) will simply
        # be ignored silently
        execution_parameters = dict()
        workflow_parameters = workflow.get('parameters', [])
        kwargs = kwargs or dict()
        for param in workflow_parameters:
            if type(param) == str:
                # parameter without a default value - ensure one was
                # provided via kwargs
                if param not in kwargs:
                    raise \
                        manager_exceptions.MissingExecutionParametersError(
                            'Workflow {0} must be provided with a "{1}" '
                            'parameter to execute'.format(name, param))
                execution_parameters[param] = kwargs[param]
            else:
                param_name = param.keys()[0]
                execution_parameters[param_name] = kwargs[param_name] if \
                    param_name in kwargs else param[param_name]

        execution_parameters['__cloudify_context'] = {
            'workflow_id': name,
            'blueprint_id': blueprint_id,
            'deployment_id': deployment_id,
            'execution_id': execution_id
        }
        client().execute_task(task_name=task_name,
                              task_queue=task_queue,
                              task_id=execution_id,
                              kwargs=execution_parameters)
        return execution_parameters


def workflow_client():
    if config.instance().test_mode:
        from test.mocks import MockWorkflowClient
        return MockWorkflowClient()
    else:
        return WorkflowClient()
