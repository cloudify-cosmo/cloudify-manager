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

from manager_rest.models import DeploymentUpdateStep
import manager_rest.blueprints_manager


RELEVANT_DEPLOYMENT_FIELDS = ['blueprint_id', 'id', 'inputs', 'nodes',
                              'outputs', 'workflows']
NODE = 'node'
NODES = 'nodes'
OUTPUT = 'output'
OUTPUTS = 'outputs'
TYPE = 'type'
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
INTERFACES = 'interfaces'


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

    def remove_last(self):
        del self[-1]

    def __str__(self):
        return self._separator.join(self)


class DeploymentPlan(dict):

    def __init__(self, deployment, nodes):
        """ Instantiate a deployment plan object

        This constructor gets a deployment and nodes in a format as if these
        were loaded from storage. Then the non deployment-update-relevant
        fields are filtered from the deployment, and the nodes are transformed
        from a list to a dict, were the keys are the ids of each node.
        """
        super(DeploymentPlan, self).__init__()

        filtered_deployment = {k: v
                               for k, v in deployment.to_dict().iteritems()
                               if k in RELEVANT_DEPLOYMENT_FIELDS}
        self.update(filtered_deployment)
        nodes = self._transform_nodes(nodes)
        self['nodes'] = nodes

    @classmethod
    def from_storage(cls, deployment_id):
        """ Create a DeploymentPlan from a stored deployment"""
        sm = manager_rest.storage_manager.get_storage_manager()
        deployment = sm.get_deployment(deployment_id)
        nodes = sm.get_nodes(
            filters={'deployment_id': [deployment_id]}).items

        return cls(deployment, nodes)

    @classmethod
    def from_deployment_update(cls, deployment_update):
        """ Create a DeploymentPlan from a DeploymentUpdate object

        Using the processed blueprint plan (informally referred to
        as a 'deployment plan' in the blueprints_manager module), this method
        creates a deployment a nodes in their stored format, to pass to the
        constructor.
        """

        blueprints_manager = \
            manager_rest.blueprints_manager.get_blueprints_manager()

        deployment_plan = deployment_update.blueprint
        deployment_id = deployment_update.deployment_id

        sm = blueprints_manager.sm
        blueprint_id = sm.get_deployment(deployment_id).blueprint_id

        deployment = blueprints_manager.prepare_deployment_for_storage(
            blueprint_id,
            deployment_id,
            deployment_plan)

        nodes = blueprints_manager.prepare_deployment_nodes_for_storage(
            blueprint_id,
            deployment_id,
            deployment_plan
        )
        return cls(deployment, nodes)

    @staticmethod
    def _transform_nodes(nodes):
        """ Transform nodes from a list of dicts to a dict

        The dictionary keys are the node ids
        [{node_id: id1, value: v1}, {node_id: id2, value: v2}]
                                   |
                                   v
                 {id1: {value: v1}, id2: {value: v2}}
        """
        nodes_by_id = {node.id: node.to_dict() for node in nodes}
        return nodes_by_id


class DeploymentUpdateStepsExtractor(object):

    entity_id_segment_to_entity_type = {
        PROPERTIES: PROPERTY,
        OUTPUTS: OUTPUT,
        WORKFLOWS: WORKFLOW
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

        self._extract_steps(new, old)
        self._inverted_diff_perspective = True
        self._extract_steps(old, new)

        return self.steps

    def _get_matching_relationship(self, relationship, relationships):

        r_type = relationship[TYPE]
        target_id = relationship[TARGET_ID]

        for other_relationship in relationships:
            other_r_type = other_relationship[TYPE]
            other_target_id = other_relationship[TARGET_ID]

            if r_type == other_r_type and other_target_id == target_id:
                return other_relationship
        return None

    def _extract_steps_from_relationships(self,
                                          relationships,
                                          old_relationships):
        with self.entity_id_builder.extend_id(RELATIONSHIPS):

            for relationship_index, relationship in enumerate(relationships):

                with self.entity_id_builder.extend_id(
                        '[{0}]'.format(relationship_index)):

                    matching_relationship = self._get_matching_relationship(
                        relationship, old_relationships)

                    if matching_relationship:
                        for field_name in relationship:
                            if field_name in [SOURCE_OPERATIONS,
                                              TARGET_OPERATIONS]:
                                self._extract_steps_from_operations(
                                    operations_type_name=field_name,
                                    operations=relationship[field_name],
                                    old_operations=matching_relationship[
                                        field_name])

                            elif field_name == PROPERTIES:
                                if (relationship[PROPERTIES] !=
                                        matching_relationship[PROPERTIES]):
                                    # alert the user that changing the
                                    # relationship is currently not supported
                                    # during deployment updates.
                                    pass
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

    def _extract_steps_from_nodes(self,
                                  new_nodes,
                                  old_nodes):
        with self.entity_id_builder.extend_id(NODES):
            for node_name, node in new_nodes.iteritems():
                with self.entity_id_builder.extend_id(node_name):
                    if node_name in old_nodes:
                        old_node = old_nodes[node_name]

                        if node[TYPE] != old_node[TYPE]:
                            # a node that changed its type counts as a
                            # different node
                            self._create_step(NODE)
                            # Since the node changed its type, there is no
                            # need to compare its other fields.
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
                                     old_entities):

        with self.entity_id_builder.extend_id(entities_name):

            for entity_name in new_entities:
                with self.entity_id_builder.extend_id(entity_name):
                    if entity_name in old_entities:
                        if old_entities[entity_name] != \
                                new_entities[entity_name]:
                            self._create_step(
                                self.entity_id_segment_to_entity_type[
                                    entities_name],
                                modify=True)
                    else:
                        self._create_step(
                            self.entity_id_segment_to_entity_type[
                                entities_name])

    def _extract_steps(self, new, old):

        for entities_name, new_entities in new.iteritems():
            old_entities = old.get(entities_name, {})

            if entities_name == NODES:
                self._extract_steps_from_nodes(
                    new_entities, old_entities)

            elif entities_name == OUTPUTS:
                self._extract_steps_from_entities(
                    OUTPUTS, new_entities, old_entities)

            elif entities_name == WORKFLOWS:
                self._extract_steps_from_entities(
                    WORKFLOWS, new_entities, old_entities)

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

    def _create_step(self, entity_type, modify=False):

        action = self._determine_step_action(modify)
        entity_id = self.entity_id_builder.entity_id

        if action:
            step = DeploymentUpdateStep(action,
                                        entity_type,
                                        entity_id,
                                        self.deployment_update_id)
            self.steps.append(step)


def extract_steps(deployment_update):
    steps_extractor = \
        DeploymentUpdateStepsExtractor(deployment_update)

    # update the steps extractor with the old and the new deployment plans
    steps_extractor.old_deployment_plan = \
        DeploymentPlan.from_storage(steps_extractor.deployment_id)
    steps_extractor.new_deployment_plan = \
        DeploymentPlan.from_deployment_update(deployment_update)

    # create the steps
    steps = steps_extractor.extract_steps()

    # sort the steps
    steps.sort()

    return steps
