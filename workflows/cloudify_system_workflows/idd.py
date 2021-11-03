from cloudify.deployment_dependencies import create_deployment_dependency
from cloudify.state import workflow_ctx
from cloudify_rest_client.client import CloudifyClient
from dsl_parser import constants as dsl_constants
from dsl_parser import models as dsl_models


def create(client: CloudifyClient,
           deployment_plan: dsl_models.Plan):
    """Create inter-deployment dependencies based on the deployment_plan."""
    new_dependencies = deployment_plan.setdefault(
        dsl_constants.INTER_DEPLOYMENT_FUNCTIONS, {})
    if not new_dependencies:
        return
    workflow_ctx.logger.info('Creating inter-deployment dependencies')
    manager_ips = [manager.private_ip
                   for manager in client.manager.get_managers()]
    ext_client, client_config, ext_deployment_id = \
        _get_external_clients(deployment_plan['nodes'], manager_ips)

    local_tenant_name = workflow_ctx.tenant_name if ext_client else None
    local_idds, external_idds = _do_create(
        manager_ips,
        client_config,
        new_dependencies,
        workflow_ctx.deployment.id,
        local_tenant_name,
        bool(ext_client),
        ext_deployment_id)
    if local_idds:
        client.inter_deployment_dependencies.create_many(
            workflow_ctx.deployment.id,
            local_idds)
    if external_idds:
        ext_client.inter_deployment_dependencies.create_many(
            workflow_ctx.deployment.id,
            external_idds)


def update(client: CloudifyClient,
           deployment_plan: dsl_models.Plan):
    """Update inter-deployment dependencies based on the deployment_plan."""
    new_dependencies = deployment_plan.setdefault(
        dsl_constants.INTER_DEPLOYMENT_FUNCTIONS, {})
    if not new_dependencies:
        return
    workflow_ctx.logger.info('Updating inter-deployment dependencies for '
                             f'deployment `{workflow_ctx.deployment.id}`')
    manager_ips = [manager.private_ip
                   for manager in client.manager.get_managers()]
    ext_client, client_config, ext_deployment_id = \
        _get_external_clients(deployment_plan['nodes'], manager_ips)

    local_tenant_name = workflow_ctx.tenant_name if ext_client else None
    local_idds, external_idds = _do_create(
        manager_ips,
        client_config,
        new_dependencies,
        workflow_ctx.deployment.id,
        local_tenant_name,
        bool(ext_client),
        ext_deployment_id)
    if local_idds:
        client.inter_deployment_dependencies.update_all(
            workflow_ctx.deployment.id,
            local_idds)
    if external_idds:
        ext_client.inter_deployment_dependencies.update_all(
            workflow_ctx.deployment.id,
            external_idds)


def _do_create(manager_ips: list,
               client_config,
               new_dependencies: dict,
               local_deployment_id: str,
               local_tenant_name: str,
               external: bool,
               ext_deployment_id: str) -> tuple:
    local_idds = []
    external_idds = []
    for func_id, deployment_id_func in new_dependencies.items():
        target_deployment_id, target_deployment_func = deployment_id_func
        if external:
            local_idds += [
                create_deployment_dependency(
                    dependency_creator=func_id,
                    target_deployment=None,
                    external_target={
                        'deployment': (ext_deployment_id
                                       if ext_deployment_id else None),
                        'client_config': client_config
                    })]
            external_idds += [
                create_deployment_dependency(
                    dependency_creator=func_id,
                    target_deployment=(target_deployment_id
                                       if target_deployment_id else ' '),
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
            local_idds += [
                create_deployment_dependency(
                    dependency_creator=func_id,
                    target_deployment=target_deployment_id,
                    target_deployment_func=(
                        target_deployment_func if not target_deployment_id
                        else None)
                )]
    return local_idds, external_idds


def _get_external_clients(nodes: list, manager_ips: list):
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
