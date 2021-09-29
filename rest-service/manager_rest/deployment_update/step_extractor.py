#########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

import operator

from functools import total_ordering
from contextlib import contextmanager

import networkx as nx

RELEVANT_DEPLOYMENT_FIELDS = ['blueprint_id', 'id', 'inputs', 'nodes',
                              'outputs', 'workflows', 'groups', 'policy_types',
                              'policy_triggers', 'description',
                              'deployment_plugins_to_install',
                              'workflow_plugins_to_install']

DEFAULT_TOPOLOGY_LEVEL = 0
NODE = 'node'
NODES = 'nodes'
OUTPUT = 'output'
OUTPUTS = 'outputs'
TYPE = 'type'
HOST_ID = 'host_id'
OPERATION = 'operation'
OPERATIONS = 'operations'
RELATIONSHIP = 'relationship'
RELATIONSHIPS = 'relationships'
TARGET_ID = 'target_id'
SOURCE_OPERATIONS = 'source_operations'
TARGET_OPERATIONS = 'target_operations'
PROPERTY = 'property'
PROPERTIES = 'properties'
WORKFLOW = 'workflow'
WORKFLOWS = 'workflows'
GROUP = 'group'
GROUPS = 'groups'
POLICY_TYPE = 'policy_type'
POLICY_TYPES = 'policy_types'
POLICY_TRIGGER = 'policy_trigger'
POLICY_TRIGGERS = 'policy_triggers'
DEPLOYMENT_PLUGINS_TO_INSTALL = 'deployment_plugins_to_install'
PLUGIN = 'plugin'
PLUGINS = 'plugins'
PLUGINS_TO_INSTALL = 'plugins_to_install'
DESCRIPTION = 'description'
CONTAINED_IN_RELATIONSHIP_TYPE = 'cloudify.relationships.contained_in'
TYPE_HIERARCHY = 'type_hierarchy'
# flake8: noqa


@total_ordering
class DeploymentUpdateStep(object):
    def __init__(self,
                 action,
                 entity_type,
                 entity_id,
                 supported=True,
                 topology_order=DEFAULT_TOPOLOGY_LEVEL):
        self.action = action
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.supported = supported
        self.topology_order = topology_order

    @property
    def entity_name(self):
        return self.entity_id.split(':')[-1]

    def __hash__(self):
        return hash(self.entity_id)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        else:
            return False

    def __str__(self):
        return str(self.__dict__)

    def __repr__(self):
        return self.__str__()

    def __lt__(self, other):
        """Is this step considered "smaller" than the other step?

        This is used for sorting the steps, ie. steps that are smaller
        come earlier, and will be executed first.
        """
        if self.action != other.action:
            # the order is 'remove' < 'add' < 'modify'
            actions = ['remove', 'add', 'modify']
            return actions.index(self.action) < actions.index(other.action)
        if self.action == 'add':
            if self.entity_type == NODE:
                if other.entity_type == RELATIONSHIP:
                    # add node before adding relationships
                    return True
                if other.entity_type == NODE:
                    # higher topology order before lower topology order
                    return self.topology_order > other.topology_order
        if self.action =='remove':
            # remove relationships before removing nodes
            if self.entity_type == RELATIONSHIP and other.entity_type == NODE:
                return True
        return False


def _is_contained_in_changed(node, other_node):
    node_container = next(
        (r['target_id'] for r in node['relationships']
         if CONTAINED_IN_RELATIONSHIP_TYPE in r[TYPE_HIERARCHY]), None)
    other_node_container = next(
        (r['target_id'] for r in other_node['relationships']
         if CONTAINED_IN_RELATIONSHIP_TYPE in r[TYPE_HIERARCHY]), None)
    return node_container != other_node_container


def _create_steps(nodes, deployment, new_plan):
    if new_plan[DESCRIPTION] != deployment.description:
        yield DeploymentUpdateStep(
            action='modify',
            entity_type=DESCRIPTION,
            entity_id=DESCRIPTION,
        )
    new_nodes = {node['id']: node for node in new_plan[NODES]}
    yield from _extract_host_agent_plugins_steps(new_nodes, nodes)
    yield from _diff_nodes(new_nodes, nodes)
    for action, key in _diff_dicts(new_plan[OUTPUTS], deployment.outputs):
        yield DeploymentUpdateStep(
            action=action,
            entity_type=OUTPUT,
            entity_id=f'{OUTPUTS}:{key}'
        )
    for action, key in _diff_dicts(new_plan[WORKFLOWS], deployment.workflows):
        yield DeploymentUpdateStep(
            action=action,
            entity_type=WORKFLOW,
            entity_id=f'{WORKFLOWS}:{key}'
        )
    for action, key in _diff_dicts(
                new_plan[POLICY_TYPES], deployment.policy_types):
        yield DeploymentUpdateStep(
            action=action,
            entity_type=POLICY_TYPE,
            entity_id=f'{POLICY_TYPES}:{key}',
            supported=False
        )
    for action, key in _diff_dicts(
                new_plan[POLICY_TRIGGERS],
                deployment.policy_triggers):
        yield DeploymentUpdateStep(
            action=action,
            entity_type=POLICY_TRIGGER,
            entity_id=f'{POLICY_TRIGGERS}:{key}',
            supported=False
        )
    for action, key in _diff_dicts(
            new_plan[GROUPS], deployment.groups,
            compare=_compare_groups
        ):
        yield DeploymentUpdateStep(
            action=action,
            entity_type=GROUP,
            entity_id=f'{GROUPS}:{key}',
            supported=False
        )


def _extract_host_agent_plugins_steps(new_nodes, old_nodes):
    # We want to update both the node's `plugins_to_install` and `plugins`
    for entity_type in (PLUGINS_TO_INSTALL, PLUGINS):
        for new_node_name, new_node in new_nodes.items():
            new_plugins = new_node.get(entity_type) or []

            # If it's a new node, the plugin will be installed anyway
            if not new_plugins or new_node_name not in old_nodes:
                continue

            old_node = old_nodes[new_node_name]
            old_plugins = old_node.get(entity_type) or []
            if old_node.get(entity_type) == new_node.get(entity_type):
                continue
            for new_plugin in new_plugins:
                old_plugin = _find_matching_plugin(new_plugin, old_plugins)
                if old_plugin == new_plugin:
                    continue

                entity_id =\
                    f'{entity_type}:{new_node_name}:{new_plugin["name"]}'
                action = 'add' if not old_plugin else 'modify'
                yield DeploymentUpdateStep(
                    action=action,
                    entity_type=PLUGIN,
                    entity_id=entity_id,
                )


def _find_matching_plugin(new_plugin, old_plugins):
    for old_plugin in old_plugins:
        if (old_plugin['name'] == new_plugin['name'] and
                old_plugin['executor'] == new_plugin['executor']):
            return old_plugin
    return None


def _diff_nodes(new_nodes, old_nodes):
    for node_name, node in new_nodes.items():
        if node_name not in old_nodes:
            yield DeploymentUpdateStep(
                action='add',
                entity_type=NODE,
                entity_id=f'{NODES}:{node_name}',
            )
            continue
        old_node = old_nodes[node_name]
        if node[TYPE] != old_node[TYPE] or \
                _is_contained_in_changed(node, old_node):
            # a node that changed its type or its host_id
            # counts as a different node
            yield DeploymentUpdateStep(
                action='modify',
                entity_type=NODE,
                entity_id=f'{NODES}:{node_name}',
                supported=False
            )
            # Since the node was classified as added or
            # removed, there is no need to compare its other
            # fields.
            continue
        yield from _diff_node(node_name, node, old_node)
    for node_name in old_nodes:
        if node_name not in new_nodes:
            yield DeploymentUpdateStep(
                action='remove',
                entity_type=NODE,
                entity_id=f'{NODES}:{node_name}',
            )


def _diff_node(node_name, new_node, old_node):
    for action, key in _diff_dicts(new_node[OPERATIONS], old_node[OPERATIONS]):
        yield DeploymentUpdateStep(
            action=action,
            entity_type=OPERATION,
            entity_id=f'{NODES}:{node_name}:{OPERATIONS}:{key}'
        )

    for rel_index, relationship in enumerate(new_node[RELATIONSHIPS]):
        entity_id_base = f'{NODES}:{node_name}:{RELATIONSHIPS}'
        old_relationship, old_rel_index = \
            _get_matching_relationship(
                old_node[RELATIONSHIPS],
                relationship[TYPE],
                relationship[TARGET_ID])
        if old_relationship is None:
            yield DeploymentUpdateStep(
                action='add',
                entity_type=RELATIONSHIP,
                entity_id=f'{entity_id_base}:[{rel_index}]',
            )
            continue

        if old_rel_index != rel_index:
            yield DeploymentUpdateStep(
                action='modify',
                entity_type=RELATIONSHIP,
                entity_id=f'{entity_id_base}:[{old_rel_index}]:[{rel_index}]',
            )

        for op_type in [SOURCE_OPERATIONS, TARGET_OPERATIONS]:
            for action, key in _diff_dicts(
                    relationship.get(op_type), old_relationship.get(op_type)):
                yield DeploymentUpdateStep(
                    action=action,
                    entity_type=OPERATION,
                    entity_id=f'{entity_id_base}:[{rel_index}]:{op_type}:{key}'
                )
        for action, key in _diff_dicts(
                relationship.get(PROPERTIES),
                old_relationship.get(PROPERTIES)):
            # modifying relationship properties is not  supported yet
            yield DeploymentUpdateStep(
                action=action,
                entity_type=PROPERTY,
                entity_id=f'{entity_id_base}:[{rel_index}]:{PROPERTIES}:{key}',
                supported=False,
            )
    for rel_index, relationship in enumerate(old_node[RELATIONSHIPS]):
        entity_id_base = f'{NODES}:{node_name}:{RELATIONSHIPS}'
        matching_relationship, _ = \
            _get_matching_relationship(
                new_node[RELATIONSHIPS],
                relationship[TYPE],
                relationship[TARGET_ID])
        if matching_relationship is None:
            yield DeploymentUpdateStep(
                action='remove',
                entity_type=RELATIONSHIP,
                entity_id=f'{entity_id_base}:[{rel_index}]',
            )

    for action, key in _diff_dicts(new_node[PROPERTIES], old_node[PROPERTIES]):
        yield DeploymentUpdateStep(
            action=action,
            entity_type=PROPERTY,
            entity_id=f'{NODES}:{node_name}:{PROPERTIES}:{key}'
        )


def _diff_operations(entity_id_base, operations, old_operations):
    for op_name in set(operations) | set(old_operations):
        new_operation = operations.get(op_name)
        old_operation = old_operations.get(op_name)
        if new_operation is not None and old_operation is None:
            action = 'add'
        elif new_operation is None and old_operation is not None:
            action = 'remove'
        elif new_operation != old_operation:
            action = 'modify'
        else:
            continue
        yield DeploymentUpdateStep(
            action=action,
            entity_type=OPERATION,
            entity_id=f'{entity_id_base}:{op_name}',
        )


def _diff_dicts(new, old, compare=operator.eq):
    new = new or {}
    old = old or {}
    for key in set(new) | set(old):
        if key in new and key not in old:
            yield 'add', key
        elif key in old and key not in new:
            yield 'remove', key
        elif not compare(new[key], old[key]):
            yield 'modify', key


def _compare_groups(new, old):
    old_clone = old.copy()
    new_clone = new.copy()
    old_members = set(old_clone.pop('members', ()))
    new_members = set(new_clone.pop('members', ()))
    return old_members == new_members and old_clone == new_clone


def _get_matching_relationship(relationships, rel_type, target_id):
    for rel_index, other_relationship in enumerate(relationships):
        other_r_type = other_relationship[TYPE]
        other_target_id = other_relationship[TARGET_ID]
        if rel_type == other_r_type and other_target_id == target_id:
            return other_relationship, rel_index
    return None, None


def _extract_added_nodes_names(supported_steps):
    add_node_steps = [step for step in supported_steps
                      if step.action == 'add' and step.entity_type == NODE]
    added_nodes_names = [step.entity_name for step in add_node_steps]
    return added_nodes_names


def _create_added_nodes_graph(nodes, supported_steps):
    """ create a graph representing the added nodes and relationships
    involving them in the deployment update blueprint

    :rtype: nx.Digraph
    """
    added_nodes_names = _extract_added_nodes_names(supported_steps)
    added_nodes_graph = nx.DiGraph()
    added_nodes_graph.add_nodes_from(added_nodes_names)
    for node_name, node in nodes.items():
        if node_name in added_nodes_names:
            for relationship in node[RELATIONSHIPS]:
                if relationship[TARGET_ID] in added_nodes_names:
                    added_nodes_graph.add_edge(node_name,
                                               relationship[TARGET_ID])
    return added_nodes_graph


def _update_topology_order_of_add_node_steps(supported_steps,
                                             topologically_sorted_added_nodes):
    for i, node_name in enumerate(topologically_sorted_added_nodes):
        # Get the corresponding 'add node' step for this node name,
        # and assign it its topology_order order
        for step in supported_steps:
            if step.action == 'add' and step.entity_type == NODE \
                    and step.entity_name == node_name:
                step.topology_order = i


def _sort_supported_steps(nodes, supported_steps):
    added_nodes_graph = _create_added_nodes_graph(nodes, supported_steps)
    topologically_sorted_added_nodes = nx.topological_sort(
        added_nodes_graph)
    _update_topology_order_of_add_node_steps(
        supported_steps, topologically_sorted_added_nodes)
    supported_steps.sort()


def extract_steps(nodes, deployment, new_plan):
    """Create DeploymentUpdateSteps

    :param nodes: currently existing nodes, as a list of dicts
    :param deployment: the deployment to be updated, as an orm object
    :param new_plan: the new deployment plan, as returned by the dsl-parser
    :return: a pair of lists: the supported steps, and the unsupported steps
    """
    nodes = {node['id']: node for node in nodes}
    new_nodes = {node['id']: node for node in new_plan[NODES]}
    supported_steps = []
    unsupported_steps = []
    for step in _create_steps(nodes, deployment, new_plan):
        if step.supported:
            supported_steps.append(step)
        else:
            unsupported_steps.append(step)
    _sort_supported_steps(new_nodes, supported_steps)
    return supported_steps, unsupported_steps
