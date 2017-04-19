from copy import deepcopy

import utils as deployment_update_utils
from constants import ENTITY_TYPES, NODE_MOD_TYPES

from manager_rest import utils
from manager_rest.resource_manager import get_resource_manager
from manager_rest.storage import get_storage_manager, models, get_node
from entity_context import get_entity_context


class StorageClient(object):
    def __init__(self):
        self.sm = get_storage_manager()
        self.rm = get_resource_manager()


class UpdateHandler(StorageClient):
    def handle(self, *_, **__):
        raise NotImplementedError

    def finalize(self, *_, **__):
        raise NotImplementedError


class FrozenEntitiesHandlerBase(StorageClient):
    def add(self, ctx, current_entities):
        raise NotImplementedError

    def remove(self, ctx, current_entities):
        raise NotImplementedError


class NodeHandler(FrozenEntitiesHandlerBase):

    def add(self, ctx, current_entities):
        self.rm._create_deployment_nodes(
            deployment_id=ctx.deployment_id,
            plan=ctx.deployment_plan,
            node_ids=ctx.raw_node_id,
        )

        current_entities[ctx.raw_node_id] = ctx.storage_node.to_dict()
        # node_handler.raw_node

        # Update new node relationships target nodes. Since any relationship
        # with target interface requires the target node to hold a plugin
        # which supports the operation, we should update the mapping for
        # this plugin under the target node.
        target_ids = [r['target_id']
                      for r in ctx.raw_node.get(ctx.RELATIONSHIPS, [])]

        for node_id in target_ids:
            node = get_node(ctx.deployment_id, node_id)
            node.plugins = deployment_update_utils.get_raw_node(
                ctx.deployment_plan, node_id)['plugins']
            self.sm.update(node)
            current_entities[node_id] = node.to_dict()

        return ctx.raw_node_id

    def remove(self, ctx, current_entities):
        """Handles removing a node

        :param ctx:
        :return: the removed node
        """
        del(current_entities[ctx.storage_node.id])
        return ctx.storage_node.id


class ModifiableEntityHandlerBase(FrozenEntitiesHandlerBase):

        def remove(self, ctx, current_entities):
            raise NotImplementedError

        def add(self, ctx, current_entities):
            raise NotImplementedError

        def modify(self, ctx, current_entities):
            raise NotImplementedError


class RelationshipHandler(ModifiableEntityHandlerBase):

    def remove(self, ctx, current_entities):
        """Handles removing a relationship

        :return: the add_node.modification node
        """

        # Set the relationship to None only in the current entities.
        # The data model should be affected only after the lifecycle ran.
        current_node = current_entities[ctx.raw_node_id]
        current_node[ctx.RELATIONSHIPS][ctx.relationship_index] = None
        return ctx.raw_node_id, ctx.target_id

    def add(self, ctx, current_entities):
        """Handles adding a relationship

        :param ctx:
        :return: the add_node.modification node
        """
        # Update source relationships and plugins

        # Extract the new relationship from the deployment update plan
        new_relationship = \
            ctx.raw_node[ctx.RELATIONSHIPS][ctx.relationship_index]

        # Extract the current relationships and manipulate the relationships
        # size to support new relationships
        raw_relationships = \
            current_entities[ctx.raw_node_id][ctx.RELATIONSHIPS]
        self._resize_relationships(raw_relationships, ctx.relationship_index)
        raw_relationships[ctx.relationship_index] = new_relationship

        relationships = deepcopy(ctx.storage_node.relationships)
        relationships.append(new_relationship)
        ctx.storage_node.relationships = relationships
        ctx.storage_node.plugins = ctx.raw_node[ctx.PLUGINS]
        self.sm.update(ctx.storage_node)

        source_node = ctx.storage_node
        raw_source_node = current_entities[source_node.id]
        raw_source_node[ctx.PLUGINS] = source_node.plugins

        target_node = get_node(ctx.deployment_id, ctx.target_id)
        target_node.plugins = ctx.raw_target_node[ctx.PLUGINS]
        self.sm.update(target_node)

        current_entities[ctx.storage_target_node.id] = \
            ctx.storage_target_node.to_dict()

        return ctx.raw_node_id, ctx.target_id

    def modify(self, ctx, current_entities):

        source_index = ctx.relationship_index
        target_index = deployment_update_utils.parse_index(
            ctx.modification_breadcrumbs[0])

        relationships = current_entities[ctx.raw_node_id][ctx.RELATIONSHIPS]
        self._resize_relationships(relationships, target_index)

        relationship = ctx.storage_node.relationships[source_index]
        relationships[target_index] = relationship

        return ctx.raw_node_id, (source_index, target_index)

    @staticmethod
    def _resize_relationships(relationships, target_index):
        if len(relationships) <= target_index:
            offset = target_index - len(relationships) + 1
            relationships.extend([None] * offset)


class OperationHandler(ModifiableEntityHandlerBase):

    @staticmethod
    def _choose_and_execute_operation_handler(ctx,
                                              current_nodes,
                                              relationship_executor,
                                              node_executor):

        if ctx.entity_id.split(':')[2] == ctx.RELATIONSHIPS:
            modifier = relationship_executor
        else:
            # the operation host could be either relationship interfaces
            # or node interfaces.
            modifier = node_executor

        return modifier(ctx, current_nodes)

    def modify(self, ctx, current_entities):
        return self._choose_and_execute_operation_handler(
                ctx,
                current_entities,
                self._modify_relationship_operation,
                self._modify_node_operation)

    def _modify_node_operation(self, ctx, current_entities):
        new_operation = deployment_update_utils.create_dict(
            ctx.modification_breadcrumbs, ctx.raw_entity_value)
        node = get_node(ctx.deployment_id, ctx.raw_node_id)
        operations = deepcopy(node.operations)
        operations.update({ctx.operation_id: new_operation})
        node.operations = operations
        node.plugins = ctx.raw_node[ctx.PLUGINS]
        self.sm.update(node)

        current_node = current_entities[ctx.raw_node_id]
        if ctx.modification_breadcrumbs:
            operation_to_update = deployment_update_utils.traverse_object(
                    current_node[ctx.OPERATIONS][ctx.operation_id],
                    ctx.modification_breadcrumbs[:-1]
            )
            operation_to_update[ctx.modification_breadcrumbs[-1]] = \
                ctx.raw_entity_value
        else:
            operation_to_update = current_node[ctx.OPERATIONS]
            operation_to_update[ctx.operation_id] = ctx.raw_entity_value

        current_node[ctx.PLUGINS] = ctx.raw_node[ctx.PLUGINS]

        return ctx.entity_id

    def _modify_relationship_operation(self, ctx, current_entities):
        current_node = current_entities[ctx.raw_node_id]
        relationships = current_node[ctx.RELATIONSHIPS]
        operations = relationships[ctx.relationship_index][ctx.operations_key]

        if ctx.modification_breadcrumbs:
            operation_to_update = \
                deployment_update_utils.traverse_object(
                    operations[ctx.operation_id],
                    ctx.modification_breadcrumbs[:-1])
            operation_to_update[ctx.modification_breadcrumbs[-1]] = \
                ctx.raw_entity_value
        else:
            operations[ctx.operation_id] = ctx.raw_entity_value

        current_node[ctx.PLUGINS] = ctx.raw_node[ctx.PLUGINS]

        node = get_node(ctx.deployment_id, ctx.raw_node_id)
        node.relationships = deepcopy(relationships)
        node.plugins = ctx.raw_node[ctx.PLUGINS]
        self.sm.update(node)

        return ctx.entity_id

    def remove(self, ctx, current_entities):
        return self._choose_and_execute_operation_handler(
                ctx,
                current_entities,
                self._remove_relationship_operation,
                self._remove_node_operation)

    @staticmethod
    def _remove_node_operation(ctx, current_entities):
        current_node = current_entities[ctx.raw_node_id]
        del(current_node[ctx.OPERATIONS][ctx.operation_id])

        return ctx.entity_id

    @staticmethod
    def _remove_relationship_operation(ctx, current_entities):
        current_node = current_entities[ctx.raw_node_id]
        modified_relationship = \
            current_node[ctx.RELATIONSHIPS][ctx.relationship_index]
        del(modified_relationship[ctx.operations_key][ctx.operation_id])

        return ctx.entity_id

    def add(self, ctx, current_entities):
        return self._choose_and_execute_operation_handler(
                ctx,
                current_entities,
                self._add_relationship_operation,
                self._add_node_operation)

    def _add_node_operation(self, ctx, current_entities):
        # since the add_node_operation basically sets the the value of the
        # property to the new value, it's the same as modifying the same
        # operation.
        return self._modify_node_operation(ctx, current_entities)

    def _add_relationship_operation(self, ctx, current_entities):
        # since the add_relationship_operation basically sets the the value of
        # the property to the new value, it's the same as modifying the same
        # operation.
        return self._modify_relationship_operation(ctx, current_entities)


class PropertyHandler(ModifiableEntityHandlerBase):
    def modify(self, ctx, current_entities):
        node = get_node(ctx.deployment_id, ctx.raw_node_id)
        properties = deepcopy(node.properties)
        properties[ctx.property_id] = deployment_update_utils.create_dict(
            ctx.modification_breadcrumbs,
            ctx.raw_entity_value
        )
        node.properties = properties
        self.sm.update(node)

        properties = current_entities[ctx.raw_node_id][ctx.PROPERTIES]

        if ctx.modification_breadcrumbs:
            property_to_update = \
                deployment_update_utils.traverse_object(
                    properties[ctx.property_id],
                    ctx.modification_breadcrumbs[:-1])
            property_to_update[ctx.modification_breadcrumbs[-1]] = \
                ctx.raw_entity_value
        else:
            properties[ctx.property_id] = ctx.raw_entity_value

        return ctx.entity_id

    def remove(self, ctx, current_entities):
        node_id = ctx.raw_node_id
        del(current_entities[node_id][ctx.PROPERTIES][ctx.property_id])

        return ctx.entity_id

    def add(self, ctx, current_entities):
        # since the add property basically sets the the value of the property
        # to the new value, it's the same as modifying the same property.
        return self.modify(ctx, current_entities)


class WorkflowHandler(ModifiableEntityHandlerBase):

    def add(self, ctx, current_entities):
        new_workflow = deployment_update_utils.create_dict(
            ctx.modification_breadcrumbs, ctx.raw_entity_value)

        deployment = self.sm.get(models.Deployment, ctx.deployment_id)
        new_workflows = deployment.workflows.copy()
        new_workflows.update({ctx.workflow_id: new_workflow})
        deployment.workflows = new_workflows
        self.sm.update(deployment)

        current_entities[ctx.WORKFLOWS][ctx.workflow_id] = new_workflow

    def remove(self, ctx, current_entities):
        deployment = self.sm.get(models.Deployment, ctx.deployment_id)
        new_workflows = deployment.workflows.copy()

        del(current_entities[ctx.WORKFLOWS][ctx.workflow_id])
        del new_workflows[ctx.workflow_id]

        deployment.workflows = new_workflows
        self.sm.update(deployment)

        return ctx.entity_id

    def modify(self, ctx, current_entities):
        return self.add(ctx, current_entities)


class OutputHandler(ModifiableEntityHandlerBase):

    def add(self, ctx, current_entities):
        new_output = deployment_update_utils.create_dict(
            ctx.modification_breadcrumbs, ctx.raw_entity_value)

        deployment = self.sm.get(models.Deployment, ctx.deployment_id)
        new_outputs = deployment.outputs.copy()
        new_outputs.update({ctx.output_id: new_output})
        deployment.outputs = new_outputs
        self.sm.update(deployment)

        current_entities[ctx.OUTPUTS][ctx.output_id] = ctx.raw_entity_value

        return ctx.entity_id

    def remove(self, ctx, current_entities):
        deployment = self.sm.get(models.Deployment, ctx.deployment_id)
        deployment.outputs = deepcopy(deployment.outputs)

        del(current_entities[ctx.OUTPUTS][ctx.output_id])
        del deployment.outputs[ctx.output_id]

        self.sm.update(deployment)
        return ctx.entity_id

    def modify(self, ctx, current_entities):
        return self.add(ctx, current_entities)


class DescriptionHandler(ModifiableEntityHandlerBase):

    def remove(self, ctx, current_entities):
        return self._set_description(ctx, current_entities, None)

    def modify(self, ctx, current_entities):
        return self.add(ctx, current_entities)

    def add(self, ctx, current_entities):
        new_value = ctx.raw_entity_value
        return self._set_description(ctx, current_entities, new_value)

    def _set_description(self, ctx, current_entities, new_value):
        deployment = self.sm.get(models.Deployment, ctx.deployment_id)
        deployment.description = new_value
        self.sm.update(deployment)
        current_entities[ctx.DESCRIPTION] = new_value
        return ctx.entity_id


class DeploymentUpdateNodeHandler(UpdateHandler):

    def __init__(self):
        super(DeploymentUpdateNodeHandler, self).__init__()
        self._supported_entity_types = {ENTITY_TYPES.NODE,
                                        ENTITY_TYPES.RELATIONSHIP,
                                        ENTITY_TYPES.OPERATION,
                                        ENTITY_TYPES.PROPERTY}
        self._entity_handlers = {
            ENTITY_TYPES.NODE: NodeHandler(),
            ENTITY_TYPES.RELATIONSHIP: RelationshipHandler(),
            ENTITY_TYPES.OPERATION: OperationHandler(),
            ENTITY_TYPES.PROPERTY: PropertyHandler()
        }

    def handle(self, dep_update):
        """handles updating new and extended nodes onto the storage.

        :param dep_update:
        :return: a list of all of the nodes
        (including the non add_node.modification nodes)
        """
        current_nodes = self.sm.list(
            models.Node,
            filters={'deployment_id': dep_update.deployment_id}
        )
        nodes_dict = {node.id: deepcopy(node.to_dict())
                      for node in current_nodes}
        modified_entities = deployment_update_utils.ModifiedEntitiesDict()

        # Iterate over the steps of the deployment update and handle each
        # step according to its operation, passing the deployment update
        # object, step entity type, entity id and a dict of updated nodes.
        # Each handler updated the dict of updated nodes, which enables
        # accumulating changes.
        for step in dep_update.steps:
            if step.entity_type in self._supported_entity_types:
                entity_handler = self._entity_handlers[step.entity_type]
                entity_updater = getattr(entity_handler, step.action)
                entity_context = get_entity_context(dep_update.deployment_plan,
                                                    dep_update.deployment_id,
                                                    step.entity_type,
                                                    step.entity_id)

                entity_id = entity_updater(entity_context, nodes_dict)

                modified_entities[step.entity_type].append(entity_id)

        return modified_entities, nodes_dict.values()

    def finalize(self, dep_update):
        """update any removed entity from nodes

        :param dep_update: the deployment update object itself.
        :return:
        """
        removed_and_related = dep_update.deployment_update_node_instances[
            NODE_MOD_TYPES.REMOVED_AND_RELATED]
        removed_node_instances = \
            removed_and_related.get(NODE_MOD_TYPES.AFFECTED, [])

        removed_node_ids = deployment_update_utils.extract_ids(
            removed_node_instances, 'node_id')

        # Since not all changes are caught on the node instances (actually only
        # the removing/adding of relationships and nodes) we need to apply all
        # of the changes, thus screening all of the nodes except the ones
        # deleted is a valid solution.
        modified_nodes = [n for n in dep_update.deployment_update_nodes
                          if n['id'] not in removed_node_ids]

        for modified_node in modified_nodes:
            # Any relationship deleted or inserted to a new index could create
            # 'None' relationships, in this final phase we remove those (if by
            # some reason any left).
            modified_node['relationships'] = \
                [r for r in modified_node['relationships'] if r]
            node = get_node(
                modified_node['deployment_id'],
                modified_node['id']
            )
            node.number_of_instances = modified_node['number_of_instances']
            node.planned_number_of_instances = modified_node[
                'planned_number_of_instances']
            node.relationships = modified_node['relationships']
            node.operations = modified_node['operations']
            node.plugins = modified_node['plugins']
            node.properties = modified_node['properties']
            self.sm.update(node)

        for removed_node_instance in removed_node_instances:
            node = get_node(
                dep_update.deployment_id,
                removed_node_instance['node_id']
            )
            self.sm.delete(node)


class DeploymentUpdateNodeInstanceHandler(UpdateHandler):

    def __init__(self):
        super(DeploymentUpdateNodeInstanceHandler, self).__init__()
        self._handlers_mapper = {
            NODE_MOD_TYPES.ADDED_AND_RELATED:
                self._handle_adding_node_instance,
            NODE_MOD_TYPES.EXTENDED_AND_RELATED:
                self._handle_adding_relationship_instance,
            NODE_MOD_TYPES.REDUCED_AND_RELATED:
                self._handle_removing_relationship_instance,
            NODE_MOD_TYPES.REMOVED_AND_RELATED:
                self._handle_removing_node_instance
        }

    def handle(self, dep_update, updated_instances):
        """Handles updating node instances according to the updated_instances

        :param dep_update:
        :param updated_instances:
        :return: dictionary of add_node.modification node instances with key as
        modification type
        """
        # create node instance relationship ordering
        modified_instances = \
            {k: {} for k, _ in self._handlers_mapper.iteritems()}
        for change_type, handler in self._handlers_mapper.iteritems():
            if updated_instances[change_type]:
                modified_instances[change_type] = \
                    handler(updated_instances[change_type], dep_update)

        return modified_instances

    def _handle_adding_node_instance(self, instances, dep_update):
        """Handles adding a node instance

        :param instances:
        :param dep_update:
        :return: the added and related node instances
        """
        added_instances = []
        add_related_instances = []

        for node_instance in instances:
            modification = node_instance.get('modification', 'related')
            if modification == 'added':
                changes = {
                    'deployment_id': dep_update.deployment_id,
                    'version': None,
                    'state': None,
                    'runtime_properties': {}
                }
                node_instance.update(changes)
                added_instances.append(node_instance)
            else:
                add_related_instances.append(node_instance)

        self.rm._create_deployment_node_instances(
            dep_update.deployment_id,
            added_instances
        )

        return {
            NODE_MOD_TYPES.AFFECTED: added_instances,
            NODE_MOD_TYPES.RELATED: add_related_instances
        }

    def _handle_removing_node_instance(self, instances, *_):
        """Handles removing a node instance

        :param raw_instances:
        :return: the removed and related node instances
        """
        removed_raw_instances = []
        remove_related_raw_instances = []

        for raw_node_instance in instances:
            modification = raw_node_instance.pop('modification', 'related')
            if modification == 'removed':
                removed_raw_instances.append(raw_node_instance)
            else:
                remove_related_raw_instances.append(raw_node_instance)

        return {
            NODE_MOD_TYPES.AFFECTED: removed_raw_instances,
            NODE_MOD_TYPES.RELATED: remove_related_raw_instances
        }

    def _handle_adding_relationship_instance(self, instances, *_):
        """Handles adding a relationship to a node instance

        :param instances:
        :return: the extended and related node instances
        """
        modified_raw_instances = []
        modify_related_raw_instances = []

        for node_instance in instances:
            modification = node_instance.get('modification', 'related')
            if modification == 'extended':
                # adding new relationships to the current relationships
                instance = self.sm.get(
                    models.NodeInstance,
                    node_instance['id'],
                    locking=True
                )
                relationships = deepcopy(instance.relationships)

                node_instance['relationships'] = \
                    sorted(node_instance['relationships'],
                           key=lambda r: r.get('rel_index', 0))

                relationships.extend(node_instance['relationships'])
                instance.relationships = relationships
                instance.version = _handle_version(node_instance['version'])
                self.sm.update(instance)
                modified_raw_instances.append(node_instance)
            else:
                modify_related_raw_instances.append(node_instance)

        return \
            {
                NODE_MOD_TYPES.AFFECTED: modified_raw_instances,
                NODE_MOD_TYPES.RELATED: modify_related_raw_instances
            }

    def _handle_removing_relationship_instance(self, instances, *_):
        """Handles removing a relationship to a node instance

        :param raw_instances:
        :return: the reduced and related node instances
        """
        modified_raw_instances = []
        modify_related_raw_instances = []

        for node_instance in instances:
            modification = node_instance.get('modification', 'related')
            if modification == 'reduced':
                modified_node = self.sm.get(
                    models.NodeInstance, node_instance['id']
                ).to_dict()
                # changing the new state of relationships on the instance
                # to not include the removed relationship
                target_ids = [rel['target_id']
                              for rel in node_instance['relationships']]
                relationships = [rel for rel in modified_node['relationships']
                                 if rel['target_id'] not in target_ids]
                modified_node['relationships'] = relationships
                modified_node['version'] = \
                    _handle_version(node_instance['version'])
                modified_raw_instances.append(modified_node)
            else:
                modify_related_raw_instances.append(node_instance)

        return {
            NODE_MOD_TYPES.AFFECTED: modified_raw_instances,
            NODE_MOD_TYPES.RELATED: modify_related_raw_instances
        }

    def finalize(self, dep_update):
        """update any removed entity from node instances

        :param dep_update: the deployment update object
        :return:
        """
        extended_node_instances = \
            dep_update.deployment_update_node_instances[
                NODE_MOD_TYPES.EXTENDED_AND_RELATED].get(
                    NODE_MOD_TYPES.AFFECTED, [])
        reduced_node_instances = \
            dep_update.deployment_update_node_instances[
                NODE_MOD_TYPES.REDUCED_AND_RELATED].get(
                    NODE_MOD_TYPES.AFFECTED, [])
        removed_node_instances = \
            dep_update.deployment_update_node_instances[
                NODE_MOD_TYPES.REMOVED_AND_RELATED].get(
                    NODE_MOD_TYPES.AFFECTED, [])

        self._reorder_relationships(
                dep_update.deployment_id,
                dep_update.modified_entity_ids['rel_mappings'])

        self._reduce_node_instances(reduced_node_instances,
                                    extended_node_instances)

        for removed_node_instance in removed_node_instances:
            node_instance = self.sm.get(
                models.NodeInstance,
                removed_node_instance['id']
            )
            self.sm.delete(node_instance)

    def _reduce_node_instances(self,
                               reduced_node_instances,
                               extended_node_instances):
        for reduced_node_instance in reduced_node_instances:
            updated_node_instance = self.sm.get(
                models.NodeInstance,
                reduced_node_instance['id'],
                locking=True
            )
            storage_relationships = updated_node_instance.relationships
            self._clean_relationship_index_field(storage_relationships)
            # Get all the remaining relationships
            remaining_relationships = reduced_node_instance['relationships']
            # Get the extended node instances
            extended_node_instances = \
                [i for i in extended_node_instances
                 if (i['id'] == reduced_node_instance['id'] and
                     'modification' in i)]

            # If this node was indeed extended, append the new relationships
            # to the remaining relationships (from the reduced node instance)
            if extended_node_instances:
                relationships = extended_node_instances[0]['relationships']
                self._clean_relationship_index_field(relationships)
                remaining_relationships.extend(relationships)

            remaining_relationships = \
                filter(lambda r: r in remaining_relationships,
                       storage_relationships)

            updated_node_instance.relationships = deepcopy(
                remaining_relationships)
            updated_node_instance.version += 1
            self.sm.update(updated_node_instance)

    @staticmethod
    def _clean_relationship_index_field(relationships):
        for relationship in relationships:
            if 'rel_index' in relationship:
                del(relationship['rel_index'])
        return relationships

    def _reorder_relationships(self, deployment_id, rel_order_instances):

        for node_id, indices_list in rel_order_instances.iteritems():
            # Getting node instance ID from deployment ID and node ID
            node_instance_id = self.sm.list(
                models.NodeInstance,
                filters={'deployment_id': deployment_id,
                         'node_id': node_id}
            ).items[0].id
            node_instance = self.sm.get(
                models.NodeInstance,
                node_instance_id,
                locking=True
            )
            relationships = deepcopy(node_instance.relationships)
            old_relationships = deepcopy(relationships)

            # Move the order of any 'modified' relationships
            for old_index, new_index in indices_list:
                relationships[new_index] = old_relationships[old_index]

            # Set any new relationships to their final index
            for index, relationship in \
                    ((i, r) for i, r in enumerate(old_relationships)
                     if 'rel_index' in r):
                relationships[index] = None
                relationships[relationship['rel_index']] = relationship

            relationships = [r for r in relationships if r]
            node_instance.relationships = relationships
            self.sm.update(node_instance)


class DeploymentUpdateDeploymentHandler(UpdateHandler):

    def __init__(self):
        super(DeploymentUpdateDeploymentHandler, self).__init__()
        self._entity_handlers = {
            ENTITY_TYPES.WORKFLOW: WorkflowHandler(),
            ENTITY_TYPES.OUTPUT: OutputHandler(),
            ENTITY_TYPES.DESCRIPTION: DescriptionHandler()
        }
        self._supported_entity_types = {ENTITY_TYPES.WORKFLOW,
                                        ENTITY_TYPES.OUTPUT,
                                        ENTITY_TYPES.DESCRIPTION}

    def handle(self, dep_update):
        deployment = dep_update.deployment.to_dict()
        modified_entities = {
            ENTITY_TYPES.WORKFLOW: [],
            ENTITY_TYPES.OUTPUT: [],
            ENTITY_TYPES.DESCRIPTION: []
        }
        for step in dep_update.steps:
            if step.entity_type in self._supported_entity_types:
                entity_handler = self._entity_handlers[step.entity_type]
                entity_updater = getattr(entity_handler, step.action)
                entity_context = get_entity_context(dep_update.deployment_plan,
                                                    dep_update.deployment_id,
                                                    step.entity_type,
                                                    step.entity_id)
                entity_id = entity_updater(entity_context, deployment)

                modified_entities[step.entity_type].append(entity_id)

        return modified_entities, deployment

    def finalize(self, dep_update):
        deployment = dep_update.deployment
        deployment.updated_at = utils.get_formatted_timestamp()
        self.sm.update(deployment)


def _handle_version(version):
    return version if version is not None else 0
