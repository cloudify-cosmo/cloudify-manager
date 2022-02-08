from collections import defaultdict
import time
import typing

from cloudify.decorators import workflow
from cloudify.exceptions import NonRecoverableError
from cloudify.state import workflow_ctx, workflow_parameters
from cloudify.models_states import ExecutionState
from cloudify.plugins import lifecycle

from dsl_parser import constants, tasks

from .. import idd
from ..deployment_environment import format_plan_schedule

from .step_extractor import extract_steps


def prepare_plan(*, update_id):
    """Prepare the new deployment plan for a deployment update"""
    dep_up = workflow_ctx.get_deployment_update(update_id)
    if dep_up.new_blueprint_id:
        bp = workflow_ctx.get_blueprint(dep_up.new_blueprint_id)
    else:
        dep = workflow_ctx.get_deployment(dep_up.deployment_id)
        bp = workflow_ctx.get_blueprint(dep.blueprint_id)

    new_inputs = {
        k: v for k, v in dep_up.new_inputs.items()
        if k in bp.plan.get('inputs', {})
    }
    deployment_plan = tasks.prepare_deployment_plan(
        bp.plan,
        workflow_ctx.get_secret,
        new_inputs,
        runtime_only_evaluation=dep_up.runtime_only_evaluation
    )
    workflow_ctx.set_deployment_update_attributes(
        update_id, plan=deployment_plan)


def create_steps(*, update_id):
    """Given a deployment update, extracts the steps for it"""
    dep_up = workflow_ctx.get_deployment_update(update_id)
    deployment = workflow_ctx.get_deployment(dep_up.deployment_id)
    nodes = workflow_ctx.list_nodes(deployment_id=dep_up.deployment_id)

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

    workflow_ctx.set_deployment_update_attributes(
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


def _diff_node_attrs(new_nodes, old_nodes):
    """Check additional node attributes and return which ones changed.

    This is for auxillary attributes that don't generate a Step.
    """
    for new_node in new_nodes:
        node_id = new_node['id']
        old_node = old_nodes.get(node_id)
        if not old_node:
            continue
        if new_node.get('capabilities') != old_node.get('capabilities'):
            yield node_id, ['capabilities']


def _diff_planned_instances(new_nodes, old_nodes):
    """Check for which nodes the planned instance count has changed"""
    for new_node in new_nodes:
        node_id = new_node['id']
        old_node = old_nodes.get(node_id)
        if not old_node:
            continue
        try:
            new_planned = new_node['capabilities']['scalable']['properties'][
                'planned_instances']
        except KeyError:
            continue
        if new_planned != old_node.planned_number_of_instances:
            yield node_id, new_planned


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
    dep_up = workflow_ctx.get_deployment_update(update_id)
    deployment = workflow_ctx.get_deployment(dep_up.deployment_id)
    old_nodes = workflow_ctx.list_nodes(deployment_id=dep_up.deployment_id)
    new_nodes = dep_up.deployment_plan['nodes'].copy()
    old_instances = workflow_ctx.list_node_instances(
        deployment_id=dep_up.deployment_id)
    node_changes = {
        'modify_attributes': _modified_attr_nodes(dep_up.steps),
        'add': _added_nodes(dep_up.steps),
        'remove': _removed_nodes(dep_up.steps),
    }

    old_nodes_by_id = {node.id: node for node in old_nodes}
    for node_id, changed_attrs in _diff_node_attrs(
        new_nodes, old_nodes_by_id
    ):
        node_changes['modify_attributes'][node_id] += changed_attrs
    modified_nodes = {}
    for node_id, instance_count in _diff_planned_instances(
        new_nodes, old_nodes_by_id
    ):
        modified_nodes[node_id] = {'instances': instance_count}

    instance_changes = tasks.modify_deployment(
        nodes=new_nodes,
        previous_nodes=old_nodes,
        previous_node_instances=old_instances,
        scaling_groups=deployment.scaling_groups,
        modified_nodes=modified_nodes
    )

    instance_changes['relationships_changed'] = \
        _relationship_changed_nodes(dep_up.steps)
    workflow_ctx.set_deployment_update_attributes(
        update_id,
        nodes=node_changes,
        node_instances=instance_changes
    )


def prepare_plugin_changes(*, update_id):
    dep_up = workflow_ctx.get_deployment_update(update_id)
    old_nodes = workflow_ctx.list_nodes(deployment_id=dep_up.deployment_id)
    old_nodes_by_id = {node.id: node for node in old_nodes}
    new_nodes = dep_up.deployment_plan['nodes']

    deleted_central_plugins = []
    deleted_host_plugins = {}

    if dep_up.new_blueprint_id:
        old_bp = workflow_ctx.get_blueprint(dep_up.old_blueprint_id)
        old_dep_plugins = old_bp.plan[constants.DEPLOYMENT_PLUGINS_TO_INSTALL]
        new_dep_plugins = dep_up.deployment_plan[
            constants.DEPLOYMENT_PLUGINS_TO_INSTALL]
        old_wf_plugins = old_bp.plan[constants.WORKFLOW_PLUGINS_TO_INSTALL]
        new_wf_plugins = dep_up.deployment_plan[
            constants.WORKFLOW_PLUGINS_TO_INSTALL]
        new_plugins = new_dep_plugins + new_wf_plugins
        old_plugins = old_dep_plugins + old_wf_plugins
        for plugin in old_plugins:
            if plugin[constants.PLUGIN_EXECUTOR_KEY] != \
                    constants.CENTRAL_DEPLOYMENT_AGENT:
                continue
            if plugin not in new_plugins and \
                    plugin not in deleted_central_plugins:
                deleted_central_plugins.append(plugin)

    for node in new_nodes:
        old_node = old_nodes_by_id.get(node['id'])
        if old_node is None:
            continue
        for plugin in old_node.plugins:
            if plugin not in node['plugins']:
                deleted_host_plugins.setdefault(node['id'], []).append(plugin)

    node_changes = dep_up['deployment_update_nodes']
    node_changes['host_plugins_to_uninstall'] = deleted_host_plugins
    # we store central plugins to uninstall, although we don't currently
    # actually uninstall them. They can be uninstalled by the user if
    # explicitly requested, by removing the plugin.
    node_changes['cda_plugins_to_uninstall'] = deleted_central_plugins

    workflow_ctx.set_deployment_update_attributes(
        update_id,
        nodes=node_changes,
    )


def _prepare_update_graph(
        ctx,
        update_id,
        **kwargs):
    """Make a tasks-graph that prepares the deployment-update.

    Those operations only plan the update and prepare the
    things-to-be-changed. They're safe to be rerun any number of times.
    """
    graph = ctx.graph_mode()
    seq = graph.sequence()
    seq.add(
        ctx.local_task(prepare_plan, kwargs={
            'update_id': update_id,
        }, total_retries=0),
        ctx.local_task(create_steps, kwargs={
            'update_id': update_id,
        }, total_retries=0),
        ctx.local_task(prepare_update_nodes, kwargs={
            'update_id': update_id,
        }, total_retries=0),
        ctx.local_task(prepare_plugin_changes, kwargs={
            'update_id': update_id,
        }, total_retries=0),
    )
    return graph


def update_deployment_nodes(*, update_id):
    """Bring deployment nodes in line with the plan.

    Create new nodes, update existing modified nodes.
    """
    dep_up = workflow_ctx.get_deployment_update(update_id)
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
            attr_name: plan_node[attr_name] for attr_name in set(changed_attrs)
        }
        if 'relationships' in new_attributes:
            # if we're to remove a relationship, make sure to keep it for now,
            # so that unlink operations can run; we'll actually remove it in
            # the post-graph
            old_node = workflow_ctx.get_node(node_name)
            new_rel_keys = {
                (r['target_id'], r['type'])
                for r in new_attributes['relationships']
            }
            for old_rel in old_node.relationships:
                old_rel_key = (old_rel.target_id, old_rel.type)
                if old_rel_key not in new_rel_keys:
                    new_attributes['relationships'].append(
                        old_rel._relationship)
            for rel in new_attributes['relationships']:
                rel.pop('source_interfaces', None)
                rel.pop('target_interfaces', None)
        workflow_ctx.update_node(
            dep_up.deployment_id,
            node_name,
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
    workflow_ctx.create_nodes(
        dep_up.deployment_id,
        create_nodes
    )


def _format_instance_relationships(node_instance):
    """Dump ni's relationships to a dict that can be parsed by RESTservice"""
    return [
        {
            'target_id': old_rel.target_id,
            'target_name': old_rel.relationship.target_node.id,
            'type': old_rel.relationship.type,
        }
        for old_rel in node_instance.relationships
        if old_rel.relationship and old_rel.relationship.target_node
    ]


def _relationship_changed_nodes(steps):
    """Names of the nodes that have had any of their relationships changed"""
    nodes = set()
    for step in steps:
        if step['entity_type'] != 'relationship':
            continue
        parts = step['entity_id'].split(':')
        nodes_label, node_id, relationships_label = parts[:3]
        if nodes_label != 'nodes' or relationships_label != 'relationships':
            continue
        nodes.add(node_id)
    return list(nodes)


def update_deployment_node_instances(*, update_id):
    dep_up = workflow_ctx.get_deployment_update(update_id)

    update_instances = dep_up['deployment_update_node_instances']
    if update_instances.get('added_and_related'):
        added_instances = [
            ni for ni in update_instances['added_and_related']
            if ni.get('modification') == 'added'
        ]
        workflow_ctx.create_node_instances(
            dep_up.deployment_id,
            added_instances
        )
    if update_instances.get('extended_and_related'):
        for ni in update_instances['extended_and_related']:
            if ni.get('modification') != 'extended':
                continue
            old_rels = _format_instance_relationships(
                workflow_ctx.get_node_instance(ni['id']))
            workflow_ctx.update_node_instance(
                ni['id'],
                relationships=old_rels + ni['relationships'],
                force=True
            )


def delete_removed_relationships(*, update_id):
    workflow_ctx.refresh_node_instances()
    dep_up = workflow_ctx.get_deployment_update(update_id)
    update_nodes = dep_up['deployment_update_nodes'] or {}
    plan_nodes = {
        node['id']: node for node in dep_up.deployment_plan['nodes']
    }
    update_instances = dep_up['deployment_update_node_instances']

    for node_name, changed_attrs in update_nodes.get(
            'modify_attributes', {}).items():
        if 'relationships' in changed_attrs:
            plan_node = plan_nodes[node_name]
            new_relationships = plan_node['relationships']
            for rel in new_relationships:
                rel.pop('source_interfaces', None)
                rel.pop('target_interfaces', None)
            workflow_ctx.update_node(
                dep_up.deployment_id, node_name,
                relationships=new_relationships
            )

    for node_name in update_instances.get('relationships_changed', []):
        node = plan_nodes[node_name]
        for instance in workflow_ctx.get_node(node_name).instances:
            if not instance:
                continue
            new_rels = _reorder_instance_relationships(
                node['relationships'],
                _format_instance_relationships(instance)
            )
            workflow_ctx.update_node_instance(
                instance.id,
                relationships=new_rels,
                force=True
            )


_T = typing.TypeVar('T')
_KT = typing.TypeVar('KT')


def _indexed_by(
    items: typing.Sequence[_T],
    key_func: typing.Callable[[_T], _KT]
) -> typing.Iterable[typing.Tuple[_T, _KT, int]]:
    """Index items by return of key_func

    This yields tuples of (item, key, count), where key is the result of
    calling key_func(item), and count says which item is it, when checking
    by the key.
    Eg. if items=[{'a': c}, {'a': d}, {'a': c}], and key_func=itemgetter('a'),
    then the result is going to be:
        - {'a': 1}, c, 0
        - {'a': 2}, d, 0
        - {'a': 1}, c, 1
    """
    seen: typing.MutableMapping[_KT, int] = defaultdict(int)
    for item in items:
        key = key_func(item)
        yield item, key, seen[key]
        seen[key] += 1


def _reorder_instance_relationships(plan_rels, instance_rels):
    """Given instance relationships, reorder them based on the plan.

    Change the ordering of the relationships, and drop relationships
    that don't exist in the plan.
    """
    instance_rels_keyed = {
        (key, count): rel
        for rel, key, count in _indexed_by(
            instance_rels, lambda r: (r['type'], r['target_name']))
    }

    new_instance_rels = []
    for _, key, count in _indexed_by(
        plan_rels,
        lambda r: (r['type'], r['target_id'])
    ):
        instance_rel = instance_rels_keyed.get((key, count))
        if instance_rel:
            new_instance_rels.append(instance_rel)
    return new_instance_rels


def _updated_deployment_labels(existing_labels, plan_labels):
    if not plan_labels:
        return []
    changed = False
    labels = {(lab.key, lab.value) for lab in existing_labels}
    for plan_label, label_definition in plan_labels.items():
        for value in label_definition.get('values', []):
            new_label = (plan_label, value)
            if new_label not in labels:
                changed = True
                labels.add(new_label)
    if not changed:
        return None
    return [{k: v} for k, v in labels]


def set_deployment_attributes(*, update_id):
    dep_up = workflow_ctx.get_deployment_update(update_id)
    deployment = workflow_ctx.get_deployment(dep_up.deployment_id)
    new_attributes = {
        'workflows': dep_up.deployment_plan['workflows'],
        'outputs': dep_up.deployment_plan['outputs'],
        'description': dep_up.deployment_plan['description'],
        'capabilities': dep_up.deployment_plan['capabilities'],
        'inputs': dep_up.deployment_plan['inputs'],
        'runtime_only_evaluation': dep_up.runtime_only_evaluation,
    }
    if dep_up.new_blueprint_id:
        new_attributes['blueprint_id'] = dep_up.new_blueprint_id
        # in the currently-running execution, update the current context as
        # well, so that later graphs downlood scripts from the new blueprint.
        # Unfortunate, but no public method for this just yet
        workflow_ctx._context['blueprint_id'] = dep_up.new_blueprint_id

    new_labels = _updated_deployment_labels(
        deployment.labels,
        dep_up.deployment_plan.get('labels')
    )
    if new_labels:
        new_attributes['labels'] = new_labels

    workflow_ctx.set_deployment_attributes(
        dep_up.deployment_id,
        **new_attributes
    )


def update_inter_deployment_dependencies(*, ctx, update_id):
    dep_up = ctx.get_deployment_update(update_id)
    idd.update(ctx, dep_up.deployment_plan)


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
        ctx.local_task(update_inter_deployment_dependencies, kwargs={
            'ctx': ctx, 'update_id': update_id,
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
    dep_up = workflow_ctx.get_deployment_update(update_id)

    update_nodes = dep_up['deployment_update_nodes'] or {}
    for node_path in update_nodes.get('remove', []):
        node_name = node_path.split(':')[-1]
        workflow_ctx.delete_node(dep_up.deployment_id, node_name)


def delete_removed_instances(*, update_id):
    dep_up = workflow_ctx.get_deployment_update(update_id)

    update_instances = dep_up['deployment_update_node_instances']
    if update_instances.get('removed_and_related'):
        removed_instances = [
            ni for ni in update_instances['removed_and_related']
            if ni.get('modification') == 'removed'
        ]
        for ni in removed_instances:
            workflow_ctx.delete_node_instance(ni['id'])


def update_schedules(*, update_id):
    dep_up = workflow_ctx.get_deployment_update(update_id)
    new_schedules = (
        dep_up.deployment_plan
        .get('deployment_settings', {})
        .get('default_schedules')
    )
    if not new_schedules:
        # we are not going to be deleting schedules that are now missing,
        # because we can't tell if they were added by the user explicitly
        return
    new_schedule_ids = set(new_schedules)
    old_schedule_ids = {s['id'] for s in workflow_ctx.list_execution_schedules(
        deployment_id=dep_up.deployment_id, _include=['id'])}

    for changed_id in old_schedule_ids & new_schedule_ids:
        schedule = format_plan_schedule(new_schedules[changed_id].copy())
        workflow_ctx.update_execution_schedule(
            changed_id, dep_up.deployment_id, **schedule)

    for added_id in new_schedule_ids - old_schedule_ids:
        schedule = format_plan_schedule(new_schedules[added_id].copy())
        workflow_ctx.create_execution_schedule(
            added_id, dep_up.deployment_id, **schedule)


def update_operations(*, update_id):
    dep_up = workflow_ctx.get_deployment_update(update_id)
    workflow_ctx._update_operation_inputs()
    for step in dep_up.steps:
        if step.get('entity_type') != 'operation':
            continue
        parts = step['entity_id'].split(':')
        if len(parts) == 4:
            # eg: nodes:node2:operations:cloudify.interfaces.lifecycle.start
            _, node_id, _, op_name = parts
            workflow_ctx._update_operation_inputs(
                deployment_id=dep_up.deployment_id,
                node_id=node_id, operation=op_name)
        elif len(parts) == 6:
            # eg: nodes:node2:relationships:[0]:target_operations:
            #     cloudify.interfaces.relationship_lifecycle.establish
            _, node_id, _, rel_index, source_or_target, op_name = parts
            rel_index = int(rel_index.strip('[]'))
            workflow_ctx._update_operation_inputs(
                deployment_id=dep_up.deployment_id,
                node_id=node_id, operation=op_name, key=source_or_target,
                rel_index=rel_index)


def _get_uninstall_plugins_tasks(ctx, update_id):
    """Prepare all the plugin uninstall tasks

    Based on the update, find which plugins need to be uninstalled,
    and prepare tasks to uninstall them, targeted at the host nodes
    that hold these plugins.
    """
    dep_up = workflow_ctx.get_deployment_update(update_id)
    deleted_host_plugins = dep_up['deployment_update_nodes'].get(
        'host_plugins_to_uninstall', {})
    for node_id, deleted_plugins in deleted_host_plugins.items():
        node = workflow_ctx.get_node(node_id)
        for instance in node.instances:
            task = lifecycle.plugins_uninstall_task(instance, deleted_plugins)
            if task:
                yield task


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
        ctx.local_task(delete_removed_relationships, kwargs={
            'update_id': update_id,
        }, total_retries=0),
        ctx.local_task(delete_removed_instances, kwargs={
            'update_id': update_id,
        }, total_retries=0),
        ctx.local_task(update_schedules, kwargs={
            'update_id': update_id,
        }, total_retries=0),
        ctx.local_task(update_operations, kwargs={
            'update_id': update_id,
        }, total_retries=0),
    )
    for task in _get_uninstall_plugins_tasks(ctx, update_id):
        seq.add(task)
    return graph


def _clear_graph(graph):
    for task in graph.tasks:
        graph.remove_task(task)


def _unlink_relationships(ctx, graph, install_params):
    node_instances = (
        install_params.reduced_instances
        + install_params.reduced_target_instances
    )

    modified_relationship_ids = defaultdict(list)
    for ni in install_params.reduced:
        node_id = ni['node_id']
        for new_rel in ni['relationships']:
            modified_relationship_ids[node_id].append(new_rel['target_name'])
    lifecycle.execute_unlink_relationships(
        graph=graph,
        node_instances=set(node_instances),
        modified_relationship_ids=modified_relationship_ids
    )


def _establish_relationships(ctx, graph, install_params):
    node_instances = (
        install_params.extended_instances
        + install_params.extended_target_instances
    )

    modified_relationship_ids = defaultdict(list)
    for ni in install_params.extended:
        node_id = ni['node_id']
        for new_rel in ni['relationships']:
            modified_relationship_ids[node_id].append(new_rel['target_name'])
    lifecycle.execute_establish_relationships(
        graph=graph,
        node_instances=set(node_instances),
        modified_relationship_ids=modified_relationship_ids
    )


def _find_reinstall_instances(steps):
    nodes_to_reinstall = set()
    for step in steps:
        if step['entity_type'] not in ('property', 'operation'):
            continue
        modified = step['entity_id'].split(':')
        if not modified or modified[0] != 'nodes':
            continue
        nodes_to_reinstall.add(modified[1])
    to_reinstall = []
    for node_id in nodes_to_reinstall:
        node = workflow_ctx.get_node(node_id)
        to_reinstall.extend(node.instances)
    return to_reinstall


def _reinstall_instances(graph, dep_up, to_install, to_uninstall,
                         ignore_failure=False, skip_reinstall=False):
    install_ids = {ni.id for ni in to_install}
    uninstall_ids = {ni.id for ni in to_uninstall}
    skip_ids = install_ids | uninstall_ids
    subgraph = set()
    if skip_reinstall:
        to_reinstall = []
    else:
        to_reinstall = _find_reinstall_instances(dep_up.steps)
    for ni in to_reinstall:
        if ni.id in skip_ids:
            continue
        subgraph |= ni.get_contained_subgraph()
    subgraph -= set(to_uninstall)
    intact_nodes = (
        set(workflow_ctx.node_instances)
        - subgraph
        - set(to_uninstall)
    )
    for n in subgraph:
        for r in n._relationship_instances:
            if r in uninstall_ids:
                n._relationship_instances.pop(r)
    if subgraph:
        _clear_graph(graph)
        lifecycle.reinstall_node_instances(
            graph=graph,
            node_instances=subgraph,
            related_nodes=intact_nodes,
            ignore_failure=ignore_failure
        )


class InstallParameters:
    """Packaged parameters for the install part of the workflow.

    This is to be given to the install part, or to the custom workflow
    provided by the user. All the install/uninstall/reinstall parameters
    are encapsulated in this.
    """
    update_id: str

    added: list
    added_targets: list
    added_ids: list
    added_target_ids: list
    added_instances: list
    added_target_instances: list

    removed: list
    removed_ids: list
    removed_target_ids: list
    removed_targets: list
    removed_instances: list
    removed_target_instances: list

    extended: list
    extended_ids: list
    extended_target_ids: list
    extended_targets: list
    extended_instances: list
    extended_target_instances: list

    reduced: list
    reduced_ids: list
    reduced_target_ids: list
    reduced_targets: list
    reduced_instances: list
    reduced_target_instances: list

    ignore_failure: bool
    skip_reinstall: list

    def __init__(self, ctx, update_params, dep_update):
        self._update_instances = dep_update['deployment_update_node_instances']
        self.update_id = dep_update.id
        self.steps = dep_update.steps

        for kind in ['added', 'removed', 'extended', 'reduced']:
            changed, related = self._split_by_modification(
                self._update_instances.get(f'{kind}_and_related'),
                kind,
            )
            changed_ids = [item['id'] for item in changed]
            related_ids = [item['id'] for item in related]
            changed_instances = [
                ctx.get_node_instance(ni_id) for ni_id in changed_ids
            ]
            related_instances = [
                ctx.get_node_instance(ni_id) for ni_id in related_ids
            ]
            setattr(self, kind, changed)
            setattr(self, f'{kind}_targets', related)
            setattr(self, f'{kind}_ids', changed_ids)
            setattr(self, f'{kind}_target_ids', related_ids)
            setattr(self, f'{kind}_instances', changed_instances)
            setattr(self, f'{kind}_target_instances', related_instances)

        for param, default in [
            ('ignore_failure', False),
            ('skip_install', False),
            ('skip_uninstall', False),
            ('skip_reinstall', []),
        ]:
            setattr(self, param, update_params.get(param, default))

    def _modified_entity_ids(self):
        modified_ids = {
            'node': [],
            'relationship': {},
            'property': [],
            'operation': [],
            'workflow': [],
            'output': [],
            'description': [],
            'group': [],
            'policy_type': [],
            'policy_trigger': [],
            'plugin': [],
            'rel_mappings': {}
        }
        for step in self.steps:
            entity_type = step['entity_type']
            parts = step['entity_id'].split(':')
            if len(parts) < 2:
                continue
            entity_id = parts[1]

            if step['entity_type'] == 'relationship':
                relationship = parts[3]
                modified_ids[entity_type].setdefault(entity_id, []).append(
                    relationship)
            elif entity_type in modified_ids:
                modified_ids[entity_type].append(entity_id)
        return modified_ids

    def _split_by_modification(self, items, modification):
        first, second = [], []
        if not items:
            return first, second
        for instance in items:
            if instance.get('modification') == modification:
                first.append(instance)
            else:
                second.append(instance)
        return first, second

    def as_workflow_parameters(self):
        return {
            'update_id': self.update_id,
            'modified_entity_ids': self._modified_entity_ids(),
            'added_instance_ids': self.added_ids,
            'added_target_instances_ids': self.added_target_ids,
            'removed_instance_ids': self.removed_ids,
            'remove_target_instance_ids': self.removed_target_ids,
            'extended_instance_ids': self.extended_ids,
            'extend_target_instance_ids': self.extended_target_ids,
            'reduced_instance_ids': self.reduced_ids,
            'reduce_target_instance_ids': self.reduced_target_ids,
            'skip_install': self.skip_install,
            'skip_uninstall': self.skip_uninstall,
            'ignore_failure': self.ignore_failure,
            'install_first': False,
            'node_instances_to_reinstall': None,
            'central_plugins_to_install': None,
            'central_plugins_to_uninstall': None,
            'update_plugins': True
        }


def _execute_deployment_update(ctx, update_id, install_params):
    """Do the "install" part of the dep-update.

    This installs, uninstalls, and reinstalls the node-instances as
    necessary. Relationships are established and unlinked as needed as well.`
    """
    graph = ctx.graph_mode()

    dep_up = workflow_ctx.get_deployment_update(update_id)

    if install_params.reduced and not install_params.skip_uninstall:
        _clear_graph(graph)
        _unlink_relationships(ctx, graph, install_params)

    if install_params.removed and not install_params.skip_uninstall:
        _clear_graph(graph)
        lifecycle.uninstall_node_instances(
            graph=graph,
            ignore_failure=install_params.ignore_failure,
            node_instances=install_params.removed_instances,
            related_nodes=install_params.removed_target_instances,
        )
    if install_params.added and not install_params.skip_install:
        _clear_graph(graph)
        lifecycle.install_node_instances(
            graph=graph,
            node_instances=install_params.added_instances,
            related_nodes=install_params.added_target_instances,
        )
    if install_params.extended and not install_params.skip_install:
        _clear_graph(graph)
        _establish_relationships(ctx, graph, install_params)

    _reinstall_instances(
        graph,
        dep_up,
        install_params.added_instances,
        install_params.removed_instances,
        ignore_failure=install_params.ignore_failure,
        skip_reinstall=install_params.skip_reinstall,
    )


def _execute_custom_workflow(dep_up, workflow_id, install_params,
                             custom_workflow_timeout=None):
    execution = workflow_ctx.start_execution(
        dep_up.deployment_id,
        workflow_id,
        parameters=install_params.as_workflow_parameters(),
        allow_custom_parameters=True,
        force=True
    )
    if custom_workflow_timeout:
        deadline = time.time() + custom_workflow_timeout
    else:
        deadline = None
    while True:
        execution = workflow_ctx.get_execution(execution.id)
        if execution.status in ExecutionState.END_STATES:
            if execution.status != ExecutionState.TERMINATED:
                NonRecoverableError(
                    f'{workflow_id} is in state {execution.status}')
            break
        time.sleep(1)
        if deadline and time.time() > deadline:
            raise NonRecoverableError(f'Timeout running {workflow_id}')


@workflow
def update_deployment(ctx, *, update_id=None, preview=False,
                      ignore_failure=False,
                      skip_reinstall=False, workflow_id=None,
                      custom_workflow_timeout=None, **kwargs):
    graph = _prepare_update_graph(ctx, update_id, **kwargs)
    graph.execute()

    if not preview:
        _clear_graph(graph)
        graph = _perform_update_graph(ctx, update_id)
        graph.execute()
        ctx.refresh_node_instances()
        dep_up = workflow_ctx.get_deployment_update(update_id)
        install_params = InstallParameters(ctx, workflow_parameters, dep_up)
        if workflow_id:
            _execute_custom_workflow(dep_up, workflow_id,
                                     install_params, custom_workflow_timeout)
        else:
            _execute_deployment_update(ctx, update_id, install_params)

        _clear_graph(graph)
        graph = _post_update_graph(ctx, update_id)
        graph.execute()

    workflow_ctx.set_deployment_update_attributes(
        update_id,
        state='successful'
    )
