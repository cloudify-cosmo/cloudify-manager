from utils import (pluralize,
                   extract_ids,
                   get_relationship_source_and_target,
                   get_entity_id_list)
from manager_rest import storage_manager
import manager_rest.manager_exceptions
from constants import (OPERATIONS,
                       ENTITY_TYPES,
                       RELATIONSHIP_SEPARATOR)


class StepValidator(object):

    def __init__(self):
        self.sm = storage_manager.get_storage_manager()

    def validate(self, dep_update, step):
        """
        validate an entity id of provided type exists in provided blueprint.
        raises error if id doesn't exist
        :param dep_update: the deployment update object.
        :param step: the deployment update step object
        :return: None
        """

        validation_mapper = {
            ENTITY_TYPES.NODE: self._validate_node,
            ENTITY_TYPES.RELATIONSHIP: self._validate_relationship,
            ENTITY_TYPES.PROPERTY: self._validate_property
        }
        if step.entity_type in ENTITY_TYPES:
            validator = validation_mapper[step.entity_type]
            if validator(dep_update, step):
                return

        raise \
            manager_rest.manager_exceptions.UnknownModificationStageError(
                    "entity type {0} with entity id {1} doesn't exist"
                        .format(step.entity_type, step.entity_id))

    def _validate_relationship(self, dep_update, step):
        """ validates relation type entity id

        :param dep_update:
        :param step: deployment update step
        :return:
        """
        if RELATIONSHIP_SEPARATOR not in step.entity_id:
            return False

        source_entity_id, target_entity_id = \
            get_relationship_source_and_target(step.entity_id)
        _, source_node_id = get_entity_id_list(source_entity_id)
        _, target_node_id = get_entity_id_list(target_entity_id)

        if step.operation == OPERATIONS.REMOVE:
            current_nodes = self.sm.get_nodes().items
            source_node = \
                [n for n in current_nodes if n.id == source_node_id][0]

            conditions = \
                [n.id for n in current_nodes if n.id == target_node_id]
            conditions += filter(lambda r: r['target_id'] == target_node_id,
                                 source_node.relationships)
        else:
            new_nodes = dep_update.blueprint['nodes']

            source_node = \
                [n for n in new_nodes if n['id'] == source_node_id][0]

            conditions = \
                [n['id'] for n in new_nodes if n['id'] == target_node_id]
            conditions += filter(lambda r: r['target_id'] == target_node_id,
                                 source_node['relationships'])

        return any(conditions)

    def _validate_node(self, dep_update, step):
        """ validates node type entity id

        :param dep_update:
        :param step: deployment update step
        :return:
        """
        _, node_id = get_entity_id_list(step.entity_id)
        if step.operation == OPERATIONS.REMOVE:
            current_node_instances = self.sm.get_node_instances(
                    filters={'deployment_id': dep_update.deployment_id}
            )
            return node_id in [i.node_id for i in current_node_instances.items]
        else:
            new_nodes = \
                dep_update.blueprint[pluralize(ENTITY_TYPES.NODE)]
            return node_id in extract_ids(new_nodes)

    def _validate_property(self, dep_update, step):
        _, node_id, _, property_id = get_entity_id_list(step.entity_id)

        is_property_in_old_node = \
            property_id in \
            self.sm.get_node(dep_update.deployment_id, node_id).properties

        modified_node = \
            [n for n in dep_update.blueprint[pluralize(ENTITY_TYPES.NODE)]][0]
        is_property_in_modified_node = \
            property_id in modified_node[pluralize(ENTITY_TYPES.PROPERTY)]

        if step.operation == OPERATIONS.REMOVE:
            return is_property_in_old_node
        elif step.operation == OPERATIONS.ADD:
            return is_property_in_modified_node
        else:
            return is_property_in_old_node and is_property_in_modified_node
