from collections import defaultdict

from cloudify.decorators import workflow
from cloudify.state import workflow_ctx
from cloudify.manager import get_rest_client
from cloudify.plugins import lifecycle

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


def _modified_attr_nodes(steps):
    """Based on the steps, find what attributes changed for every node.

    Returns a dict of {node-id: [attributes that changed]}.
    """
    modified = defaultdict(list)
    modified_entity_type = {
        'plugin': 'plugins',
        'relationship': 'relationships',
        'property': 'properties'
    }
    for step in steps:
        parts = step['entity_id'].split(':')
        if len(parts) < 2:
            continue
        node_id = parts[1]
        entity_type = step['entity_type']
        if entity_type in modified_entity_type:
            modified[node_id].append(modified_entity_type[entity_type])
        if entity_type == 'operation':
            if 'relationships' in parts:
                modified[node_id].append('relationships')
            else:
                modified[node_id].append('operations')
    return modified


def _added_nodes(steps):
    """Based on the steps, find node ids that were added."""
    added = set()
    for step in steps:
        if step['entity_type'] == 'node' and step['action'] == 'add':
            added.add(step['entity_id'])
    return list(added)


def _removed_nodes(steps):
    """Based on the steps, find node ids that were removed."""
    added = set()
    for step in steps:
        if step['entity_type'] == 'node' and step['action'] == 'remove':
            added.add(step['entity_id'])
    return list(added)


def prepare_update_nodes(*, update_id):
    client = get_rest_client()
    dep_up = client.deployment_updates.get(update_id)
    deployment = client.deployments.get(dep_up.deployment_id)
    old_nodes = client.nodes.list(deployment_id=dep_up.deployment_id)
    new_nodes = dep_up.deployment_plan['nodes'].copy()
    old_instances = client.node_instances.list(
        deployment_id=dep_up.deployment_id)
    instance_changes = tasks.modify_deployment(
        nodes=new_nodes,
        previous_nodes=old_nodes,
        previous_node_instances=old_instances,
        scaling_groups=deployment.scaling_groups,
        modified_nodes=()
    )
    node_changes = {
        'modify_attributes': _modified_attr_nodes(dep_up.steps),
        'add': _added_nodes(dep_up.steps),
        'remove':_removed_nodes(dep_up.steps),
    }
    client.deployment_updates.set_attributes(
        update_id,
        nodes=node_changes,
        node_instances=instance_changes
    )


def _prepare_update_graph(
        ctx,
        update_id,
        *,
        inputs=None,
        blueprint_id=None,
        **kwargs):
    """Make a tasks-graph that prepares the deployment-update.

    Those operations only plan the update and prepare the
    things-to-be-changed. They're safe to be rerun any number of times.
    """
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


def update_deployment_nodes(*, update_id):
    """Bring deployment nodes in line with the plan.

    Create new nodes, update existing modified nodes.
    """
    client = get_rest_client()
    dep_up = client.deployment_updates.get(update_id)
    update_nodes = dep_up['deployment_update_nodes'] or {}
    plan_nodes = dep_up.deployment_plan['nodes']
    create_nodes = []
    for node_name, changed_attrs in update_nodes.get(
            'modify_attributes', {}).items():
        for plan_node in plan_nodes:
            if plan_node['name'] == node_name:
                break
        else:
            raise RuntimeError(f'Node {node_name} not found in the plan')
        new_attributes = {
            attr_name: plan_node[attr_name] for attr_name in changed_attrs
        }
        client.nodes.update(
            dep_up.deployment_id, node_name,
            **new_attributes
        )
    for node_path in update_nodes.get('add', []):
        node_name = node_path.split(':')[-1]
        for plan_node in plan_nodes:
            if plan_node['name'] == node_name:
                create_nodes.append(plan_node)
                break
        else:
            raise RuntimeError(f'New node {node_name} not found in the plan')
    client.nodes.create_many(
        dep_up.deployment_id,
        create_nodes
    )


def _format_old_relationships(node_instance):
    """Dump ni's relationships to a dict that can be parsed by RESTservice"""
    return [
        {
            'target_id': old_rel.relationship.target_id,
            'target_name': old_rel.relationship.target_node.id,
            'type': old_rel.relationship.type,
        }
        for old_rel in node_instance.relationships
    ]


def update_deployment_node_instances(*, update_id):
    client = get_rest_client()
    dep_up = client.deployment_updates.get(update_id)

    update_instances = dep_up['deployment_update_node_instances']
    if update_instances.get('added_and_related'):
        added_instances = [
            ni for ni in update_instances['added_and_related']
            if ni.get('modification') == 'added'
        ]
        client.node_instances.create_many(
            dep_up.deployment_id,
            added_instances
        )
    if update_instances.get('extended_and_related'):
        for ni in update_instances['extended_and_related']:
            if ni.get('modification') != 'extended':
                continue
            old_rels = _format_old_relationships(
                workflow_ctx.get_node_instance(ni['id']))
            client.node_instances.update(
                ni['id'],
                relationships=old_rels + ni['relationships'],
                force=True
            )


def set_deployment_attributes(*, update_id):
    client = get_rest_client()
    dep_up = client.deployment_updates.get(update_id)
    client.deployments.set_attributes(
        dep_up.deployment_id,
        blueprint_id=dep_up.new_blueprint_id,
        workflows=dep_up.deployment_plan['workflows'],
        outputs=dep_up.deployment_plan['outputs'],
        description=dep_up.deployment_plan['description'],
    )
    # in the currently-running execution, update the current context as well,
    # so that later graphs downlod scripts from the new blueprint. Unfortunate,
    # but no public method for this just yet
    workflow_ctx._context['blueprint_id'] = dep_up.new_blueprint_id


def _perform_update_graph(ctx, update_id, **kwargs):
    """Make a tasks-graph that performs the deployment-update.

    This is for the destructive operations that actually change the
    deployment.
    """
    graph = ctx.graph_mode()
    seq = graph.sequence()
    seq.add(
        ctx.local_task(set_deployment_attributes, kwargs={
            'update_id': update_id,
        }, total_retries=0),
        ctx.local_task(update_deployment_nodes, kwargs={
            'update_id': update_id,
        }, total_retries=0),
        ctx.local_task(update_deployment_node_instances, kwargs={
            'update_id': update_id,
        }, total_retries=0),
    )
    return graph

def delete_removed_nodes(*, update_id):
    client = get_rest_client()
    dep_up = client.deployment_updates.get(update_id)

    update_nodes = dep_up['deployment_update_nodes'] or {}
    for node_path in update_nodes.get('remove', []):
        node_name = node_path.split(':')[-1]
        client.nodes.delete(dep_up.deployment_id, node_name)


def _post_update_graph(ctx, update_id, **kwargs):
    """The update part that runs after the interface operations.

    This runs the finalizing changes which need to happen after the
    install/uninstall phase of the dep-update.
    """
    graph = ctx.graph_mode()
    seq = graph.sequence()
    seq.add(
        ctx.local_task(delete_removed_nodes, kwargs={
            'update_id': update_id,
        }, total_retries=0),
    )
    return graph


def _clear_graph(graph):
    for task in graph.tasks:
        graph.remove_task(task)


def _establish_relationships(ctx, graph, extended_and_related, **kwargs):
    node_instances = [
        ctx.get_node_instance(ni['id'])
        for ni in extended_and_related
    ]

    modified_relationship_ids = defaultdict(list)
    for ni in extended_and_related:
        if ni.get('modification') != 'extended':
            continue
        node_id = ni['node_id']
        for new_rel in ni['relationships']:
            modified_relationship_ids[node_id].append(new_rel['target_name'])
    lifecycle.execute_establish_relationships(
        graph=graph,
        node_instances=node_instances,
        modified_relationship_ids=modified_relationship_ids
    )


def _execute_deployment_update(ctx, client, update_id, **kwargs):
    """Do all the non-preview, destructive, update operations."""
    graph = ctx.graph_mode()

    _clear_graph(graph)
    graph = _perform_update_graph(ctx, update_id)
    graph.execute()
    ctx.refresh_node_instances()

    dep_up = client.deployment_updates.get(update_id)
    update_instances = dep_up['deployment_update_node_instances']

    install_instances = []
    install_related_instances = []

    if update_instances.get('added_and_related'):
        added_and_related = update_instances['added_and_related']
        install_instances += [
            ctx.get_node_instance(ni['id'])
            for ni in added_and_related
            if ni.get('modification') == 'added'
        ]
        install_related_instances += [
            ctx.get_node_instance(ni['id'])
            for ni in added_and_related
            if ni.get('modification') != 'added'
        ]
    if install_instances:
        _clear_graph(graph)
        lifecycle.install_node_instances(
            graph=graph,
            node_instances=install_instances,
            related_nodes=install_related_instances,
        )
    if update_instances.get('extended_and_related'):
        _clear_graph(graph)
        _establish_relationships(
            ctx, graph, update_instances['extended_and_related'], **kwargs)

    _clear_graph(graph)
    graph = _post_update_graph(ctx, update_id)
    graph.execute()


@workflow
def update_deployment(ctx, *, preview=False, **kwargs):
    client = get_rest_client()
    update_id = '{0}_{1}'.format(ctx.deployment.id, ctx.execution_id)
    graph = _prepare_update_graph(ctx, update_id, **kwargs)
    graph.execute()

    if not preview:
        _execute_deployment_update(ctx, client, update_id, **kwargs)

    client.deployment_updates.set_attributes(
        update_id,
        state='successful'
    )
