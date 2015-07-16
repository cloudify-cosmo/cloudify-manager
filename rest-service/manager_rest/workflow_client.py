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


from manager_rest.celery_client import celery_client as client


class WorkflowClient(object):

    @staticmethod
    def execute_workflow(name,
                         workflow,
                         blueprint_id,
                         deployment_id,
                         execution_id,
                         execution_parameters=None):
        task_name = workflow['operation']
        task_queue = '{}_workflows'.format(deployment_id)

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

    @staticmethod
    def execute_system_workflow(deployment, wf_id, task_id, task_mapping,
                                execution_parameters=None):
        # task_id is not generated here since for system workflows,
        # the task id is equivalent to the execution id

        context = {
            'task_id': task_id,
            'task_name': task_mapping,
            'execution_id': task_id,
            'workflow_id': wf_id,
            'blueprint_id': deployment.blueprint_id,
            'deployment_id': deployment.id,
        }

        return WorkflowClient._execute_wf_on_manager_worker(
            context,
            execution_parameters
        )

    @staticmethod
    def execute_system_wide_workflow(wf_id, task_id, task_mapping,
                                     execution_parameters=None):
        # task_id is not generated here since for system workflows,
        # the task id is equivalent to the execution id

        context = {
            'task_id': task_id,
            'task_name': task_mapping,
            'execution_id': task_id,
            'workflow_id': wf_id,
        }

        return WorkflowClient._execute_wf_on_manager_worker(
            context,
            execution_parameters
        )

    @staticmethod
    def _execute_wf_on_manager_worker(context, execution_parameters):
        task_queue = 'cloudify.management'

        context['task_target'] = task_queue

        if execution_parameters is None:
            execution_parameters = {}
        execution_parameters['__cloudify_context'] = context

        return client().execute_task(
            context['task_name'],
            task_queue,
            context['task_id'],
            kwargs=execution_parameters
        )


def workflow_client():
    return WorkflowClient()
