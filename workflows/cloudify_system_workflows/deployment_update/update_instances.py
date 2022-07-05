"""Deployment update: node-instance reinstallation

This is the part of the update workflow that makes sure node-instances that
changed are reinstalled.
"""
from cloudify.state import workflow_ctx
from cloudify.plugins import lifecycle

from .utils import clear_graph


def _find_reinstall_instances(steps):
    nodes_to_reinstall = set()
    for step in steps:
        if step['entity_type'] not in ('property', 'operation'):
            continue
        if not step['entity_id'] or step['entity_id'][0] != 'nodes':
            continue
        nodes_to_reinstall.add(step['entity_id'][1])
    to_reinstall = []
    for node_id in nodes_to_reinstall:
        node = workflow_ctx.get_node(node_id)
        to_reinstall.extend(node.instances)
    return to_reinstall


def reinstall_instances(
    graph,
    dep_up,
    to_install,
    to_uninstall,
    ignore_failure=False,
    skip_reinstall=False
):
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
        clear_graph(graph)
        lifecycle.reinstall_node_instances(
            graph=graph,
            node_instances=subgraph,
            related_nodes=intact_nodes,
            ignore_failure=ignore_failure
        )
