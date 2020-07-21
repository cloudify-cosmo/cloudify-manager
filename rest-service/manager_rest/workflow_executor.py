#########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
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

import uuid
import math
import hashlib
from datetime import datetime

from flask_security import current_user

from cloudify.amqp_client import (get_client,
                                  SendHandler,
                                  ScheduledExecutionHandler)
from cloudify.models_states import PluginInstallationState
from cloudify.constants import (
    MGMTWORKER_QUEUE,
    BROKER_PORT_SSL
)

from manager_rest import config, utils
from manager_rest.storage import get_storage_manager, models


def execute_workflow(name,
                     workflow,
                     workflow_plugins,
                     blueprint_id,
                     deployment,
                     execution_id,
                     execution_parameters=None,
                     bypass_maintenance=None,
                     dry_run=False,
                     wait_after_fail=600,
                     execution_creator=None,
                     scheduled_time=None,
                     resume=False,
                     execution_token=None):

    execution_parameters = execution_parameters or {}
    task_name = workflow['operation']
    execution_token = execution_token or generate_execution_token(execution_id)

    context = {
        'type': 'workflow',
        'task_name': task_name,
        'task_id': execution_id,
        'workflow_id': name,
        'blueprint_id': blueprint_id,
        'deployment_id': deployment.id,
        'runtime_only_evaluation': deployment.runtime_only_evaluation,
        'execution_id': execution_id,
        'bypass_maintenance': bypass_maintenance,
        'dry_run': dry_run,
        'is_system_workflow': False,
        'wait_after_fail': wait_after_fail,
        'resume': resume,
        'execution_token': execution_token,
        'plugin': {}
    }
    plugin_name = workflow['plugin']
    plugins = [p for p in workflow_plugins if p['name'] == plugin_name]
    plugin = plugins[0] if plugins else None
    if plugin is not None and plugin['package_name']:
        sm = get_storage_manager()
        filter_plugin = {'package_name': plugin.get('package_name'),
                         'package_version': plugin.get('package_version')}
        managed_plugins = sm.list(models.Plugin, filters=filter_plugin).items
        if managed_plugins:
            plugin['visibility'] = managed_plugins[0].visibility
            plugin['tenant_name'] = managed_plugins[0].tenant_name

        context['plugin'] = {
            'name': plugin_name,
            'package_name': plugin.get('package_name'),
            'package_version': plugin.get('package_version'),
            'visibility': plugin.get('visibility'),
            'tenant_name': plugin.get('tenant_name')
        }

    return _execute_task(execution_id=execution_id,
                         execution_parameters=execution_parameters,
                         context=context,
                         execution_creator=execution_creator,
                         scheduled_time=scheduled_time)


def execute_system_workflow(wf_id,
                            task_id,
                            task_mapping,
                            deployment=None,
                            execution_parameters=None,
                            bypass_maintenance=None,
                            update_execution_status=True,
                            dry_run=False,
                            is_system_workflow=True,
                            execution_creator=None):
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
        'is_system_workflow': is_system_workflow,
        'execution_token': generate_execution_token(task_id),
    }

    if deployment:
        context['blueprint_id'] = deployment.blueprint_id
        context['deployment_id'] = deployment.id

    return _execute_task(execution_id=context['task_id'],
                         execution_parameters=execution_parameters,
                         context=context, execution_creator=execution_creator)


def generate_execution_token(execution_id):
    sm = get_storage_manager()
    execution = sm.get(models.Execution, execution_id)
    execution_token = uuid.uuid4().hex

    # Store the token hashed in the DB
    execution.token = hashlib.sha256(
        execution_token.encode('ascii')).hexdigest()
    sm.update(execution)
    return execution_token


def _get_tenant_dict():
    return {'name': utils.current_tenant.name}


def _get_amqp_client(tenant=None):
    vhost = '/' if tenant is None else tenant.rabbitmq_vhost
    client = get_client(
        amqp_host=config.instance.amqp_host,
        amqp_user=config.instance.amqp_username,
        amqp_pass=config.instance.amqp_password,
        amqp_port=BROKER_PORT_SSL,
        amqp_vhost=vhost,
        ssl_enabled=True,
        ssl_cert_path=config.instance.amqp_ca_path
    )
    return client


def _send_mgmtworker_task(message, exchange=MGMTWORKER_QUEUE,
                          exchange_type='direct', routing_key='workflow'):
    """Send a message to the mgmtworker exchange"""
    client = _get_amqp_client()
    send_handler = SendHandler(exchange, exchange_type,
                               routing_key=routing_key)
    client.add_handler(send_handler)
    with client:
        send_handler.publish(message)


def _send_task_to_dlx(message, message_ttl, routing_key='workflow'):
    """
    We use Rabbit's `Dead Letter Exchange` to achieve execution scheduling:
    1. Create a Dead Letter Exchange with the following parameters:
        - `ttl` (time until message is moved to another queue): the delta
            between now and the scheduled time.
        - `dead-letter-exchange`: The temporary exchange that is used to
            forward the task
        - `dead-letter-routing-key`: The queue we want the task to be
             ultimately sent to (in this case MGMTWORKER queue).
    2. Send the execution to that DLX
    3. When ttl is passed the task will automatically be sent to the
        MGMTWORKER queue and will be executed normally.
    """
    dlx_exchange = message['dlx_id']
    dlx_routing_key = message['dlx_id'] + '_queue'

    client = _get_amqp_client()
    send_handler = ScheduledExecutionHandler(exchange=dlx_exchange,
                                             exchange_type='direct',
                                             routing_key=dlx_routing_key,
                                             target_exchange=MGMTWORKER_QUEUE,
                                             target_routing_key=routing_key,
                                             ttl=message_ttl)
    client.add_handler(send_handler)
    with client:
        send_handler.publish(message)


def _execute_task(execution_id, execution_parameters,
                  context, execution_creator, scheduled_time=None):
    # Get the host ip info and return them
    sm = get_storage_manager()
    managers = sm.list(models.Manager)
    context['rest_host'] = [manager.private_ip for manager in managers]
    context['rest_token'] = execution_creator.get_auth_token()
    context['tenant'] = _get_tenant_dict()
    context['task_target'] = MGMTWORKER_QUEUE
    execution_parameters['__cloudify_context'] = context
    message = {
        'cloudify_task': {'kwargs': execution_parameters},
        'id': execution_id,
        'dlx_id': None,
        'execution_creator': current_user.id
    }
    if scheduled_time:
        message_ttl = _get_time_to_live(scheduled_time)
        message['dlx_id'] = execution_id
        _send_task_to_dlx(message, message_ttl)
        return
    _send_mgmtworker_task(message)


def _get_time_to_live(scheduled_time):
    """
    Rabbit's ttl is the time until message is moved to another queue.
    Ttl should be an Integer and in miliseconds.
    :param scheduled_time: The date and time this execution is scheduled for.
    :return: time (in miliseconds) between `now` and `scheduled time`
    """
    now = datetime.utcnow()
    delta = (scheduled_time - now).total_seconds()
    delta = int(math.floor(delta))
    delta_in_milisecs = delta * 1000
    return delta_in_milisecs


def cancel_execution(execution_id):
    sm = get_storage_manager()
    managers = sm.list(models.Manager)
    message = {
        'service_task': {
            'task_name': 'cancel-workflow',
            'kwargs': {
                'rest_host': [manager.private_ip for manager in managers],
                'execution_id': execution_id,
                'rest_token': current_user.get_auth_token(),
                'tenant': _get_tenant_dict(),
                'execution_token': generate_execution_token(execution_id)
            }
        }
    }
    _send_mgmtworker_task(message, routing_key='service')


def _get_plugin_message(plugin, task='install-plugin', target_names=None):
    """Make plugin-related service task message.

    This is for creating plugin install/uninstall messages, to send to
    the mgmtworkers/agents.
    """
    sm = get_storage_manager()
    managers = sm.list(models.Manager)
    message = {
        'service_task': {
            'task_name': task,
            'kwargs': {
                'plugin': plugin.to_dict(),
                'rest_host': [manager.private_ip for manager in managers],
                'rest_token': current_user.get_auth_token(),
                'tenant': _get_tenant_dict(),
            }
        }
    }
    if target_names:
        message['service_task']['kwargs']['target'] = target_names
    return message


def install_plugin(plugin):
    """Send the install-plugin message to agents/mgmtworkers.

    Send the install-plugin message to agents/mgmtworkers that are
    in state==PENDING for that plugin.
    """
    sm = get_storage_manager()
    pstates = sm.list(models._PluginState, filters={
        '_plugin_fk': plugin._storage_id,
        'state': PluginInstallationState.PENDING
    })
    agents_per_tenant = {}
    managers = []
    for pstate in pstates:
        if pstate.manager:
            managers.append(pstate.manager.hostname)
        if pstate.agent:
            agents_per_tenant.setdefault(
                pstate.agent.tenant, []).append(pstate.agent)
    if managers:
        _send_mgmtworker_task(
            _get_plugin_message(plugin, target_names=managers),
            routing_key='service')

    agent_message = _get_plugin_message(plugin)
    if agents_per_tenant:
        for tenant, agents in agents_per_tenant.items():
            # amqp client for the given tenant's vhost.
            # Still use the manager's creds.
            tenant_client = _get_amqp_client(tenant)
            with tenant_client:
                for agent in agents:
                    send_handler = SendHandler(
                        agent.name,
                        exchange_type='direct',
                        routing_key='service')
                    tenant_client.add_handler(send_handler)
                    send_handler.publish(agent_message)
