from typing import Dict, List

from flask import current_app
from flask_security import current_user

from cloudify import logs
from cloudify.amqp_client import SendHandler
from cloudify.models_states import PluginInstallationState
from cloudify.constants import MGMTWORKER_QUEUE, EVENTS_EXCHANGE_NAME

from manager_rest import config
from manager_rest.storage import get_storage_manager, models
from manager_rest.utils import current_tenant, get_amqp_client


def get_amqp_handler(kind):
    """Get a stored amqp SendHandler

    Returns a ready-to-use SendHandler, tied to a long-lived AMQP
    connection stored on the app.
    """
    if 'amqp_client' not in current_app.extensions:
        workflow_handler = workflow_sendhandler()
        hook_handler = hooks_sendhandler()
        service_handler = service_sendhandler()
        client = get_amqp_client()
        client.add_handler(workflow_handler)
        client.add_handler(hook_handler)
        client.add_handler(service_handler)

        client.consume_in_thread()
        current_app.extensions['amqp_client'] = {
            'client': client,
            'handlers': {
                'workflow': workflow_handler,
                'hook': hook_handler,
                'service': service_handler,
            },
        }
    return current_app.extensions['amqp_client']['handlers'][kind]


def execute_workflow(messages):
    if not messages:
        return
    handler = get_amqp_handler('workflow')
    for message in messages:
        handler.publish(message)


def send_hook(event):
    logs.populate_base_item(event, 'cloudify_event')
    handler = get_amqp_handler('hook')
    handler.publish(event)


def _get_tenant_dict():
    return {'name': current_tenant.name}


def workflow_sendhandler() -> SendHandler:
    return SendHandler(MGMTWORKER_QUEUE, 'direct', routing_key='workflow')


def hooks_sendhandler() -> SendHandler:
    return SendHandler(EVENTS_EXCHANGE_NAME, exchange_type='topic',
                       routing_key='events.hooks')


def service_sendhandler() -> SendHandler:
    return SendHandler('cloudify-mgmtworker-service', exchange_type='fanout',
                       routing_key='service')


def _broadcast_mgmtworker_task(message):
    """Broadcast a message to all mgmtworkers in a cluster."""
    send_handler = get_amqp_handler('service')
    send_handler.publish(message)


def restart_restservice():
    message = {
        'service_task': {
            'task_name': 'restart-restservice',
        }
    }
    _broadcast_mgmtworker_task(message)


def cancel_execution(executions):
    sm = get_storage_manager()
    managers = sm.list(models.Manager, get_all_results=True)
    message = {
        'service_task': {
            'task_name': 'cancel-workflow',
            'kwargs': {
                'rest_host': [manager.private_ip for manager in managers],
                'rest_port': config.instance.default_agent_port,
                'executions': executions,
                'tenant': _get_tenant_dict(),
            }
        }
    }
    _broadcast_mgmtworker_task(message)


def _get_plugin_message(plugin, task='install-plugin', target_names=None):
    """Make plugin-related service task message.

    This is for creating plugin install/uninstall messages, to send to
    the mgmtworkers/agents.
    """
    sm = get_storage_manager()
    managers = sm.list(models.Manager, get_all_results=True)
    message = {
        'service_task': {
            'task_name': task,
            'kwargs': {
                'plugin': plugin.to_dict(),
                'rest_host': [manager.private_ip for manager in managers],
                'rest_port': config.instance.default_agent_port,
                'rest_token': current_user.get_auth_token(
                    description=f'Plugins task {task} rest token.',
                ),
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
    }, get_all_results=True)
    agents_per_tenant: Dict[models.Tenant, List[models.Agent]] = {}
    managers = []
    for pstate in pstates:
        if pstate.manager:
            managers.append(pstate.manager.hostname)
        if pstate.agent:
            agents_per_tenant.setdefault(
                pstate.agent.tenant, []).append(pstate.agent)
    if managers:
        _broadcast_mgmtworker_task(
            _get_plugin_message(plugin, target_names=managers))

    agent_message = _get_plugin_message(plugin)
    if agents_per_tenant:
        for tenant, agents in agents_per_tenant.items():
            # amqp client for the given tenant's vhost.
            # Still use the manager's creds.
            tenant_client = get_amqp_client(tenant)
            with tenant_client:
                for agent in agents:
                    send_handler = SendHandler(
                        agent.name,
                        exchange_type='direct',
                        routing_key='service')
                    tenant_client.add_handler(send_handler)
                    send_handler.publish(agent_message)


def uninstall_plugin(plugin):
    sm = get_storage_manager()
    pstates = sm.list(models._PluginState, filters={
        '_plugin_fk': plugin._storage_id,
        'state': [
            PluginInstallationState.INSTALLED,
            PluginInstallationState.INSTALLING,
            PluginInstallationState.ERROR
        ]
    }, get_all_results=True)
    agents_per_tenant: Dict[models.Tenant, List[models.Agent]] = {}
    managers = []
    for pstate in pstates:
        if pstate.manager:
            managers.append(pstate.manager.hostname)
        if pstate.agent:
            agents_per_tenant.setdefault(
                pstate.agent.tenant, []).append(pstate.agent)
    if managers:
        _broadcast_mgmtworker_task(
            _get_plugin_message(
                plugin, target_names=managers, task='uninstall-plugin'))

    agent_message = _get_plugin_message(plugin, task='uninstall-plugin')
    if agents_per_tenant:
        for tenant, agents in agents_per_tenant.items():
            # amqp client for the given tenant's vhost.
            # Still use the manager's creds.
            tenant_client = get_amqp_client(tenant)
            with tenant_client:
                for agent in agents:
                    send_handler = SendHandler(
                        agent.name,
                        exchange_type='direct',
                        routing_key='service')
                    tenant_client.add_handler(send_handler)
                    send_handler.publish(agent_message)


def delete_source_plugins(deployment_id):
    _broadcast_mgmtworker_task(
        message={
            'service_task': {
                'task_name': 'delete-source-plugins',
                'kwargs': {
                    'deployment_id': deployment_id,
                    'tenant_name': current_tenant.name
                }
            }
        })


def clean_tenant_dirs(tenant_name):
    _broadcast_mgmtworker_task(
        message={
            'service_task': {
                'task_name': 'clean-tenant-dirs',
                'kwargs': {
                    'tenant_name': tenant_name,
                }
            }
        })
