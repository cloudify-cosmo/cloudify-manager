import utils
from manager_rest import storage_manager
import manager_rest.manager_exceptions
from constants import (ENTITY_TYPES,
                       ACTION_TYPES)


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
            ENTITY_TYPES.OPERATION: self._validate_operation,
            ENTITY_TYPES.WORKFLOW: self._validate_workflow,
            ENTITY_TYPES.OUTPUT: self._validate_output
        }
        if step.entity_type in ENTITY_TYPES:
            validate = validation_mapper[step.entity_type]
            if validate(dep_update=dep_update, step=step):
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
        entity_keys = utils.get_entity_keys(step.entity_id)
        if len(entity_keys) < 4:
            return
        NODES, source_node_id, RELATIONSHIPS, relationship_index = entity_keys

        # assert the index is indeed readable
        relationship_index = utils.parse_index(relationship_index)
        if not relationship_index:
            return

        storage_source_node = \
            self._get_storage_node(dep_update.deployment_id, source_node_id)

        raw_source_node = \
            utils.get_raw_node(dep_update.blueprint, source_node_id)

        source_node = (storage_source_node
                       if step.operation == ACTION_TYPES.REMOVE else
                       raw_source_node)
        if (not source_node or
           len(source_node[RELATIONSHIPS]) <= relationship_index):
            return

        target_node_id = \
            source_node[RELATIONSHIPS][relationship_index]['target_id']

        in_old = self._get_storage_node(dep_update.deployment_id,
                                        target_node_id)
        in_new = utils.get_raw_node(dep_update.blueprint, target_node_id)

        return {
            ACTION_TYPES.ADD: bool(in_new),
            ACTION_TYPES.REMOVE: bool(in_old),
            ACTION_TYPES.MODIFY: bool(in_new) and bool(in_old)
        }[step.operation]

    def _validate_node(self, dep_update, step):
        """ validates node type entity id

        :param dep_update:
        :param step: deployment update step
        :return:
        """
        NODES, node_id = utils.get_entity_keys(step.entity_id)

        in_old = self._get_storage_node(dep_update.deployment_id, node_id)
        in_new = utils.get_raw_node(dep_update.blueprint, node_id)
        return {
            ACTION_TYPES.ADD: bool(in_new) and not bool(in_old),
            ACTION_TYPES.REMOVE: bool(in_old) and not bool(in_new),
            ACTION_TYPES.MODIFY: bool(in_new) and bool(in_old)
        }[step.operation]

    def _validate_property(self, dep_update, step):
        property_keys = utils.get_entity_keys(step.entity_id)

        if len(property_keys) < 2:
            return
        NODES, node_id = property_keys[:2]
        property_id = property_keys[2:]

        storage_node = \
            self._get_storage_node(dep_update.deployment_id, node_id)
        raw_node = utils.get_raw_node(dep_update.blueprint, node_id)

        in_old = utils.traverse_object(storage_node, property_id)
        in_new = utils.traverse_object(raw_node, property_id)

        return {
            ACTION_TYPES.ADD: bool(in_new) and not bool(in_old),
            ACTION_TYPES.REMOVE: bool(in_old) and not bool(in_new),
            ACTION_TYPES.MODIFY: bool(in_new) and bool(in_old)
        }[step.operation]

    def _validate_operation(self, dep_update, step):
        operation_keys = utils.get_entity_keys(step.entity_id)
        if len(operation_keys) < 2:
            return

        NODES, node_id = operation_keys[:2]
        operation_id = operation_keys[2:]

        storage_node = \
            self._get_storage_node(dep_update.deployment_id, node_id)
        in_old = utils.traverse_object(storage_node, operation_id)

        raw_node = utils.get_raw_node(dep_update.blueprint, node_id)
        in_new = utils.traverse_object(raw_node, operation_id)

        return {
            ACTION_TYPES.ADD: bool(in_new),
            ACTION_TYPES.REMOVE: bool(in_old),
            ACTION_TYPES.MODIFY: bool(in_new) and bool(in_old)
        }[step.operation]

    def _validate_workflow(self, dep_update, step):
        workflow_keys = utils.get_entity_keys(step.entity_id)

        if len(workflow_keys) < 2:
            return

        WORKFLOWS = workflow_keys[0]
        entity_id = workflow_keys[1:]

        storage_workflows = getattr(
                self.sm.get_deployment(dep_update.deployment_id),
                WORKFLOWS,
                {}
        )
        raw_workflows = dep_update.blueprint[WORKFLOWS]

        in_old = utils.traverse_object(storage_workflows, entity_id)
        in_new = utils.traverse_object(raw_workflows, entity_id)

        return {
            ACTION_TYPES.ADD: bool(in_new) and not bool(in_old),
            ACTION_TYPES.REMOVE: bool(in_old) and not bool(in_new),
            ACTION_TYPES.MODIFY: bool(in_new) and bool(in_old)
        }[step.operation]

    def _validate_output(self, dep_update, step):
        output_keys = utils.get_entity_keys(step.entity_id)

        if len(output_keys) < 2:
            return

        OUTPUTS = output_keys[0]
        entity_id = output_keys[1:]

        storage_outputs = getattr(
                self.sm.get_deployment(dep_update.deployment_id),
                OUTPUTS,
                {})
        raw_outputs = dep_update.blueprint[OUTPUTS]

        in_old = utils.traverse_object(storage_outputs, entity_id)
        in_new = utils.traverse_object(raw_outputs, entity_id)

        return {
            ACTION_TYPES.ADD: bool(in_new) and not bool(in_old),
            ACTION_TYPES.REMOVE: bool(in_old) and not bool(in_new),
            ACTION_TYPES.MODIFY: bool(in_new) and bool(in_old)
        }[step.operation]

    def _get_storage_node(self, deployment_id, node_id):
        nodes = self.sm.get_nodes(filters={'id': node_id})
        return nodes.items[0].to_dict() if nodes.items else {}
