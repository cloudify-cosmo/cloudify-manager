"""Deployment update: node-instance reinstallation

This is the part of the update workflow that makes sure node-instances that
changed are updated or reinstalled.
"""
from itertools import chain

from cloudify.state import workflow_ctx
from cloudify.plugins import lifecycle, workflows

from .utils import clear_graph


def _find_changed_instances(steps):
    """Instances that are changed and need to be updated/reinstalled"""
    nodes_to_reinstall = set()
    for step in steps:
        if step['entity_type'] not in ('property', 'operation'):
            continue
        if not step['entity_id'] or step['entity_id'][0] != 'nodes':
            continue
        nodes_to_reinstall.add(step['entity_id'][1])
    changed = set()
    for node_id in nodes_to_reinstall:
        node = workflow_ctx.get_node(node_id)
        changed.update(node.instances)
    return changed


def _get_drift_sources(instance):
    """Drift is defined in system_properties, in several places.

    This yields the instance drift itself, and also drift for each of its
    relationships. This way, we can find if the instance has _any_ drift.
    """
    props = instance.system_properties

    for drift in chain(
        [props.get('configuration_drift')],
        props.get('target_relationships_configuration_drift', {}).values(),
        props.get('source_relationships_configuration_drift', {}).values()
    ):
        if drift:
            yield drift


def _has_drift(instance):
    """Does the instance have any drift, itself of relationship?"""
    for drift in _get_drift_sources(instance):
        if drift.get('result'):
            return True
    return False


def _has_failed_drift_check(instance):
    """Did any of the check_drift calls for the instance fail?"""
    for drift in _get_drift_sources(instance):
        if not drift.get('ok'):
            return True
    return False


def _do_check_drift(ctx, instances):
    """Run the check_drift operation on instances.

    Returns a set of instances that do have drift, and a set of instances
    that failed the drift check (those will need to be reinstalled).
    """
    graph = workflows._make_check_drift_graph(
        ctx, node_instance_ids={ni.id for ni in instances},
        name='update_check_drift',
        ignore_failure=True,
    )
    graph.execute()
    instances_with_drift = set()
    failed_check = set()
    for instance in instances:
        if _has_failed_drift_check(instance):
            failed_check.add(instance)
        elif _has_drift(instance):
            instances_with_drift.add(instance)
    return instances_with_drift, failed_check


def _can_be_updated(instance):
    """Can this instance be updated, or does it need to be reinstalled?

    If this instance defines an update operation, it can be updated. Otherwise,
    we'll need to fall back to reinstalling it.
    """
    props = instance.system_properties

    if props.get('configuration_drift', {}).get('result'):
        if not any(instance.node.has_operation(op) for op in [
            'cloudify.interfaces.lifecycle.update',
            'cloudify.interfaces.lifecycle.update_config',
            'cloudify.interfaces.lifecycle.update_apply',
        ]):
            return False
    # TODO also check relationships drift
    return True


def _find_update_failed_instances(ctx, instances):
    """Find instances that failed the update operation.

    The update_failed flag is set in the failure callback in the update
    subgraph.
    """
    update_failed = set()
    for instance in instances:
        try:
            if instance.system_properties['update_failed'] == ctx.execution_id:
                update_failed.add(instance)
        except KeyError:
            pass
    return update_failed


def _clean_updated_property(ctx, instances):
    for instance in instances:
        system_properties = instance.system_properties or {}
        if 'update_failed' not in system_properties:
            continue
        del system_properties['update_failed']
        ctx.update_node_instance(
            instance.id,
            force=True,
            system_properties=system_properties
        )


def update_or_reinstall_instances(
    ctx,
    graph,
    dep_up,
    to_install,
    to_uninstall,
    ignore_failure=False,
    skip_reinstall=False,
):
    to_skip = set(to_install) | set(to_uninstall)
    consider_for_update = set(workflow_ctx.node_instances) - to_skip
    changed_instances = _find_changed_instances(dep_up.steps)
    instances_with_check_drift = {
        instance
        for instance in consider_for_update
        if instance.node.has_operation(
            'cloudify.interfaces.lifecycle.check_drift'
        )
    }

    must_reinstall = set()
    instances_with_drift = set()
    if instances_with_check_drift:
        clear_graph(graph)
        instances_with_drift, failed_check = _do_check_drift(
            ctx, instances_with_check_drift)
        for instance in failed_check:
            must_reinstall |= instance.get_contained_subgraph()

    # instances that we know have changed, but don't define a way to check
    # drift, are considered to have drifted by default
    instances_with_drift |= changed_instances - instances_with_check_drift
    for instance in instances_with_drift:
        if instance in must_reinstall:
            continue
        if not _can_be_updated(instance):
            must_reinstall |= instance.get_contained_subgraph()

    instances_to_update = instances_with_drift - must_reinstall

    if instances_to_update:
        intact_nodes = set(workflow_ctx.node_instances) - instances_to_update
        clear_graph(graph)
        lifecycle.update_node_instances(
            graph=graph,
            node_instances=instances_to_update,
            related_nodes=intact_nodes,
        )
        failed_update = _find_update_failed_instances(
            ctx,
            {ctx.get_node_instance(ni.id) for ni in instances_to_update},
        )
        _clean_updated_property(ctx, failed_update)
        must_reinstall |= failed_update

    if must_reinstall and not skip_reinstall:
        intact_nodes = (
            set(workflow_ctx.node_instances)
            - must_reinstall
            - set(to_uninstall)
        )
        uninstall_ids = {ni.id for ni in to_uninstall}
        for n in must_reinstall:
            for r in n._relationship_instances:
                if r in uninstall_ids:
                    n._relationship_instances.pop(r)
        clear_graph(graph)
        lifecycle.reinstall_node_instances(
            graph=graph,
            node_instances=must_reinstall,
            related_nodes=intact_nodes,
            ignore_failure=ignore_failure
        )
