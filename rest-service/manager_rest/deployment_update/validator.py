import utils
from manager_rest import storage_manager
import manager_rest.manager_exceptions
from constants import (ENTITY_TYPES,
                       OPERATION_TYPE)
from entity_context import get_entity_keys


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
            ENTITY_TYPES.PROPERTY: self._validate_property,
            ENTITY_TYPES.OPERATION: self._validate_operation
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
        entity_keys = get_entity_keys(step.entity_id)
        if len(entity_keys) < 4:
            return False
        NODES, source_node_id, RELATIONSHIPS, relationship_index = entity_keys
        relationship_index = int(relationship_index[1:-1])

        current_nodes = self.sm.get_nodes().items
        source_node = [n for n in current_nodes if n.id == source_node_id][0]

        if step.operation == OPERATION_TYPE.REMOVE:
            old_relationship = source_node.relationships[relationship_index]
            target_node_id = old_relationship['target_id']
            conditions = \
                [n.id for n in current_nodes if n.id == target_node_id]
        else:
            modified_nodes = dep_update.blueprint['nodes']
            source_node = \
                utils.get_raw_node(dep_update.blueprint, source_node_id)
            new_relationship = source_node[RELATIONSHIPS][relationship_index]
            target_node_id = new_relationship['target_id']
            conditions = \
                [n['id'] for n in modified_nodes if n['id'] == target_node_id]

            conditions += filter(lambda r: r['target_id'] == target_node_id,
                                 source_node[RELATIONSHIPS])

        return any(conditions)

    def _validate_node(self, dep_update, step):
        """ validates node type entity id

        :param dep_update:
        :param step: deployment update step
        :return:
        """
        NODES, node_id = utils.get_entity_keys(step.entity_id)
        if step.operation == OPERATION_TYPE.REMOVE:
            current_node_instances = self.sm.get_node_instances(
                    filters={'deployment_id': dep_update.deployment_id}
            )
            return node_id in [i.node_id for i in current_node_instances.items]
        else:
            new_nodes = \
                dep_update.blueprint[NODES]
            return node_id in utils.extract_ids(new_nodes)

    def _validate_property(self, dep_update, step):
        property_keys = utils.get_entity_keys(step.entity_id)

        NODES, node_id, PROPERTIES = property_keys[:3]
        property_id = property_keys[3:]

        base_node = self.sm.get_node(dep_update.deployment_id, node_id)
        is_in_old = utils.traverse_object(base_node.properties,
                                          property_id)

        modified_node = utils.get_raw_node(dep_update.blueprint, node_id)
        is_in_new = utils.traverse_object(modified_node[PROPERTIES],
                                          property_id)

        if step.operation == OPERATION_TYPE.REMOVE:
            return is_in_old
        elif step.operation == OPERATION_TYPE.ADD:
            return is_in_new
        else:
            return is_in_old and is_in_new

    def _validate_operation(self, dep_update, step):
        operation_keys = utils.get_entity_keys(step.entity_id)
        NODES, node_id, operation_host = operation_keys[:3]
        operation_id = operation_keys[3:]

        base_node = self.sm.get_node(dep_update.deployment_id, node_id)
        is_in_old = utils.traverse_object(getattr(base_node, operation_host),
                                          operation_id)

        modified_node = utils.get_raw_node(dep_update.blueprint, node_id)
        is_in_new = utils.traverse_object(modified_node[operation_host],
                                          operation_id)

        if step.operation == OPERATION_TYPE.REMOVE:
            return is_in_old
        elif step.operation == OPERATION_TYPE.ADD:
            return is_in_new
        else:
            return is_in_old and is_in_new
