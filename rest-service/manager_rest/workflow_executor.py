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


from flask_security import current_user

from manager_rest import celery_client, utils
from manager_rest.constants import MGMTWORKER_QUEUE


def execute_workflow(name,
                     workflow,
                     workflow_plugins,
                     blueprint_id,
                     deployment_id,
                     execution_id,
                     execution_parameters=None,
                     bypass_maintenance=None):
    execution_parameters = execution_parameters or {}
    task_name = workflow['operation']

    plugin_name = workflow['plugin']
    plugin = [p for p in workflow_plugins if p['name'] == plugin_name][0]

    context = {
        'type': 'workflow',
        'task_name': task_name,
        'task_id': execution_id,
        'workflow_id': name,
        'blueprint_id': blueprint_id,
        'deployment_id': deployment_id,
        'execution_id': execution_id,
        'bypass_maintenance': bypass_maintenance,
        'plugin': {
            'name': plugin_name,
            'package_name': plugin.get('package_name'),
            'package_version': plugin.get('package_version')
        }
    }
    return _execute_task(execution_id=execution_id,
                         execution_parameters=execution_parameters,
                         context=context)


def execute_system_workflow(wf_id,
                            task_id,
                            task_mapping,
                            deployment=None,
                            execution_parameters=None,
                            bypass_maintenance=None,
                            update_execution_status=True):
    execution_parameters = execution_parameters or {}
    context = {
        'type': 'workflow',
        'task_id': task_id,
        'task_name': task_mapping,
        'execution_id': task_id,
        'workflow_id': wf_id,
        'bypass_maintenance': bypass_maintenance,
        'update_execution_status': update_execution_status
    }

    if deployment:
        context['blueprint_id'] = deployment.blueprint_id
        context['deployment_id'] = deployment.id

    return _execute_task(execution_id=context['task_id'],
                         execution_parameters=execution_parameters,
                         context=context)


def _get_tenant_dict():
    tenant_dict = utils.current_tenant.to_dict()
    for to_remove in ['id', 'users', 'groups']:
        tenant_dict.pop(to_remove)
    return tenant_dict


def _execute_task(execution_id, execution_parameters, context):
    context['rest_token'] = current_user.get_auth_token()
    context['tenant'] = _get_tenant_dict()
    context['task_target'] = MGMTWORKER_QUEUE
    execution_parameters['__cloudify_context'] = context
    celery = celery_client.get_client()
    try:
        return celery.execute_task(task_queue=MGMTWORKER_QUEUE,
                                   task_id=execution_id,
                                   kwargs=execution_parameters)
    finally:
        celery.close()
