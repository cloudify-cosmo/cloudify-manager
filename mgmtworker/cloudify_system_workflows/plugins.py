########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

from cloudify.utils import wait_for
from cloudify.decorators import workflow
from cloudify.manager import get_rest_client
from cloudify.utils import get_tenant_name
from cloudify.models_states import ExecutionState
from cloudify_rest_client.exceptions import CloudifyClientError


@workflow(system_wide=True)
def install(ctx, plugin, **_):
    try:
        execution_result = _operate_on_plugin(ctx, plugin, 'install')
    except Exception as e:
        ctx.send_event("The plugin '{0}' failed to install. "
                       "Sending a 'force plugin uninstall' request..."
                       "".format(plugin['id']))
        client = get_rest_client()
        plugins = client.plugins.list(id=plugin['id'])
        if plugins:
            client.plugins.delete(plugin_id=plugin['id'], force=True)
            ctx.send_event("Sent a 'force plugin uninstall' request for "
                           "plugin '{0}'.".format(plugin['id']))
        else:
            ctx.send_event("The plugin {0} entry doesn't exist."
                           "".format(plugin['id']))
        raise e
    return execution_result


@workflow(system_wide=True)
def uninstall(ctx, plugin, **_):
    return _operate_on_plugin(ctx, plugin, 'uninstall')


def _operate_on_plugin(ctx, plugin, action):
    graph = ctx.graph_mode()
    graph.add_task(ctx.execute_task(
        'cloudify_agent.operations.{0}_plugins'.format(action),
        kwargs={'plugins': [plugin]}))
    return graph.execute()


@workflow(system_wide=True)
def update(ctx, update_id, temp_blueprint_id, deployments_to_update,
           deployments_per_tenant, force, auto_correct_types,
           reevaluate_active_statuses, **_):
    """Execute deployment update for all the given deployments_to_update.

    :param update_id: plugins update ID.
    :param temp_blueprint_id: temporary blueprint ID that should be used for
    this workflow only.
    :param deployments_to_update: deployments to perform the update on, using
    the temp blueprint ID provided.
    :param deployments_per_tenant: dictionary containing information about
     deployment IDs to be updated (values) for various tenants (keys).
    :param force: force update (i.e. even if the blueprint is used to create
    components).
    :param auto_correct_types: update deployments with auto_correct_types flag,
     which will attempt to cast inputs to the types defined by the blueprint.
    :reevaluate_active_statuses: reevaluate deployment updates states based on
     relevant executions statuses.
    """

    ctx.logger.info('Executing update_plugin system workflow with flags: '
                    'force={0}, auto_correct_types={1}'.
                    format(force, auto_correct_types))

    ctx.send_event(f'Plugins update workflow, update_id={update_id}, '
                   f'deployments_to_update={deployments_to_update}, '
                   f'deployments_per_tenant={deployments_per_tenant}')

    kwargs = {
        'blueprint_id': temp_blueprint_id,
        'skip_install': True,
        'skip_uninstall': True,
        'skip_reinstall': True,
        'force': force,
        'auto_correct_types': auto_correct_types,
        'reevaluate_active_statuses': reevaluate_active_statuses
    }

    if deployments_per_tenant:
        for tenant_name, deployment_ids in deployments_per_tenant.items():
            client = get_rest_client(tenant=tenant_name)
            for dep_id in deployment_ids:
                _do_update(ctx, client, update_id, dep_id, tenant_name, kwargs)
    elif deployments_to_update:
        tenant_name = get_tenant_name()
        client = get_rest_client()
        for dep_id in deployments_to_update:
            _do_update(ctx, client, update_id, dep_id, tenant_name, kwargs)

    ctx.send_event('Finalizing plugins update...')
    client = get_rest_client()
    client.plugins_update.finalize_plugins_update(update_id)


def _do_update(ctx, client, update_id, deployment_id, tenant_name, kwargs):
    ctx.send_event('Executing deployment update for deployment '
                   '{}...'.format(deployment_id))
    try:
        execution_id = client.deployment_updates \
            .update_with_existing_blueprint(
                deployment_id=deployment_id,
                **kwargs) \
            .execution_id
    except CloudifyClientError:
        execution_id = None
        execution_status = ExecutionState.FAILED
    else:
        wait_for(client.executions.get,
                 execution_id,
                 'status',
                 lambda x: x in ExecutionState.END_STATES,
                 RuntimeError,
                 'Deployment update has failed with '
                 f'execution ID: {execution_id}.',
                 timeout=3600)
        execution_status = client.executions.get(execution_id).status

    msg = f'Deployment update of deployment {deployment_id} of ' \
          f'{tenant_name} {execution_status}. Plugins update ID {update_id}.'
    if execution_id:
        msg += f' Execution ID {execution_id}.'
    ctx.send_event(msg)
