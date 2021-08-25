from cloudify.decorators import workflow
from cloudify.state import workflow_ctx
from cloudify.manager import get_rest_client

from dsl_parser import tasks

from .step_extractor import extract_steps


def create_update(*, update_id, blueprint_id, new_inputs):
    client = get_rest_client()
    dep = client.deployments.get(workflow_ctx.deployment.id)

    inputs = dep.inputs.copy()
    inputs.update(new_inputs)

    client.deployment_updates.create(
        update_id,
        workflow_ctx.deployment.id,
        blueprint_id=blueprint_id,
        inputs=inputs,
    )


def prepare_plan(*, update_id):
    """Prepare the new deployment plan for a deployment update"""
    client = get_rest_client()
    dep_up = client.deployment_updates.get(update_id)
    bp = client.blueprints.get(dep_up.new_blueprint_id)

    deployment_plan = tasks.prepare_deployment_plan(
        bp.plan,
        client.secrets.get,
        dep_up.new_inputs,
        runtime_only_evaluation=dep_up.runtime_only_evaluation
    )
    client.deployment_updates.set_attributes(update_id, plan=deployment_plan)


def create_steps(*, update_id):
    """Given a deployment update, extracts the steps for it"""
    client = get_rest_client()
    dep_up = client.deployment_updates.get(update_id)
    deployment = client.deployments.get(dep_up.deployment_id)
    nodes = client.nodes.list(deployment_id=dep_up.deployment_id)

    # step-extractor expects workflows in this format - this is the same format
    # as returned by prepare_deployment_plan
    deployment['workflows'] = {
        workflow.id: dict(workflow) for workflow in deployment['workflows']
    }
    for deployment_workflow in deployment['workflows'].values():
        deployment_workflow.pop('name')

    supported_steps, unsupported_steps = extract_steps(
        nodes,
        deployment,
        dep_up.deployment_plan
    )
    if unsupported_steps:
        for step in unsupported_steps:
            workflow_ctx.logger.error('Unsupported step: %s', step)
        raise RuntimeError('Cannot update: unsupported steps found')

    client.deployment_updates.set_attributes(
        update_id,
        steps=[step.as_dict() for step in supported_steps]
    )


def prepare_update_nodes(*, update_id):
    client = get_rest_client()
    dep_up = client.deployment_updates.get(update_id)
    deployment = client.deployments.get(dep_up.deployment_id)
    old_nodes = client.nodes.list(deployment_id=dep_up.deployment_id)
    new_nodes = dep_up.deployment_plan['nodes'].copy()
    old_instances = client.node_instances.list(
        deployment_id=dep_up.deployment_id)
    changed_instances = tasks.modify_deployment(
        nodes=new_nodes,
        previous_nodes=old_nodes,
        previous_node_instances=old_instances,
        scaling_groups=deployment.scaling_groups,
        modified_nodes=()
    )
    workflow_ctx.logger.info('changed_instances %s', changed_instances)
    update_nodes = {}
    for step in dep_up.steps:
        if step['entity_type'] != 'node':
            continue
        update_nodes.setdefault(step['action'], []).append(step['entity_id'])
    client.deployment_updates.set_attributes(
        update_id,
        nodes=update_nodes,
        node_instances=changed_instances
    )


def _prepare_update_graph(
        ctx,
        update_id,
        *,
        inputs=None,
        blueprint_id=None,
        **kwargs):
    graph = ctx.graph_mode()
    seq = graph.sequence()
    seq.add(
        ctx.local_task(create_update, kwargs={
            'update_id': update_id,
            'blueprint_id': blueprint_id,
            'new_inputs': inputs or {},
        }, total_retries=0),
        ctx.local_task(prepare_plan, kwargs={
            'update_id': update_id,
        }, total_retries=0),
        ctx.local_task(create_steps, kwargs={
            'update_id': update_id,
        }, total_retries=0),
        ctx.local_task(prepare_update_nodes, kwargs={
            'update_id': update_id,
        }, total_retries=0),
    )
    return graph


def create_new_nodes(*, update_id):
    client = get_rest_client()
    dep_up = client.deployment_updates.get(update_id)
    update_nodes = dep_up['deployment_update_nodes'] or {}
    plan_nodes = dep_up.deployment_plan['nodes']
    create_nodes = []
    for node_path in update_nodes.get('add', []):
        node_name = node_path.split(':')[-1]
        for plan_node in plan_nodes:
            if plan_node['name'] == node_name:
                create_nodes.append(plan_node)
                new_node = plan_node
                break
        else:
            raise RuntimeError(f'New node {node_name} not found in the plan')
    client.nodes.create_many(
        dep_up.deployment_id,
        create_nodes
    )


def create_new_instances(*, update_id):
    client = get_rest_client()
    dep_up = client.deployment_updates.get(update_id)

    update_instances = dep_up['deployment_update_node_instances']
    if update_instances.get('added_and_related'):
        client.node_instances.create_many(
            dep_up.deployment_id,
            update_instances['added_and_related']
        )


def _perform_update_graph(ctx, update_id, **kwargs):
    graph = ctx.graph_mode()
    seq = graph.sequence()
    seq.add(
        ctx.local_task(create_new_nodes, kwargs={
            'update_id': update_id,
        }, total_retries=0),
        ctx.local_task(create_new_instances, kwargs={
            'update_id': update_id,
        }, total_retries=0),
    )
    return graph


def _clear_graph(graph):
    for task in graph.tasks:
        graph.remove_task(task)


@workflow
def update_deployment(ctx, *, preview=False, **kwargs):
    client = get_rest_client()
    update_id = '{0}_{1}'.format(ctx.deployment.id, ctx.execution_id)
    graph = _prepare_update_graph(ctx, update_id, **kwargs)
    graph.execute()


    if not preview:
        _clear_graph(graph)
        graph = _perform_update_graph(ctx, update_id)
        graph.execute()

    client.deployment_updates.set_attributes(
        update_id,
        state='successful'
    )
