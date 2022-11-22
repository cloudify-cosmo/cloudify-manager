from typing import Dict, List, Optional, Sequence, Tuple

from cloudify.deployment_dependencies import create_deployment_dependency
from cloudify.workflows.workflow_context import CloudifyWorkflowContext
from cloudify_rest_client.client import CloudifyClient
from dsl_parser import constants as dsl_constants
from dsl_parser import models as dsl_models
from dsl_parser import functions as dsl_functions


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


def _drop_on_update(idd):
    """During a dep-update, should this idd be deleted? (and re-created)

    Component and SharedResource IDDs don't need to be deleted, because
    they will be deleted/created by the Component itself, while uninstalling.

    Custom IDDs, created by the user via the rest-client, ie. not coming from
    an intrinsic functions, should be kept as well.
    """
    creator = idd['dependency_creator']
    if creator.startswith(
        ('component.', 'sharedresource.')
    ):
        return False

    _, _, last_segment = creator.rpartition('.')
    if last_segment in dsl_functions.TEMPLATE_FUNCTIONS:
        func = dsl_functions.TEMPLATE_FUNCTIONS[last_segment]
        if issubclass(
                func, dsl_functions.InterDeploymentDependencyCreatingFunction):
            # this idd was created by the function, because it is a
            # idd-creating-function, so it does need to be removed, not kept
            return True

    return False


def update(ctx: CloudifyWorkflowContext, deployment_plan: dsl_models.Plan):
    """Update inter-deployment dependencies based on the deployment_plan."""
    local_dependencies, external_dependencies, ext_client = _prepare(
        deployment_plan,
        ctx.get_managers(),
        deployment_plan['nodes'],
        ctx.tenant_name,
        ctx.deployment.id,
    )

    preexisting = ctx.list_idds(source_deployment_id=ctx.deployment.id)
    for entry in preexisting:
        if _drop_on_update(entry):
            continue
        keep_entry = {
            'dependency_creator': entry['dependency_creator'],
            'target_deployment_func': entry['target_deployment_func'],
        }
        if entry.get('external_target'):
            target = external_dependencies
            keep_entry['external_target'] = entry['external_target']
        else:
            target = local_dependencies
            keep_entry['target_deployment'] = entry['target_deployment_id']
        target.append(keep_entry)

    if local_dependencies:
        ctx.update_idds(ctx.deployment.id, local_dependencies)
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
    for dependency in new_dependencies:
        func_id = dependency['function_identifier']

        target_deployment_id, target_deployment_func = \
            dependency['target_deployment']
        if target_deployment_func:
            target_deployment_func = {
                'function': target_deployment_func,
                'context': dependency.get('context', {}),
            }
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
