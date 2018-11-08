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

from cloudify.cryptography_utils import decrypt
from cloudify.amqp_client import get_client, SendHandler

from manager_rest import config, utils
from manager_rest.storage import get_storage_manager, models
from manager_rest.constants import MGMTWORKER_QUEUE, BROKER_SSL_PORT


def execute_workflow(name,
                     workflow,
                     workflow_plugins,
                     blueprint_id,
                     deployment_id,
                     execution_id,
                     execution_parameters=None,
                     bypass_maintenance=None,
                     dry_run=False):
    execution_parameters = execution_parameters or {}
    task_name = workflow['operation']
    plugin_name = workflow['plugin']
    plugin = [p for p in workflow_plugins if p['name'] == plugin_name][0]
    if plugin and plugin['package_name']:
        sm = get_storage_manager()
        filter_plugin = {'package_name': plugin.get('package_name'),
                         'package_version': plugin.get('package_version')}
        managed_plugins = sm.list(models.Plugin, filters=filter_plugin).items
        if managed_plugins:
            plugin['visibility'] = managed_plugins[0].visibility
            plugin['tenant_name'] = managed_plugins[0].tenant_name

    context = {
        'type': 'workflow',
        'task_name': task_name,
        'task_id': execution_id,
        'workflow_id': name,
        'blueprint_id': blueprint_id,
        'deployment_id': deployment_id,
        'execution_id': execution_id,
        'bypass_maintenance': bypass_maintenance,
        'dry_run': dry_run,
        'is_system_workflow': False,
        'plugin': {
            'name': plugin_name,
            'package_name': plugin.get('package_name'),
            'package_version': plugin.get('package_version'),
            'visibility': plugin.get('visibility'),
            'tenant_name': plugin.get('tenant_name')
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
                            update_execution_status=True,
                            dry_run=False,
                            is_system_workflow=True):
    execution_parameters = execution_parameters or {}
    context = {
        'type': 'workflow',
        'task_id': task_id,
        'task_name': task_mapping,
        'execution_id': task_id,
        'workflow_id': wf_id,
        'bypass_maintenance': bypass_maintenance,
        'dry_run': dry_run,
        'update_execution_status': update_execution_status,
        'is_system_workflow': is_system_workflow
    }

    if deployment:
        context['blueprint_id'] = deployment.blueprint_id
        context['deployment_id'] = deployment.id

    return _execute_task(execution_id=context['task_id'],
                         execution_parameters=execution_parameters,
                         context=context)


def _get_tenant_dict():
    tenant_dict = utils.current_tenant.to_dict()
    tenant_dict['rabbitmq_password'] = decrypt(
        tenant_dict['rabbitmq_password']
    )
    for to_remove in ['id', 'users', 'groups']:
        tenant_dict.pop(to_remove)
    return tenant_dict


def _send_mgmtworker_task(message, routing_key='workflow'):
    """Send a message to the mgmtworker exchange"""
    client = get_client(
        amqp_host=config.instance.amqp_host,
        amqp_user=config.instance.amqp_username,
        amqp_pass=config.instance.amqp_password,
        amqp_port=BROKER_SSL_PORT,
        amqp_vhost='/',
        ssl_enabled=True,
        ssl_cert_path=config.instance.amqp_ca_path
    )
    send_handler = SendHandler(MGMTWORKER_QUEUE, routing_key=routing_key)
    client.add_handler(send_handler)
    with client:
        send_handler.publish(message)


def _execute_task(execution_id, execution_parameters, context):
    context['rest_token'] = current_user.get_auth_token()
    context['tenant'] = _get_tenant_dict()
    context['task_target'] = MGMTWORKER_QUEUE
    execution_parameters['__cloudify_context'] = context
    message = {
        'cloudify_task': {'kwargs': execution_parameters},
        'id': execution_id,
    }

    _send_mgmtworker_task(message)


def cancel_execution(execution_id):
    message = {
        'service_task': {
            'task_name': 'cancel-workflow',
            'kwargs': {
                'execution_id': execution_id,
                'rest_token': current_user.get_auth_token(),
                'tenant': _get_tenant_dict()
            }
        }
    }
    _send_mgmtworker_task(message, routing_key='service')
