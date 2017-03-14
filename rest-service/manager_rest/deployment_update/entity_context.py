import utils

from constants import ENTITY_TYPES

from manager_rest.storage import get_storage_manager, models, get_node


def get_entity_context(plan, deployment_id, entity_type, entity_id):
    entity_context_by_type = {
        ENTITY_TYPES.NODE: NodeContext,
        ENTITY_TYPES.RELATIONSHIP: RelationshipContext,
        ENTITY_TYPES.PROPERTY: PropertyContext,
        ENTITY_TYPES.OPERATION: _operation_context,
        ENTITY_TYPES.WORKFLOW: WorkflowContext,
        ENTITY_TYPES.OUTPUT: OutputContext,
        ENTITY_TYPES.DESCRIPTION: DescriptionContext
    }

    context = entity_context_by_type[entity_type]

    return context(plan, deployment_id, *utils.get_entity_keys(entity_id))


def _operation_context(plan, deployment_id, *entity_keys):
    if entity_keys[2] == utils.pluralize(ENTITY_TYPES.RELATIONSHIP):
        entity_context = RelationshipInterfaceOperationContext
    else:
        entity_context = NodeInterfaceOperationContext

    return entity_context(plan, deployment_id, *entity_keys)


class EntityContextBase(object):
    NODES = utils.pluralize(ENTITY_TYPES.NODE)
    RELATIONSHIPS = utils.pluralize(ENTITY_TYPES.RELATIONSHIP)
    OPERATIONS = utils.pluralize(ENTITY_TYPES.OPERATION)
    PROPERTIES = utils.pluralize(ENTITY_TYPES.PROPERTY)
    WORKFLOWS = utils.pluralize(ENTITY_TYPES.WORKFLOW)
    OUTPUTS = utils.pluralize(ENTITY_TYPES.OUTPUT)
    DESCRIPTION = 'description'
    PLUGINS = 'plugins'

    def __init__(self, plan, deployment_id, entity_type, top_level_entity_id):
        self.sm = get_storage_manager()
        self._deployment_id = deployment_id
        self._entity_type = entity_type
        self._top_level_entity_id = top_level_entity_id
        self._plan = plan

    @property
    def deployment_plan(self):
        return self._plan

    @property
    def entity_type(self):
        return self._entity_type

    @property
    def deployment_id(self):
        return self._deployment_id

    @property
    def entity_id(self):
        raise NotImplementedError

    @property
    def storage_entity_value(self):
        raise NotImplementedError

    @property
    def raw_entity_value(self):
        raise NotImplementedError


class NodeContextBase(EntityContextBase):

    def __init__(self, plan, deployment_id, entity_type, top_level_entity_id):
        super(NodeContextBase, self).__init__(plan,
                                              deployment_id,
                                              entity_type,
                                              top_level_entity_id)
        self._raw_super_entity = \
            utils.get_raw_node(self.deployment_plan, self._top_level_entity_id)

    @property
    def entity_id(self):
        raise NotImplementedError

    @property
    def storage_entity_value(self):
        raise NotImplementedError

    @property
    def raw_entity_value(self):
        raise NotImplementedError

    @property
    def storage_node(self):
        return get_node(self._deployment_id, self._top_level_entity_id) or None

    @property
    def raw_node(self):
        return self._raw_super_entity

    @property
    def raw_node_id(self):
        return self.raw_node['id']


class NodeContext(NodeContextBase):
    def __init__(self,
                 plan,
                 deployment_id,
                 nodes_key,
                 top_level_entity_id,
                 *modification_breadcrumbs):
        super(NodeContext, self).__init__(plan,
                                          deployment_id,
                                          ENTITY_TYPES.NODE,
                                          top_level_entity_id)
        entity_keys = [nodes_key, top_level_entity_id]
        entity_keys.extend(modification_breadcrumbs)
        self._entity_id = ':'.join(entity_keys)

    @property
    def raw_entity_value(self):
        return self.raw_node

    @property
    def storage_entity_value(self):
        return self.storage_node

    @property
    def entity_id(self):
        return self._entity_id


class RelationshipContext(NodeContextBase):
    def __init__(self,
                 plan,
                 deployment_id,
                 nodes_key,
                 top_level_entity_id,
                 relationships_key,
                 relationship_index,
                 *modification_breadcrumbs):
        super(RelationshipContext, self).__init__(plan,
                                                  deployment_id,
                                                  ENTITY_TYPES.RELATIONSHIP,
                                                  top_level_entity_id)

        self._relationship_index = utils.parse_index(relationship_index)
        self._modification_breadcrumbs = modification_breadcrumbs
        self._raw_target_node = utils.get_raw_node(self.deployment_plan,
                                                   self.target_id)
        entity_keys = [nodes_key, top_level_entity_id, relationships_key,
                       relationship_index]
        entity_keys.extend(modification_breadcrumbs)
        self._entity_id = ':'.join(entity_keys)

    @property
    def target_id(self):
        return self.raw_entity_value.get('target_id') or \
               self.storage_entity_value.get('target_id')

    @property
    def storage_target_node(self):
        return get_node(self._deployment_id, self.target_id) or None

    @property
    def raw_target_node(self):
        return self._raw_target_node

    @property
    def raw_entity_value(self):
        if len(self.raw_node['relationships']) > self.relationship_index:
            return self.raw_node['relationships'][self.relationship_index]
        else:
            return {}

    @property
    def storage_entity_value(self):
        if len(self.storage_node.relationships) > self.relationship_index:
            return self.storage_node.relationships[self.relationship_index]
        else:
            return {}

    @property
    def relationship_index(self):
        return self._relationship_index

    @property
    def modification_breadcrumbs(self):
        return self._modification_breadcrumbs

    @property
    def entity_id(self):
        return self._entity_id


class PropertyContext(NodeContextBase):
    def __init__(self,
                 plan,
                 deployment_id,
                 nodes_key,
                 top_level_entity_id,
                 properties_key,
                 property_id,
                 *modification_breadcrumbs):
        super(PropertyContext, self).__init__(plan,
                                              deployment_id,
                                              ENTITY_TYPES.PROPERTY,
                                              top_level_entity_id)

        self._property_id = property_id
        self._modification_breadcrumbs = modification_breadcrumbs
        entity_keys = \
            [nodes_key, top_level_entity_id, properties_key, property_id]
        entity_keys.extend(modification_breadcrumbs)
        self._entity_id = ':'.join(entity_keys)

    @property
    def raw_entity_value(self):
        return utils.traverse_object(self.raw_entity,
                                     self._modification_breadcrumbs)

    @property
    def storage_entity_value(self):
        return utils.traverse_object(self.storage_entity,
                                     self._modification_breadcrumbs)

    @property
    def raw_entity(self):
        return self.raw_node['properties'][self.property_id]

    @property
    def storage_entity(self):
        return self.storage_node.properties[self.property_id]

    @property
    def property_id(self):
        return self._property_id

    @property
    def entity_id(self):
        return self._entity_id

    @property
    def modification_breadcrumbs(self):
        return self._modification_breadcrumbs


class NodeInterfaceOperationContext(NodeContextBase):

    def __init__(self,
                 plan,
                 deployment_id,
                 nodes_key,
                 top_level_entity_id,
                 operations_key,
                 operation_id,
                 *modification_breadcrumbs):
        super(NodeInterfaceOperationContext, self).__init__(
                plan,
                deployment_id,
                ENTITY_TYPES.OPERATION,
                top_level_entity_id)

        self._operation_id = operation_id
        self._modification_breadcrumbs = modification_breadcrumbs
        entity_keys = [nodes_key, top_level_entity_id, operation_id]
        entity_keys.extend(modification_breadcrumbs)
        self._entity_id = ':'.join(entity_keys)

    @property
    def raw_entity_value(self):
        return utils.traverse_object(self.raw_entity,
                                     self.modification_breadcrumbs)

    @property
    def storage_entity_value(self):
        return utils.traverse_object(self.storage_entity,
                                     self._modification_breadcrumbs)

    @property
    def raw_entity(self):
        return self.raw_node[self.OPERATIONS][self.operation_id]

    @property
    def storage_entity(self):
        return self.storage_node.operations[self.operation_id]

    @property
    def modification_breadcrumbs(self):
        return self._modification_breadcrumbs

    @property
    def operation_id(self):
        return self._operation_id

    @property
    def entity_id(self):
        return self._entity_id


class RelationshipInterfaceOperationContext(NodeContextBase):

    def __init__(self,
                 plan,
                 deployment_id,
                 nodes_key,
                 top_level_entity_id,
                 relatonships_key,
                 relationship_index,
                 operations_key,
                 operation_id,
                 *modification_breadcrumbs):
        super(RelationshipInterfaceOperationContext, self).__init__(
            plan,
            deployment_id,
            ENTITY_TYPES.OPERATION,
            top_level_entity_id)

        self._relationships_index = utils.parse_index(relationship_index)
        self._operations_key = operations_key
        self._operation_id = operation_id
        self._modification_breadcrumbs = modification_breadcrumbs
        entity_keys = [nodes_key, top_level_entity_id, relatonships_key,
                       relationship_index, operation_id]
        entity_keys.extend(modification_breadcrumbs)
        self._entity_id = ':'.join(entity_keys)

    @property
    def operations_key(self):
        """
        Operation key could hold only two possible keys. e.g. source and
        target operations.
        :return:
        """
        return self._operations_key

    @property
    def raw_operations(self):
        return self.raw_relationship[self.operations_key]

    @property
    def storage_operations(self):
        return self.storage_relationship[self.operations_key]

    @property
    def relationship_index(self):
        return self._relationships_index

    @property
    def raw_relationship(self):
        return self.raw_node[self.RELATIONSHIPS][self._relationships_index]

    @property
    def storage_relationship(self):
        return self.storage_node.relationships[self._relationships_index]

    @property
    def modification_breadcrumbs(self):
        return self._modification_breadcrumbs

    @property
    def raw_entity(self):
        return self.raw_operations.get(self.operation_id)

    @property
    def storage_entity(self):
        return self.storage_operations.get(self.operation_id)

    @property
    def raw_entity_value(self):
        return utils.traverse_object(self.raw_entity,
                                     self.modification_breadcrumbs)

    @property
    def storage_entity_value(self):
        return utils.traverse_object(self.storage_entity,
                                     self.modification_breadcrumbs)

    @property
    def operation_id(self):
        return self._operation_id

    @property
    def entity_id(self):
        return self._entity_id


class DeploymentContextBase(EntityContextBase):

    def entity_id(self):
        raise NotImplementedError

    def storage_entity_value(self):
        raise NotImplementedError

    def raw_entity_value(self):
        raise NotImplementedError

    def _get_entity(self, top_level_entity):
        return top_level_entity[self._top_level_entity_id]

    def _get_entity_value(self, source_entity):
        if self._modification_breadcrumbs:
            return utils.traverse_object(source_entity,
                                         self.modification_breadcrumbs)
        else:
            return source_entity


class WorkflowContext(DeploymentContextBase):

    def __init__(self,
                 plan,
                 deployment_id,
                 workflows_key,
                 top_level_entity_id,
                 *modification_breadcrumbs):
        super(WorkflowContext, self).__init__(plan,
                                              deployment_id,
                                              ENTITY_TYPES.WORKFLOW,
                                              top_level_entity_id)
        self._modification_breadcrumbs = modification_breadcrumbs
        entity_keys = [workflows_key, top_level_entity_id]
        entity_keys.extend(modification_breadcrumbs)
        self._entity_id = ':'.join(entity_keys)

    @property
    def storage_entity(self):
        deployment = self.sm.get(models.Deployment, self.deployment_id)
        return self._get_entity(deployment.workflows)

    @property
    def raw_entity(self):
        return self._get_entity(self.deployment_plan[self.WORKFLOWS])

    @property
    def entity_id(self):
        return self._entity_id

    @property
    def storage_entity_value(self):
        return self._get_entity_value(self.storage_entity)

    @property
    def raw_entity_value(self):
        return self._get_entity_value(self.raw_entity)

    @property
    def workflow_id(self):
        return self._top_level_entity_id

    @property
    def modification_breadcrumbs(self):
        return self._modification_breadcrumbs


class DescriptionContext(DeploymentContextBase):

    def __init__(self,
                 plan,
                 deployment_id,
                 description_key):
        super(DescriptionContext, self).__init__(plan,
                                                 deployment_id,
                                                 ENTITY_TYPES.DESCRIPTION,
                                                 description_key)

    @property
    def entity_id(self):
        return self._top_level_entity_id

    @property
    def storage_entity(self):
        deployment = self.sm.get(models.Deployment, self.deployment_id)
        return deployment.description

    @property
    def raw_entity(self):
        return self._get_entity(self.deployment_plan)

    @property
    def raw_entity_value(self):
        return self.raw_entity

    @property
    def storage_entity_value(self):
        return self.storage_entity


class OutputContext(DeploymentContextBase):

    def __init__(self,
                 plan,
                 deployment_id,
                 workflows_key,
                 top_level_entity_id,
                 *modification_breadcrumbs):
        super(OutputContext, self).__init__(plan,
                                            deployment_id,
                                            ENTITY_TYPES.OUTPUT,
                                            top_level_entity_id)
        self._modification_breadcrumbs = modification_breadcrumbs
        entity_keys = [workflows_key, top_level_entity_id]
        entity_keys.extend(modification_breadcrumbs)
        self._entity_id = ':'.join(entity_keys)

    @property
    def storage_entity(self):
        deployment = self.sm.get(models.Deployment, self.deployment_id)
        return self._get_entity(deployment.outputs)

    @property
    def raw_entity(self):
        return self._get_entity(self.deployment_plan[self.OUTPUTS])

    @property
    def entity_id(self):
        return self._entity_id

    @property
    def storage_entity_value(self):
        return self._get_entity_value(self.storage_entity)

    @property
    def raw_entity_value(self):
        return self._get_entity_value(self.raw_entity)

    @property
    def output_id(self):
        return self._top_level_entity_id

    @property
    def modification_breadcrumbs(self):
        return self._modification_breadcrumbs
