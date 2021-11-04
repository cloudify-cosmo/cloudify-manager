from typing import Dict, List, Optional, Sequence, Tuple

from cloudify.deployment_dependencies import create_deployment_dependency
from cloudify.workflows.workflow_context import CloudifyWorkflowContext
from cloudify_rest_client.client import CloudifyClient
from dsl_parser import constants as dsl_constants
from dsl_parser import models as dsl_models


def create(ctx: CloudifyWorkflowContext,
           client: CloudifyClient,
           deployment_plan: dsl_models.Plan):
    """Create inter-deployment dependencies based on the deployment_plan."""
    local_dependencies, external_dependencies, ext_client = _prepare(
        deployment_plan,
        client.manager.get_managers(),
        deployment_plan['nodes'],
        ctx.tenant_name,
        ctx.deployment.id,
    )
    if local_dependencies:
        client.inter_deployment_dependencies.create_many(
            ctx.deployment.id,
            local_dependencies)
    if external_dependencies:
        ext_client.inter_deployment_dependencies.create_many(
            ctx.deployment.id,
            external_dependencies)


def update(ctx: CloudifyWorkflowContext,
           client: CloudifyClient,
           deployment_plan: dsl_models.Plan):
    """Update inter-deployment dependencies based on the deployment_plan."""
    local_dependencies, external_dependencies, ext_client = _prepare(
        deployment_plan,
        client.manager.get_managers(),
        deployment_plan['nodes'],
        ctx.tenant_name,
        ctx.deployment.id,
    )
    if local_dependencies:
        client.inter_deployment_dependencies.update_all(
            ctx.deployment.id,
            local_dependencies)
    if external_dependencies:
        ext_client.inter_deployment_dependencies.update_all(
            ctx.deployment.id,
            external_dependencies)


def _prepare(deployment_plan: dsl_models.Plan,
             managers: Sequence,
             nodes: List,
             tenant_name: str,
             local_deployment_id: str,
             ) -> Tuple[List, List, Optional[CloudifyClient]]:

    new_dependencies = deployment_plan.setdefault(
        dsl_constants.INTER_DEPLOYMENT_FUNCTIONS, {})
    if not new_dependencies:
        return [], [], None

    manager_ips = [manager.private_ip for manager in managers]
    ext_client, client_config, ext_deployment_id = \
        _get_external_clients(manager_ips, nodes)
    local_tenant_name = tenant_name if ext_client else None

    local_dependencies, external_dependencies = [], []
    for func_id, deployment_id_func in new_dependencies.items():
        target_deployment_id, target_deployment_func = deployment_id_func
        if ext_client:
            local_dependencies += [
                create_deployment_dependency(
                    dependency_creator=func_id,
                    target_deployment=None,
                    external_target={
                        'deployment': (ext_deployment_id
                                       if ext_deployment_id
                                       else None),
                        'client_config': client_config
                    })]
            external_dependencies += [
                create_deployment_dependency(
                    dependency_creator=func_id,
                    target_deployment=(target_deployment_id
                                       if target_deployment_id
                                       else ' '),
                    external_source={
                        'deployment': local_deployment_id,
                        'tenant': local_tenant_name,
                        'host': manager_ips,
                    })]
        else:
            # It should be safe to assume that if the target_deployment
            # is known, there's no point passing target_deployment_func.
            # Also because in this case the target_deployment_func will
            # be of type string, while REST endpoint expects a dict.
            local_dependencies += [
                create_deployment_dependency(
                    dependency_creator=func_id,
                    target_deployment=target_deployment_id,
                    target_deployment_func=(
                        target_deployment_func
                        if not target_deployment_id
                        else None)
                )]
    return local_dependencies, external_dependencies, ext_client


def _get_external_clients(manager_ips: List,
                          nodes: List
                          ) -> Tuple[Optional[CloudifyClient],
                                     Dict,
                                     Optional[str]]:
    client_config = None
    target_deployment = None
    for node in nodes:
        if node['type'] in ['cloudify.nodes.Component',
                            'cloudify.nodes.SharedResource']:
            client_config = node['properties'].get('client')
            target_deployment = node['properties'].get(
                'resource_config').get('deployment')
            break
    external_client = None
    if client_config:
        internal_hosts = ({'127.0.0.1', 'localhost'} | set(manager_ips))
        host = client_config['host']
        host = {host} if type(host) == str else set(host)
        if not (host & internal_hosts):
            external_client = CloudifyClient(**client_config)

    return \
        external_client, \
        client_config, \
        target_deployment.get('id') if target_deployment else None
