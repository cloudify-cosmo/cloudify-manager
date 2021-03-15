import hashlib
import uuid

from flask_security import current_user

from cloudify.amqp_client import get_client, SendHandler
from cloudify.models_states import PluginInstallationState
from cloudify.constants import (
    MGMTWORKER_QUEUE,
    BROKER_PORT_SSL
)
from dsl_parser import constants

from manager_rest import config, utils
from manager_rest.storage import get_storage_manager, models


def execute_workflow(execution,
                     bypass_maintenance=None,
                     wait_after_fail=600,
                     resume=False,
                     handler: SendHandler = None,):
    deployment = execution.deployment
    blueprint = deployment.blueprint
    workflow = deployment.workflows[execution.workflow_id]
    task_name = workflow['operation']
    execution_token = execution.token or generate_execution_token(execution.id)

    context = {
        'type': 'workflow',
        'task_name': task_name,
        'task_id': execution.id,
        'workflow_id': execution.workflow_id,
        'blueprint_id': blueprint.id,
        'deployment_id': deployment.id,
        'runtime_only_evaluation': deployment.runtime_only_evaluation,
        'execution_id': execution.id,
        'bypass_maintenance': bypass_maintenance,
        'dry_run': execution.is_dry_run,
        'is_system_workflow': False,
        'wait_after_fail': wait_after_fail,
        'resume': resume,
        'execution_token': execution_token,
        'plugin': {}
    }
    plugin_name = workflow['plugin']
    workflow_plugins = blueprint.plan[constants.WORKFLOW_PLUGINS_TO_INSTALL]
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
            'tenant_name': plugin.get('tenant_name'),
            'source': plugin.get('source')
        }

    return _execute_task(execution_id=execution.id,
                         execution_parameters=execution.parameters,
                         context=context,
                         execution_creator=execution.creator,
                         handler=handler,)


def _system_workflow_task_name(wf_id):
    return {
        'create_snapshot': 'cloudify_system_workflows.snapshot.create',
        'restore_snapshot': 'cloudify_system_workflows.snapshot.restore',
        'uninstall_plugin': 'cloudify_system_workflows.plugins.uninstall',
        'create_deployment_environment':
            'cloudify_system_workflows.deployment_environment.create',
        'delete_deployment_environment':
            'cloudify_system_workflows.deployment_environment.delete',
        'update_plugin': 'cloudify_system_workflows.plugins.update',
        'upload_blueprint': 'cloudify_system_workflows.blueprint.upload'
    }[wf_id]


def execute_system_workflow(execution,
                            bypass_maintenance=None,
                            update_execution_status=True):
    context = {
        'type': 'workflow',
        'task_id': execution.id,
        'execution_id': execution.id,
        'workflow_id': execution.workflow_id,
        'task_name': _system_workflow_task_name(execution.workflow_id),
        'bypass_maintenance': bypass_maintenance,
        'dry_run': execution.is_dry_run,
        'update_execution_status': update_execution_status,
        'is_system_workflow': execution.is_system_workflow,
        'execution_token': generate_execution_token(execution.id),
    }

    if execution.deployment:
        context['blueprint_id'] = execution.deployment.blueprint_id
        context['deployment_id'] = execution.deployment.id

    return _execute_task(execution_id=context['task_id'],
                         execution_parameters=execution.parameters,
                         context=context, execution_creator=execution.creator)


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


def get_amqp_client(tenant=None):
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


def workflow_sendhandler() -> SendHandler:
    return SendHandler(MGMTWORKER_QUEUE, 'direct', routing_key='workflow')


def _send_mgmtworker_task(message, exchange=MGMTWORKER_QUEUE,
                          exchange_type='direct', routing_key='workflow'):
    """Send a message to the mgmtworker exchange"""
    client = get_amqp_client()
    send_handler = SendHandler(exchange, exchange_type,
                               routing_key=routing_key)
    client.add_handler(send_handler)
    with client:
        send_handler.publish(message)


def _broadcast_mgmtworker_task(message, exchange='cloudify-mgmtworker-service',
                               exchange_type='fanout', routing_key='service'):
    """Broadcast a message to all mgmtworkers in a cluster."""
    client = get_amqp_client()
    send_handler = SendHandler(exchange, exchange_type,
                               routing_key=routing_key)
    client.add_handler(send_handler)
    with client:
        send_handler.publish(message)


def _execute_task(execution_id, execution_parameters,
                  context, execution_creator, handler: SendHandler = None):
    # Get the host ip info and return them
    sm = get_storage_manager()
    managers = sm.list(models.Manager)
    context['rest_host'] = [manager.private_ip for manager in managers]
    context['rest_token'] = execution_creator.get_auth_token()
    context['tenant'] = _get_tenant_dict()
    context['task_target'] = MGMTWORKER_QUEUE
    context['execution_creator_username'] = execution_creator.username
    execution_parameters['__cloudify_context'] = context
    message = {
        'cloudify_task': {'kwargs': execution_parameters},
        'id': execution_id,
        'dlx_id': None,
        'execution_creator': execution_creator.id
    }
    if handler is not None:
        handler.publish(message)
    else:
        _send_mgmtworker_task(message)


def restart_restservice():
    message = {
        'service_task': {
            'task_name': 'restart-restservice',
            'kwargs': {
                'service_management': config.instance.service_management,
            },
        }
    }
    _broadcast_mgmtworker_task(message)


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
    _broadcast_mgmtworker_task(message)


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
                    'tenant_name': utils.current_tenant.name
                }
            }
        })
