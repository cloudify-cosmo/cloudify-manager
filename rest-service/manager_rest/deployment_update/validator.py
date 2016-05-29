from manager_rest import storage_manager
from manager_rest.deployment_update import utils
from manager_rest.manager_exceptions import UnknownModificationStageError
from manager_rest.deployment_update.constants import ENTITY_TYPES, ACTION_TYPES


class EntityValidatorBase(object):
    def __init__(self):
        self.sm = storage_manager.get_storage_manager()
        self._validation_mapper = {
            ACTION_TYPES.ADD: self._validate_add,
            ACTION_TYPES.MODIFY: self._validate_modify,
            ACTION_TYPES.REMOVE: self._validate_remove
        }

    def validate(self, dep_update, step):
        try:
            self._validate_entity(dep_update, step)
        except UnknownModificationStageError as e:
            entity_identifier_msg = \
                "Entity type {0} with entity id {1}".format(step.entity_type,
                                                            step.entity_id)
            err_msg = "{0}: {1}".format(entity_identifier_msg, e.message)
            raise UnknownModificationStageError(err_msg)

    def _validate_entity(self, dep_update, step):
        raise NotImplementedError

    def _in_old(self, *args, **kwargs):
        raise NotImplementedError

    def _in_new(self, *args, **kwargs):
        raise NotImplementedError

    def _validate_add(self, entity_id, entity_type,  **kwargs):
        if not (self._in_new(**kwargs) and not self._in_old(**kwargs)):
            raise UnknownModificationStageError(
                "The entity either doesn't exist in the deployment update "
                "blueprint or exists in the original deployment blueprint")

    def _validate_modify(self, entity_id, entity_type, **kwargs):
        if not (self._in_new(**kwargs) and self._in_old(**kwargs)):
            raise UnknownModificationStageError(
                "The entity either doesn't exist in the deployment update "
                "blueprint or it doesn't exists in the original deployment "
                "blueprint")

    def _validate_remove(self, entity_id, entity_type, **kwargs):
        if not (not self._in_new(**kwargs) and self._in_old(**kwargs)):
            raise UnknownModificationStageError(
                "The entity either exists in the deployment update blueprint "
                "or doesn't exists in the original deployment blueprint")

    def _get_storage_node(self, deployment_id, node_id):
        nodes = self.sm.get_nodes(filters={'deployment_id': deployment_id,
                                           'id': node_id})
        return nodes.items[0].to_dict() if nodes.items else {}


class NodeValidator(EntityValidatorBase):

    def _validate_entity(self, dep_update, step):
        entity_keys = utils.get_entity_keys(step.entity_id)
        if len(entity_keys) != 2:
            return
        _, node_id = entity_keys

        validate = self._validation_mapper[step.action]
        return validate(step.entity_id,
                        step.entity_type,
                        dep_update=dep_update,
                        node_id=node_id)

    def _in_old(self, dep_update, node_id):
        storage_node = \
            self._get_storage_node(dep_update.deployment_id, node_id)
        return bool(storage_node)

    def _in_new(self, dep_update, node_id):
        raw_node = utils.get_raw_node(dep_update.blueprint, node_id)
        return bool(raw_node)


class RelationshipValidator(EntityValidatorBase):

    def _validate_entity(self, dep_update, step):
        entity_keys = utils.get_entity_keys(step.entity_id)
        if len(entity_keys) < 4:
            return
        _, source_node_id, relationships, relationship_index = entity_keys

        # assert the index is indeed readable
        relationship_index = utils.parse_index(relationship_index)
        if not relationship_index:
            return

        validate = self._validation_mapper[step.action]
        return validate(step.entity_id,
                        step.entity_type,
                        dep_update=dep_update,
                        source_node_id=source_node_id,
                        relationships=relationships,
                        relationship_index=relationship_index)

    def _in_new(self,
                dep_update,
                source_node_id,
                relationships,
                relationship_index):
        source_node = utils.get_raw_node(dep_update.blueprint,
                                         source_node_id)
        if not (source_node and
                len(source_node[relationships]) > relationship_index):
            return

        target_node_id = \
            source_node[relationships][relationship_index]['target_id']

        raw_target_node = utils.get_raw_node(dep_update.blueprint,
                                             target_node_id)
        return raw_target_node

    def _in_old(self,
                dep_update,
                source_node_id,
                relationships,
                relationship_index):
        source_node = self._get_storage_node(dep_update.deployment_id,
                                             source_node_id)
        if not (source_node and
                len(source_node[relationships]) > relationship_index):
            return

        target_node_id = \
            source_node[relationships][relationship_index]['target_id']
        storage_target_node = self._get_storage_node(dep_update.deployment_id,
                                                     target_node_id)
        return storage_target_node


class PropertyValidator(EntityValidatorBase):

    def _validate_entity(self, dep_update, step):
        property_keys = utils.get_entity_keys(step.entity_id)

        if len(property_keys) < 2:
            return
        _, node_id = property_keys[:2]
        property_id = property_keys[2:]

        validate = self._validation_mapper[step.action]
        return validate(step.entity_id,
                        step.entity_type,
                        dep_update=dep_update,
                        node_id=node_id,
                        property_id=property_id)

    @staticmethod
    def _in_new(dep_update, node_id, property_id):
        raw_node = utils.get_raw_node(dep_update.blueprint, node_id)
        return utils.traverse_object(raw_node, property_id) is not None

    def _in_old(self, dep_update, node_id, property_id):
        storage_node = self._get_storage_node(dep_update.deployment_id,
                                              node_id)

        return utils.traverse_object(storage_node, property_id) is not None


class OperationValidator(EntityValidatorBase):

    def _validate_entity(self, dep_update, step):
        operation_keys = utils.get_entity_keys(step.entity_id)
        if len(operation_keys) < 2:
            return

        _, node_id = operation_keys[:2]
        operation_id = operation_keys[2:]

        validate = self._validation_mapper[step.action]
        return validate(step.entity_id,
                        step.entity_type,
                        dep_update=dep_update,
                        node_id=node_id,
                        operation_id=operation_id)

    def _in_new(self, dep_update, node_id, operation_id):
        raw_node = utils.get_raw_node(dep_update.blueprint, node_id)
        return utils.traverse_object(raw_node, operation_id) is not None

    def _in_old(self, dep_update, node_id, operation_id):
        storage_node = self._get_storage_node(dep_update.deployment_id,
                                              node_id)
        return utils.traverse_object(storage_node, operation_id) is not None


class WorkflowValidator(EntityValidatorBase):

    def _validate_entity(self, dep_update, step):
        workflow_keys = utils.get_entity_keys(step.entity_id)

        if len(workflow_keys) < 2:
            return

        workflows = workflow_keys[0]
        workflow_id = workflow_keys[1:]

        validate = self._validation_mapper[step.action]

        return validate(step.entity_id,
                        step.entity_type,
                        dep_update=dep_update,
                        workflow_id=workflow_id,
                        workflows=workflows)

    @staticmethod
    def _in_new(dep_update, workflow_id, workflows):
        raw_workflows = dep_update.blueprint[workflows]
        return utils.traverse_object(raw_workflows, workflow_id) is not None

    def _in_old(self, dep_update, workflow_id, workflows):
        deployment_id = dep_update.deployment_id
        storage_workflows = getattr(self.sm.get_deployment(deployment_id),
                                    workflows,
                                    {})

        return \
            utils.traverse_object(storage_workflows, workflow_id) is not None


class OutputValidator(EntityValidatorBase):

    def _validate_entity(self, dep_update, step):
        output_keys = utils.get_entity_keys(step.entity_id)

        if len(output_keys) < 2:
            return

        outputs = output_keys[0]
        output_id = output_keys[1:]

        validate = self._validation_mapper[step.action]
        return validate(step.entity_id,
                        step.entity_type,
                        dep_update=dep_update,
                        output_id=output_id,
                        outputs=outputs)

    @staticmethod
    def _in_new(dep_update, output_id, outputs):

        raw_outputs = dep_update.blueprint[outputs]
        return utils.traverse_object(raw_outputs, output_id) is not None

    def _in_old(self, dep_update, output_id, outputs):
        storage_outputs = getattr(
                self.sm.get_deployment(dep_update.deployment_id),
                outputs,
                {})
        return utils.traverse_object(storage_outputs, output_id) is not None


class DescriptionValidator(EntityValidatorBase):
    def _validate_entity(self, dep_update, step):
        description_key = step.entity_id

        validate = self._validation_mapper[step.action]
        return validate(step.entity_id,
                        step.entity_type,
                        dep_update=dep_update,
                        description_key=description_key)

    def _in_new(self, dep_update, description_key):
        raw_description = dep_update.blueprint[description_key]
        return bool(raw_description)

    def _in_old(self, dep_update, description_key):
        deployment_id = dep_update.deployment_id
        storage_description = getattr(self.sm.get_deployment(deployment_id),
                                      description_key,
                                      {})
        return bool(storage_description)


class StepValidator(object):

    def __init__(self):
        self._validation_mapper = {
            ENTITY_TYPES.NODE: NodeValidator(),
            ENTITY_TYPES.RELATIONSHIP: RelationshipValidator(),
            ENTITY_TYPES.PROPERTY: PropertyValidator(),
            ENTITY_TYPES.OPERATION: OperationValidator(),
            ENTITY_TYPES.WORKFLOW: WorkflowValidator(),
            ENTITY_TYPES.OUTPUT: OutputValidator(),
            ENTITY_TYPES.DESCRIPTION: DescriptionValidator()
        }

    def validate(self, dep_update, step):
        """
        validate an entity id of provided type exists in provided blueprint.
        raises error if id doesn't exist
        :param dep_update: the deployment update object.
        :param step: the deployment update step object
        :return: None
        """
        if step.entity_type in ENTITY_TYPES:
            self._validation_mapper[step.entity_type].validate(dep_update,
                                                               step)
