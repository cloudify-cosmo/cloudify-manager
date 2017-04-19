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
from contextlib import contextmanager

import networkx as nx

import manager_rest.resource_manager
from manager_rest.storage import get_storage_manager, models


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
CENTRAL_DEPLOYMENT_AGENT_PLUGINS = 'central_deployment_agent_plugins'
HOST_AGENT_PLUGINS = 'host_agent_plugins'
PLUGIN = 'plugin'
PLUGINS_TO_INSTALL = 'plugins_to_install'
DESCRIPTION = 'description'
CONTAINED_IN_RELATIONSHIP_TYPE = 'cloudify.relationships.contained_in'
TYPE_HIERARCHY = 'type_hierarchy'
# flake8: noqa


class EntityIdBuilder(list):

    _separator = ':'

    @property
    def entity_id(self):
        return str(self)

    @contextmanager
    def extend_id(self, key):
        self.append(key)
        yield
        self.remove_last()

    @contextmanager
    def prepend_id_last_element(self, key):
        last_elem = self[-1]
        self.remove_last()
        self.append(key)
        self.append(last_elem)
        yield
        self.remove_last()
        self.remove_last()
        self.append(last_elem)

    def remove_last(self):
        del self[-1]

    def __str__(self):
        return self._separator.join(self)


class DeploymentPlan(dict):

    def __init__(self,
                 deployment,
                 nodes,
                 deployment_plugins_to_install,
                 workflow_plugins_to_install):
        """ Instantiate a deployment plan object

        This constructor gets a deployment and nodes in a format as if these
        were loaded from storage. Then the non deployment-update-relevant
        fields are filtered from the deployment, and the nodes are transformed
        from a list to a dict, were the keys are the ids of each node.
        """
        super(DeploymentPlan, self).__init__()

        filtered_deployment = {k: v
                               for k, v in deployment.iteritems()
                               if k in RELEVANT_DEPLOYMENT_FIELDS}
        self.update(filtered_deployment)

        # update the plan with deployment_plugins_to_install and with
        # workflow_plugins_to_install
        deployment_plugins_to_install_by_name = \
            self._transform_plugins(deployment_plugins_to_install)
        self.update({
            'deployment_plugins_to_install':
                deployment_plugins_to_install_by_name})
        workflow_plugins_to_install_by_name = \
            self._transform_plugins(workflow_plugins_to_install)
        self.update({
            'workflow_plugins_to_install':
                workflow_plugins_to_install_by_name})

        self['nodes'] = nodes

    @classmethod
    def from_storage(cls, deployment_id):
        """ Create a DeploymentPlan from a stored deployment"""
        sm = get_storage_manager()
        # get deployment from storage
        deployment = sm.get(models.Deployment, deployment_id)
        blueprint_plan = deployment.blueprint.plan

        deployment_plugins_to_install = \
            blueprint_plan['deployment_plugins_to_install']
        workflow_plugins_to_install = \
            blueprint_plan['workflow_plugins_to_install']

        # get the nodes from the storage
        nodes = sm.list(
            models.Node,
            filters={'deployment_id': [deployment_id]}
        )
        nodes = {node.id: node.to_dict() for node in nodes}
        return cls(deployment.to_dict(), nodes, deployment_plugins_to_install,
                   workflow_plugins_to_install)

    @classmethod
    def from_deployment_update(cls, deployment_update):
        """ Create a DeploymentPlan from a DeploymentUpdate object

        Using the processed blueprint plan (informally referred to
        as a 'deployment plan' in the resource_manager module), this method
        creates a deployment a nodes in their stored format, to pass to the
        constructor.
        """

        rm = manager_rest.resource_manager.get_resource_manager()

        deployment_plan = deployment_update.deployment_plan
        deployment_id = deployment_update.deployment_id

        blueprint = deployment_update.deployment.blueprint

        new_deployment = rm.prepare_deployment_for_storage(
            deployment_id,
            deployment_plan
        )
        dep_dict = new_deployment.to_dict(suppress_error=True)
        dep_dict['blueprint_id'] = blueprint.id

        deployment_plugins_to_install = \
            deployment_plan['deployment_plugins_to_install']
        workflow_plugins_to_install = \
            deployment_plan['workflow_plugins_to_install']

        nodes = rm.prepare_deployment_nodes_for_storage(deployment_plan)
        nodes_dict = dict()

        for node in nodes:
            node_dict = node.to_dict(suppress_error=True)
            node_dict['deployment_id'] = deployment_id
            nodes_dict[node.id] = node_dict
        return cls(dep_dict, nodes_dict, deployment_plugins_to_install,
                   workflow_plugins_to_install)

    @staticmethod
    def _transform_plugins(plugins):
        plugins_by_name = {plugin['name']: plugin for plugin in plugins}
        return plugins_by_name


class DeploymentUpdateStep(object):

    def __init__(self, action, entity_type, entity_id,
                 supported=True, topology_order=DEFAULT_TOPOLOGY_LEVEL):

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

    def __cmp__(self, other):

        if self.action != other.action:
            # the order is 'remove' < 'add' < 'modify'
            if self.action == 'remove' and other.action != 'remove':
                return -1
            elif self.action == 'add':
                return -1 if other.action == 'modify' else 1
            else:
                return 1
        else:
            if self.action == 'add':
                if self.entity_type == NODE:
                    if other.entity_type == RELATIONSHIP:
                        # add node before adding relationships
                        return -1
                    if other.entity_type == NODE:
                        # higher topology order before lower topology order
                        if self.topology_order > other.topology_order:
                            return -1
                        else:
                            return 1

            elif self.action == 'remove':
                if (self.entity_type == RELATIONSHIP and
                        other.entity_type == NODE):
                    # remove relationships before removing nodes
                    return -1
        # other comparisons don't matter
        return 0


class StepExtractor(object):

    entity_id_segment_to_entity_type = {
        PROPERTIES: PROPERTY,
        OUTPUTS: OUTPUT,
        WORKFLOWS: WORKFLOW,
        GROUPS: GROUP,
        POLICY_TYPES: POLICY_TYPE,
        POLICY_TRIGGERS: POLICY_TRIGGER
    }

    def __init__(self, deployment_update):
        self.deployment_id = deployment_update.deployment_id
        self.deployment_update_id = deployment_update.id
        self.deployment_update_manager = \
            manager_rest.deployment_update.manager.\
            get_deployment_updates_manager()
        self.sm = self.deployment_update_manager.sm
        self.entity_id_builder = EntityIdBuilder()
        self.old_deployment_plan = None
        self.new_deployment_plan = None
        self.steps = []

        # The following property determines the type of steps that will be
        # created as part of a call to self._extract_steps.

        # If it is False, the diff process (which is composed of two calls to
        # self.extract_steps) will detect entities that were not in
        # `old_deployment_plan` but exist in `new_deployment_plan`.
        # That is, the diff will detect all the entities that were added as
        # part of the deployment update process.
        # Furthermore, if the diff perspective is not inversed, the diff will
        # also detect all the entities that were modified. That is, entities
        # that exist both in `old_deployment_plan` and in
        # `new_deployment_plan`, but that their values are different.

        # If _inverted_diff_perspective is True, the diff process will detect
        # all entities that were in `old_deployment_plan`, but aren't a part
        # of `new_deployment_plan`. That is, the diff will detect all the
        # entities that were removed as part of the deployment update process.
        self._inverted_diff_perspective = False

    def extract_steps(self):
        old = self.old_deployment_plan
        new = self.new_deployment_plan

        self._extract_steps_from_description(old[DESCRIPTION],
                                             new[DESCRIPTION])

        self._extract_host_agent_plugins_steps(old[NODES], new[NODES])

        self._extract_central_deployment_agent_plugins_steps(
            old[DEPLOYMENT_PLUGINS_TO_INSTALL],
            new[DEPLOYMENT_PLUGINS_TO_INSTALL])

        self._extract_steps(new, old)
        self._inverted_diff_perspective = True
        self._extract_steps(old, new)

        supported_steps = [step for step in self.steps if step.supported]
        self._sort_supported_steps(supported_steps)

        unsupported_steps = [step for step in self.steps if not step.supported]

        return supported_steps, unsupported_steps

    @staticmethod
    def _extract_added_nodes_names(supported_steps):

        add_node_steps = [step for step in supported_steps
                          if step.action == 'add' and step.entity_type == NODE]
        added_nodes_names = [step.entity_name for step in add_node_steps]
        return added_nodes_names

    def _create_added_nodes_graph(self, supported_steps):
        """ create a graph representing the added nodes and relationships
        involving them in the deployment update blueprint

        :rtype: nx.Digraph
        """
        added_nodes_names = self._extract_added_nodes_names(supported_steps)

        added_nodes_graph = nx.DiGraph()
        added_nodes_graph.add_nodes_from(added_nodes_names)

        nodes = self.new_deployment_plan[NODES]
        for node_name, node in nodes.iteritems():
            if node_name in added_nodes_names:
                for relationship in node[RELATIONSHIPS]:
                    if relationship[TARGET_ID] in added_nodes_names:
                        added_nodes_graph.add_edge(node_name,
                                                   relationship[TARGET_ID])
        return added_nodes_graph

    def _update_topology_order_of_add_node_steps(
            self,
            supported_steps,
            topologically_sorted_added_nodes):

        for i, node_name in enumerate(topologically_sorted_added_nodes):
            # Get the corresponding 'add node' step for this node name,
            # and assign it its topology_order order
            for step in supported_steps:
                if step.action == 'add' and step.entity_type == NODE \
                        and step.entity_name == node_name:
                    step.topology_order = i

    def _sort_supported_steps(self, supported_steps):

        added_nodes_graph = self._create_added_nodes_graph(supported_steps)

        topologically_sorted_added_nodes = \
            nx.topological_sort(added_nodes_graph)

        self._update_topology_order_of_add_node_steps(
            supported_steps, topologically_sorted_added_nodes)

        supported_steps.sort()

    def _extract_steps_from_description(self,
                                        old_description,
                                        new_description):
        with self.entity_id_builder.extend_id(DESCRIPTION):
            if old_description is None:
                if new_description is not None:
                    self._create_step(DESCRIPTION)
            else:
                if new_description is None:
                    self._inverted_diff_perspective = True
                    self._create_step(DESCRIPTION)
                    self._inverted_diff_perspective = False
                else:
                    if old_description != new_description:
                        self._create_step(DESCRIPTION, modify=True)

    def _extract_host_agent_plugins_steps(self, old_nodes, new_nodes):
        with self.entity_id_builder.extend_id(HOST_AGENT_PLUGINS):
            for new_node_name in new_nodes:
                new_node = new_nodes[new_node_name]
                new_plugins_to_install = new_node[PLUGINS_TO_INSTALL]
                if new_plugins_to_install:
                    if new_node_name in old_nodes:
                        with self.entity_id_builder.extend_id(new_node_name):
                            old_node = old_nodes[new_node_name]
                            if old_node != new_node:
                                old_plugins_to_install = old_node[
                                    PLUGINS_TO_INSTALL]
                                for new_plugin_to_install in \
                                        new_plugins_to_install:
                                    if new_plugin_to_install['install']:
                                        new_plug_name = new_plugin_to_install['name']
                                        old_plugins_to_install = next((p for p in old_plugins_to_install if p['name'] == new_plug_name), None)
                                        if not old_plugins_to_install:
                                            self._create_step(PLUGIN,
                                                              supported=False)
                                        else:
                                            if new_plugin_to_install != old_plugins_to_install:
                                                self._create_step(
                                                    PLUGIN,
                                                    supported=False,
                                                    modify=True)

    def _extract_central_deployment_agent_plugins_steps(
            self,
            old_deployment_plugins_to_install,
            new_deployment_plugins_to_install):
        with self.entity_id_builder.extend_id(
                CENTRAL_DEPLOYMENT_AGENT_PLUGINS):
            for new_cda_plugin in new_deployment_plugins_to_install:
                if new_deployment_plugins_to_install[new_cda_plugin] \
                        ['install']:
                    with self.entity_id_builder.extend_id(new_cda_plugin):
                        if new_cda_plugin not in \
                                old_deployment_plugins_to_install:
                            self._create_step(PLUGIN,
                                              supported=False)
                        else:
                            if new_deployment_plugins_to_install[
                                new_cda_plugin] != \
                                    old_deployment_plugins_to_install[
                                        new_cda_plugin]:
                                self._create_step(PLUGIN,
                                                  supported=False,
                                                  modify=True)

    @staticmethod
    def _get_matching_relationship(relationship, relationships):

        r_type = relationship[TYPE]
        target_id = relationship[TARGET_ID]

        for rel_index, other_relationship in enumerate(relationships):
            other_r_type = other_relationship[TYPE]
            other_target_id = other_relationship[TARGET_ID]

            if r_type == other_r_type and other_target_id == target_id:
                return other_relationship, rel_index
        return None, None

    def _extract_steps_from_relationships(self,
                                          relationships,
                                          old_relationships):
        with self.entity_id_builder.extend_id(RELATIONSHIPS):

            for relationship_index, relationship in enumerate(relationships):

                with self.entity_id_builder.extend_id(
                        '[{0}]'.format(relationship_index)):

                    matching_relationship, old_rel_index = \
                        self._get_matching_relationship(
                            relationship, old_relationships)

                    if matching_relationship:
                        # relationship has been reordered to a different index
                        if old_rel_index != relationship_index:
                            with self.entity_id_builder.\
                                    prepend_id_last_element(
                                    '[{0}]'.format(old_rel_index)):
                                self._create_step(RELATIONSHIP,
                                                  modify=True)

                        for field_name in relationship:
                            if field_name in [SOURCE_OPERATIONS,
                                              TARGET_OPERATIONS]:
                                self._extract_steps_from_operations(
                                    operations_type_name=field_name,
                                    operations=relationship[field_name],
                                    old_operations=matching_relationship[
                                        field_name])

                            elif field_name == PROPERTIES:
                                # modifying relationship properties is not
                                # supported yet
                                self._extract_steps_from_entities(
                                    entities_name=PROPERTIES,
                                    new_entities=relationship[PROPERTIES],
                                    old_entities=matching_relationship[
                                        PROPERTIES],
                                    supported=False)
                    else:
                        self._create_step(RELATIONSHIP)

    def _extract_steps_from_operations(self,
                                       operations_type_name,
                                       operations,
                                       old_operations):

        with self.entity_id_builder.extend_id(operations_type_name):
            for operation_name in operations:
                with self.entity_id_builder.extend_id(operation_name):
                    if operation_name in old_operations:
                        old_operation = old_operations[operation_name]
                        if old_operation != operations[operation_name]:
                            self._create_step(
                                OPERATION, modify=True)
                    else:
                        self._create_step(OPERATION)

    def _extract_step_from_workflows(self,
                                     new_workflows,
                                     old_workflows,
                                     old_workflow_plugins_to_install,
                                     new_workflow_plugins_to_install):

        with self.entity_id_builder.extend_id(WORKFLOWS):

            for workflow_name in new_workflows:
                with self.entity_id_builder.extend_id(workflow_name):
                    new_workflow = new_workflows[workflow_name]
                    if workflow_name in old_workflows:
                        old_workflow = old_workflows[workflow_name]
                        if old_workflow != new_workflow:
                            if new_workflow['plugin'] not in \
                                    old_workflow_plugins_to_install:
                                # the plugin of the workflow was modified
                                if new_workflow_plugins_to_install[new_workflow['plugin']]['install']:
                                    self._create_step(WORKFLOW,
                                                      supported=False,
                                                      modify=True)
                            else:
                                self._create_step(WORKFLOW,
                                                  modify=True)
                    else:
                        if new_workflow['plugin'] not in \
                            old_workflow_plugins_to_install and \
                            new_workflow_plugins_to_install[
                                new_workflow['plugin']]['install']:
                            if not self._inverted_diff_perspective:
                                # the added workflow's plugin does not exist
                                # in the old workflows_plugins_to_install
                                self._create_step(WORKFLOW,
                                                  supported=False)
                            else:
                                # if we are in an inversed perspective, then
                                # remove the workflow as usual
                                self._create_step(WORKFLOW)
                        else:
                            self._create_step(WORKFLOW)

    def _extract_steps_from_nodes(self,
                                  new_nodes,
                                  old_nodes):
        with self.entity_id_builder.extend_id(NODES):
            for node_name, node in new_nodes.iteritems():
                with self.entity_id_builder.extend_id(node_name):
                    if node_name in old_nodes:
                        old_node = old_nodes[node_name]

                        if node[TYPE] != old_node[TYPE] or \
                            _is_contained_in_changed(node, old_node):
                            # a node that changed its type or its host_id
                            # counts as a different node
                            self._create_step(NODE,
                                              supported=False,
                                              modify=True)
                            # Since the node was classified as added or
                            # removed, there is no need to compare its other
                            # fields.
                            continue

                        self._extract_steps_from_operations(
                            operations_type_name=OPERATIONS,
                            operations=node[OPERATIONS],
                            old_operations=old_node[OPERATIONS])

                        self._extract_steps_from_relationships(
                            relationships=node[RELATIONSHIPS],
                            old_relationships=old_node[RELATIONSHIPS])

                        self._extract_steps_from_entities(
                            PROPERTIES,
                            new_entities=node[PROPERTIES],
                            old_entities=old_node[PROPERTIES])

                    else:
                        # add (remove) node step
                        self._create_step(NODE)

    def _extract_steps_from_entities(self,
                                     entities_name,
                                     new_entities,
                                     old_entities,
                                     supported=True):

        with self.entity_id_builder.extend_id(entities_name):

            for entity_name in new_entities:
                with self.entity_id_builder.extend_id(entity_name):
                    if entity_name in old_entities:
                        if old_entities[entity_name] != \
                                new_entities[entity_name]:
                            self._create_step(
                                self.entity_id_segment_to_entity_type[
                                    entities_name],
                                supported,
                                modify=True)
                    else:
                        self._create_step(
                            self.entity_id_segment_to_entity_type[
                                entities_name],
                            supported)

    def _extract_steps(self, new, old):

        for entities_name, new_entities in new.iteritems():
            old_entities = old.get(entities_name, {})

            if entities_name == NODES:
                self._extract_steps_from_nodes(new_entities, old_entities)

            elif entities_name == OUTPUTS:
                self._extract_steps_from_entities(
                    OUTPUTS, new_entities, old_entities)

            elif entities_name == WORKFLOWS:
                self._extract_step_from_workflows(
                    new_workflows=new_entities,
                    old_workflows=old_entities,
                    old_workflow_plugins_to_install=self.old_deployment_plan[
                        'workflow_plugins_to_install'],
                    new_workflow_plugins_to_install=self.new_deployment_plan[
                        'workflow_plugins_to_install'])

            elif entities_name == POLICY_TYPES:
                self._extract_steps_from_entities(
                    POLICY_TYPES, new_entities, old_entities,
                    supported=False)

            elif entities_name == POLICY_TRIGGERS:
                self._extract_steps_from_entities(
                    POLICY_TRIGGERS, new_entities, old_entities,
                    supported=False)

            elif entities_name == GROUPS:
                self._extract_steps_from_entities(
                    GROUPS, new_entities, old_entities,
                    supported=False)

    def _determine_step_action(self, modify):
        """ Determine if the step will be of type 'add', 'remove', 'modify' or
        no type at all

        Notice that you can identify an entity modification ('modify' action)
        whether you compare the old plan to the new plan, or whether you
        compare new plan to the old plan, but you only need to create one
        'modify' step representing this modification.
        We chose, arbitrarily, to create the 'modify' step when we compare the
        new to the old (_inverted_diff_perspective == False).
        """
        if modify and not self._inverted_diff_perspective:
            return 'modify'
        elif modify:
            return None
        elif self._inverted_diff_perspective:
            return 'remove'
        else:
            return 'add'

    def _create_step(self, entity_type, supported=True, modify=False):

        action = self._determine_step_action(modify)
        entity_id = self.entity_id_builder.entity_id

        if action:
            step = DeploymentUpdateStep(action,
                                        entity_type,
                                        entity_id,
                                        supported)
            self.steps.append(step)


def extract_steps(deployment_update):
    steps_extractor = \
        StepExtractor(deployment_update)

    # update the steps extractor with the old and the new deployment plans
    steps_extractor.old_deployment_plan = \
        DeploymentPlan.from_storage(steps_extractor.deployment_id)
    steps_extractor.new_deployment_plan = \
        DeploymentPlan.from_deployment_update(deployment_update)

    # create the steps
    supported_steps, unsupported_steps = steps_extractor.extract_steps()

    return supported_steps, unsupported_steps


def _is_contained_in_changed(node, other_node):
    node_container = \
        next((r['target_id'] for r in node['relationships']
              if CONTAINED_IN_RELATIONSHIP_TYPE in r[TYPE_HIERARCHY]), None)
    other_node_container = \
        next((r['target_id'] for r in other_node['relationships']
              if CONTAINED_IN_RELATIONSHIP_TYPE in r[TYPE_HIERARCHY]), None)

    return node_container != other_node_container
