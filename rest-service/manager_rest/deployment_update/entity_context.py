from utils import pluralize, get_entity_keys, get_raw_node, traverse_object
from manager_rest import storage_manager
from constants import ENTITY_TYPES


def get_entity_context(dep_update, entity_type, entity_id):
    entity_context_by_type = {
        ENTITY_TYPES.NODE: NodeContext,
        ENTITY_TYPES.RELATIONSHIP: RelationshipContext,
        ENTITY_TYPES.PROPERTY: PropertyContext,
        ENTITY_TYPES.OPERATION: _operation_context
    }

    context = entity_context_by_type[entity_type]

    return context(dep_update, *get_entity_keys(entity_id))


def _operation_context(dep_update, *entity_keys):
    if entity_keys[2] == pluralize(ENTITY_TYPES.RELATIONSHIP):
        return RelationshipOperationContext(dep_update, *entity_keys)
    else:
        return NodeOperationContext(dep_update, *entity_keys)


class EntityContextBase(object):
    NODES = pluralize(ENTITY_TYPES.NODE)
    RELATIONSHIPS = pluralize(ENTITY_TYPES.RELATIONSHIP)
    OPERATIONS = pluralize(ENTITY_TYPES.OPERATION)
    PROPERTIES = pluralize(ENTITY_TYPES.PROPERTY)
    PLUGINS = 'plugins'

    def __init__(self, dep_update, entity_type, node_id):
        self.sm = storage_manager.get_storage_manager()
        self._deployment_id = dep_update.deployment_id
        self._entity_type = entity_type
        self._node_id = node_id
        self._blueprint = dep_update.blueprint
        self._raw_node = get_raw_node(self.blueprint, self._node_id)

    @property
    def entity_id(self):
        return self._entity_id

    @property
    def blueprint(self):
        return self._blueprint

    @property
    def entity_type(self):
        return self._entity_type

    @property
    def storage_node(self):
        return self.sm.get_node(self._deployment_id, self._node_id) or {}

    @property
    def storage_node_instance(self):
        old_node_instances = self.sm.get_node_instance(
                filters={'deployment_id': self._deployment_id,
                         'node_id': self._node_id}
        )
        return old_node_instances[0] if old_node_instances else {}

    @property
    def raw_node(self):
        return self._raw_node

    @property
    def raw_node_id(self):
        return self.raw_node['id']

    @property
    def storage_node_id(self):
        return self.storage_node.id

    @property
    def storage_entity_value(self):
        raise NotImplementedError

    @property
    def raw_entity_value(self):
        raise NotImplementedError

    @property
    def deployment_id(self):
        return self._deployment_id


class NodeContext(EntityContextBase):
    def __init__(self,
                 dep_update,
                 nodes_key,
                 node_id,
                 *modification_id):
        super(NodeContext, self).__init__(dep_update,
                                          ENTITY_TYPES.NODE,
                                          node_id)
        entity_id = [nodes_key, node_id]
        entity_id.extend(modification_id)
        self._entity_id = ':'.join(entity_id)

    @property
    def raw_entity_value(self):
        return self.raw_node

    @property
    def storage_entity_value(self):
        return self.storage_node

    @property
    def entity_type(self):
        return ENTITY_TYPES.NODE


class RelationshipContext(EntityContextBase):
    def __init__(self,
                 dep_update,
                 nodes_key,
                 node_id,
                 relationships_key,
                 relationship_index,
                 *modification_id):
        super(RelationshipContext, self).__init__(dep_update,
                                                  ENTITY_TYPES.RELATIONSHIP,
                                                  node_id)

        self._relationship_index = int(relationship_index[1:-1])
        self._modification_id = modification_id
        self._raw_target_node = get_raw_node(self.blueprint, self.target_id)
        entity_id = [nodes_key, node_id, relationships_key,
                     '[{0}]'.format(relationship_index)]
        entity_id.extend(modification_id)
        self._entity_id = ':'.join(entity_id)

    @property
    def target_id(self):
        return self.storage_entity_value.get('target_id') or \
               self.raw_entity_value.get('target_id')

    @property
    def storage_target_node(self):
        return self.sm.get_node(self._deployment_id,
                                self.raw_entity_value['target_id']) or {}

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
    def modification_id(self):
        return self._modification_id


class PropertyContext(EntityContextBase):
    def __init__(self,
                 dep_update,
                 nodes_key,
                 node_id,
                 properties_key,
                 property_id,
                 *modification_id):
        super(PropertyContext, self).__init__(dep_update,
                                              ENTITY_TYPES.PROPERTY,
                                              node_id)

        self._property_id = property_id
        self._modification_id = modification_id
        entity_id = [nodes_key, node_id, properties_key, property_id]
        entity_id.extend(modification_id)
        self._entity_id = ':'.join(entity_id)

    @property
    def raw_entity_value(self):
        return self.raw_node['properties'][self._property_id]

    @property
    def storage_entity_value(self):
        return self.storage_node.properties[self._property_id]

    @property
    def property_id(self):
        return self._property_id


class NodeOperationContext(EntityContextBase):

    def __init__(self,
                 dep_update,
                 nodes_key,
                 node_id,
                 interfaces_key,
                 operation_id,
                 *modification_id):
        super(NodeOperationContext, self).__init__(dep_update,
                                                   ENTITY_TYPES.OPERATION,
                                                   node_id)

        self._operation_id = operation_id
        self._modification_id = modification_id
        entity_id = [nodes_key, node_id, interfaces_key, operation_id]
        entity_id.extend(modification_id)
        self._entity_id = ':'.join(entity_id)

    @property
    def raw_entity_value(self):
        base_entity = self.raw_node[self.OPERATIONS][self.operation_id]
        return traverse_object(base_entity, self.modification_id)

    @property
    def storage_entity_value(self):
        base_entity = self.storage_node.operations[self.operation_id]
        return traverse_object(base_entity, self.modification_id)

    @property
    def raw_modification_entity(self):
        return traverse_object(self.raw_entity_value, self.modification_id)

    @property
    def storage_modification_entity(self):
        return traverse_object(self.storage_entity_value, self.modification_id)

    @property
    def modification_id(self):
        return self._modification_id

    @property
    def operation_id(self):
        return self._operation_id


class RelationshipOperationContext(EntityContextBase):

    def __init__(self,
                 dep_update,
                 nodes_key,
                 node_id,
                 relatonships_key,
                 relationship_index,
                 operations_key,
                 operation_id,
                 *modification_id):
        super(RelationshipOperationContext, self).__init__(
                dep_update,
                ENTITY_TYPES.OPERATION,
                node_id)

        self._relationships_index = int(relationship_index[1:-1])
        self._operations_key = operations_key
        self._operation_id = operation_id
        self._modification_id = modification_id
        entity_id = [nodes_key, node_id, relatonships_key,
                     '[{0}]'.format(relationship_index), operation_id]
        entity_id.extend(modification_id)
        self._entity_id = ':'.join(entity_id)

    @property
    def operations_key(self):
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
    def modification_id(self):
        return self._modification_id

    @property
    def raw_operation(self):
        return self.raw_operations.get(self.operation_id)

    @property
    def storage_operation(self):
        return self.storage_operations.get(self.operation_id)

    @property
    def raw_entity_value(self):
        return traverse_object(self.raw_operation, self.modification_id)

    @property
    def storage_entity_value(self):
        return traverse_object(self.storage_operation, self.modification_id)

    @property
    def operation_id(self):
        return self._operation_id
