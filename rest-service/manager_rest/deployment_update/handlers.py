import utils
import manager_rest.models
import manager_rest.manager_exceptions
from manager_rest import storage_manager
from manager_rest.blueprints_manager import get_blueprints_manager
from entity_context import get_entity_context

from constants import (ACTION_TYPES,
                       ENTITY_TYPES,
                       NODE_MOD_TYPES)


class StorageClient(object):
    def __init__(self):
        self.sm = storage_manager.get_storage_manager()


class UpdateHandler(StorageClient):
    def handle(self, *_, **__):
        raise NotImplementedError

    def finalize(self, *_, **__):
        raise NotImplementedError


class DeploymentUpdateNodeHandler(UpdateHandler):

    def __init__(self):
        super(DeploymentUpdateNodeHandler, self).__init__()
        self.modified_entities = utils.ModifiedEntitiesDict()
        self._supported_entity_types = {ENTITY_TYPES.NODE,
                                        ENTITY_TYPES.RELATIONSHIP,
                                        ENTITY_TYPES.OPERATION,
                                        ENTITY_TYPES.PROPERTY}
        self.entities_update_mapper = {
            ACTION_TYPES.ADD: self._add_entity,
            ACTION_TYPES.REMOVE: self._remove_entity,
            ACTION_TYPES.MODIFY: self._modify_entity
        }

        self._add_entity_mapper = {
            ENTITY_TYPES.NODE: self._add_node,
            ENTITY_TYPES.RELATIONSHIP: self._add_relationship,
            ENTITY_TYPES.PROPERTY: self._add_property,
            ENTITY_TYPES.OPERATION: self._add_operation
        }

        self._modify_entity_mapper = {
            ENTITY_TYPES.OPERATION: self._modify_operation,
            ENTITY_TYPES.PROPERTY: self._modify_property
        }

        self._remove_entity_mapper = {
            ENTITY_TYPES.NODE: self._remove_node,
            ENTITY_TYPES.RELATIONSHIP: self._remove_relationship,
            ENTITY_TYPES.OPERATION: self._remove_operation,
            ENTITY_TYPES.PROPERTY: self._remove_property
        }

    def handle(self, dep_update):
        """handles updating new and extended nodes onto the storage.

        :param dep_update:
        :return: a list of all of the nodes
        (including the non add_node.modification nodes)
        """
        current_nodes = self.sm.get_nodes(
                filters={'deployment_id': dep_update.deployment_id}).items
        nodes_dict = {node.id: node.to_dict() for node in current_nodes}

        # Iterate over the steps of the deployment update and handle each
        # step according to its operation, passing the deployment update
        # object, step entity type, entity id and a dict of updated nodes.
        # Each handler updated the dict of updated nodes, which enables
        # accumulating changes.
        for step in dep_update.steps:
            if step.entity_type in self._supported_entity_types:
                entity_updater = self.entities_update_mapper[step.operation]
                entity_context = get_entity_context(dep_update.blueprint,
                                                    dep_update.deployment_id,
                                                    step.entity_type,
                                                    step.entity_id)
                entity_id = entity_updater(entity_context, nodes_dict)

                self.modified_entities[step.entity_type].append(entity_id)

        return self.modified_entities, nodes_dict.values()

    def _add_entity(self, ctx, current_nodes):
        """ handles adding an entity

        :param ctx:
        :return: the entity id and the node which contains the added entity
        """
        add_entity_handler = self._add_entity_mapper[ctx.entity_type]

        entity_id = add_entity_handler(ctx, current_nodes)

        return entity_id

    def _add_node(self, ctx, current_nodes):
        """ handles adding a node

        :param ctx:
        :return: the new node
        """

        get_blueprints_manager()._create_deployment_nodes(
                deployment_id=ctx.deployment_id,
                blueprint_id='N/A',
                plan=ctx.plan,
                node_ids=ctx.raw_node_id
        )

        current_nodes[ctx.raw_node_id] = \
            ctx.storage_node.to_dict()
        # node_handler.raw_node

        # Update new node relationships target nodes. Since any relationship
        # with target interface requires the target node to hold a plugin
        # which supports the operation, we should update the mapping for
        # this plugin under the target node.
        target_ids = [r['target_id']
                      for r in ctx.raw_node.get('relationships', [])]

        for node_id in target_ids:
            self.sm.update_node(
                    deployment_id=ctx.deployment_id,
                    node_id=node_id,
                    changes={
                        'plugins':
                            utils.get_raw_node(ctx.plan,
                                               node_id)['plugins']
                    })

            current_nodes[node_id] = \
                self.sm.get_node(ctx.deployment_id, node_id).to_dict()

        return ctx.raw_node_id

    def _add_relationship(self, ctx, current_nodes):
        """Handles adding a relationship

        :param ctx:
        :return: the add_node.modification node
        """
        # Update source relationships and plugins
        source_changes = {
            'relationships': ctx.raw_node['relationships'],
            'plugins': ctx.raw_node['plugins']
        }
        self.sm.update_node(deployment_id=ctx.deployment_id,
                            node_id=ctx.raw_node_id,
                            changes=source_changes)
        source_node = ctx.storage_node
        current_nodes[source_node.id] = source_node.to_dict()

        # Update target plugins
        target_changes = {'plugins': ctx.raw_target_node['plugins']}
        self.sm.update_node(deployment_id=ctx.deployment_id,
                            node_id=ctx.raw_target_node['id'],
                            changes=target_changes)
        current_nodes[ctx.storage_target_node.id] = \
            ctx.storage_target_node.to_dict()

        return ctx.raw_node_id, ctx.raw_target_node['id']

    def _add_property(self, ctx, current_nodes):
        # since the add property basically sets the the value of the property
        # to the new value, it's the same as modifying the same property.
        return self._modify_property(ctx, current_nodes)

    @staticmethod
    def _choose_and_execute_operation_handler(ctx,
                                              current_nodes,
                                              relationship_executor,
                                              node_executor):

        if ctx.entity_id.split(':')[2] == 'relationships':
            modifier = relationship_executor
        else:
            # the operation host could be either relationship interfaces
            # or node interfaces.
            modifier = node_executor

        return modifier(ctx, current_nodes)

    def _add_operation(self, ctx, current_nodes):
        return self._choose_and_execute_operation_handler(
                ctx,
                current_nodes,
                self._add_relationship_operation,
                self._add_node_operation)

    def _add_node_operation(self, ctx, current_nodes):
        # since the add_node_operation basically sets the the value of the
        # property to the new value, it's the same as modifying the same
        # operation.
        return self._modify_node_operation(ctx, current_nodes)

    def _add_relationship_operation(self, ctx, current_nodes):
        # since the add_relationship_operation basically sets the the value of
        # the property to the new value, it's the same as modifying the same
        # operation.
        return self._modify_relationship_operation(ctx, current_nodes)

    def _remove_entity(self, ctx, current_nodes):
        """Handles removing an entity

        :param ctx:
        :return: entity id and it's add_node.modification node
        """
        remove_entity_handler = self._remove_entity_mapper[ctx.entity_type]
        entity_id = remove_entity_handler(ctx, current_nodes)

        return entity_id

    @staticmethod
    def _remove_node(ctx, current_nodes):
        """Handles removing a node

        :param ctx:
        :return: the removed node
        """
        del(current_nodes[ctx.storage_node.id])
        return ctx.storage_node.id

    @staticmethod
    def _remove_relationship(ctx, current_nodes):
        """Handles removing a relationship

        :return: the add_node.modification node
        """
        current_node = current_nodes[ctx.raw_node_id]
        current_node[ctx.RELATIONSHIPS].remove(ctx.storage_entity_value)
        return ctx.raw_node_id, ctx.raw_target_node['id']

    def _remove_operation(self, ctx, current_nodes):
        return self._choose_and_execute_operation_handler(
                ctx,
                current_nodes,
                self._remove_relationship_operation,
                self._remove_node_operation)

    @staticmethod
    def _remove_node_operation(ctx, current_nodes):
        current_node = current_nodes[ctx.raw_node_id]
        del(current_node[ctx.OPERATIONS][ctx.operation_id])

        return ctx.entity_id

    @staticmethod
    def _remove_relationship_operation(ctx, current_nodes):
        current_node = current_nodes[ctx.raw_node_id]
        modified_relationship = \
            current_node[ctx.RELATIONSHIPS][ctx.relationship_index]
        del(modified_relationship[ctx.operations_key][ctx.operation_id])

        return ctx.entity_id

    @staticmethod
    def _remove_property(ctx, current_nodes):
        node_id = ctx.raw_node_id
        del(current_nodes[node_id][ctx.PROPERTIES][ctx.property_id])

        return ctx.entity_id

    def _modify_entity(self, ctx, current_nodes):
        """ handles adding an entity

        :param ctx:
        :return: the entity id and the node which contains the added entity
        """
        add_entity_handler = self._modify_entity_mapper[ctx.entity_type]
        entity_id = add_entity_handler(ctx, current_nodes)

        return entity_id

    def _modify_operation(self, ctx, current_nodes):
        return self._choose_and_execute_operation_handler(
                ctx,
                current_nodes,
                self._modify_relationship_operation,
                self._modify_node_operation)

    def _modify_node_operation(self, ctx, current_nodes):
        new_operation = utils.create_dict(ctx.modification_breadcrumbs,
                                          ctx.raw_entity_value)

        changes = {
            ctx.OPERATIONS: {ctx.operation_id: new_operation},
            ctx.PLUGINS: ctx.raw_node[ctx.PLUGINS]
        }
        self.sm.update_node(deployment_id=ctx.deployment_id,
                            node_id=ctx.raw_node_id,
                            changes=changes)
        current_node = current_nodes[ctx.raw_node_id]
        if ctx.modification_breadcrumbs:
            operation_to_update = utils.traverse_object(
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

    def _modify_relationship_operation(self, ctx, current_nodes):
        current_node = current_nodes[ctx.raw_node_id]
        relationships = current_node[ctx.RELATIONSHIPS]
        operations = relationships[ctx.relationship_index][ctx.operations_key]

        if ctx.modification_breadcrumbs:
            operation_to_update = \
                utils.traverse_object(operations[ctx.operation_id],
                                      ctx.modification_breadcrumbs[:-1])
            operation_to_update[ctx.modification_breadcrumbs[-1]] = \
                ctx.raw_entity_value
        else:
            operations[ctx.operation_id] = ctx.raw_entity_value

        current_node[ctx.PLUGINS] = ctx.raw_node[ctx.PLUGINS]

        changes = {
            ctx.RELATIONSHIPS: relationships,
            ctx.PLUGINS: ctx.raw_node[ctx.PLUGINS]
        }

        self.sm.update_node(deployment_id=ctx.deployment_id,
                            node_id=ctx.raw_node_id,
                            changes=changes)

        return ctx.entity_id

    def _modify_property(self, ctx, current_nodes):
        changes = {
            ctx.PROPERTIES: {
                ctx.property_id:
                    utils.create_dict(ctx.modification_breadcrumbs,
                                      ctx.raw_entity_value)
            }
        }

        self.sm.update_node(deployment_id=ctx.deployment_id,
                            node_id=ctx.raw_node_id,
                            changes=changes)

        properties = current_nodes[ctx.raw_node_id][ctx.PROPERTIES]

        if ctx.modification_breadcrumbs:
            property_to_update = \
                utils.traverse_object(properties[ctx.property_id],
                                      ctx.modification_breadcrumbs[:-1])
            property_to_update[ctx.modification_breadcrumbs[-1]] = \
                ctx.raw_entity_value
        else:
            properties[ctx.property_id] = ctx.raw_entity_value

        return ctx.entity_id

    def finalize(self, dep_update):

        """update any removed entity from nodes

        :param dep_update: the deployment update object itself.
        :return:
        """
        removed_and_related = dep_update.deployment_update_node_instances[
            NODE_MOD_TYPES.REMOVED_AND_RELATED]
        removed_node_instances = \
            removed_and_related.get(NODE_MOD_TYPES.AFFECTED, [])

        removed_node_ids = utils.extract_ids(removed_node_instances, 'node_id')

        # Since not all changes are caught on the node instances (actually only
        # the removing/adding of relationships and nodes) we need to apply all
        # of the changes, thus screening all of the nodes except the ones
        # deleted is a valid solution.
        modified_nodes = [n for n in dep_update.deployment_update_nodes
                          if n['id'] not in removed_node_ids]

        for modified_node in modified_nodes:
            # Since there is no good way deleting a specific value from
            # elasticsearch, we first remove it, and than re-enter it.
            self.sm.delete_node(dep_update.deployment_id, modified_node['id'])
            node = manager_rest.models.DeploymentNode(**modified_node)
            self.sm.put_node(node)

        for removed_node_instance in removed_node_instances:
            self.sm.delete_node(dep_update.deployment_id,
                                removed_node_instance['node_id'])


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
        instances = \
            {k: {} for k, _ in self._handlers_mapper.iteritems()}

        for change_type, handler in self._handlers_mapper.iteritems():
            if updated_instances[change_type]:
                instances[change_type] = \
                    handler(updated_instances[change_type], dep_update)

        return instances

    def _handle_adding_node_instance(self, raw_instances, dep_update):
        """Handles adding a node instance

        :param raw_instances:
        :param dep_update:
        :return: the added and related node instances
        """
        added_instances = []
        add_related_instances = []

        for raw_node_instance in raw_instances:
            if raw_node_instance.get('modification') == 'added':
                changes = {
                    'deployment_id': dep_update.deployment_id,
                    'version': None,
                    'state': None,
                    'runtime_properties': {}
                }
                raw_node_instance.update(changes)
                added_instances.append(raw_node_instance)
            else:
                add_related_instances.append(raw_node_instance)
                self._update_node_instance(raw_node_instance)

        get_blueprints_manager()._create_deployment_node_instances(
                dep_update.deployment_id,
                added_instances
        )

        return {
            NODE_MOD_TYPES.AFFECTED: added_instances,
            NODE_MOD_TYPES.RELATED: add_related_instances
        }

    @staticmethod
    def _handle_removing_node_instance(instances, *_):
        """Handles removing a node instance

        :param raw_instances:
        :return: the removed and related node instances
        """
        removed_raw_instances = []
        remove_related_raw_instances = []

        for raw_node_instance in instances:
            node_instance = \
                manager_rest.models.DeploymentNodeInstance(**raw_node_instance)
            if raw_node_instance.get('modification') == 'removed':
                removed_raw_instances.append(node_instance)
            else:
                remove_related_raw_instances.append(node_instance)

        return {
            NODE_MOD_TYPES.AFFECTED: removed_raw_instances,
            NODE_MOD_TYPES.RELATED: remove_related_raw_instances
        }

    def _handle_adding_relationship_instance(self, instances, *_):
        """Handles adding a relationship to a node instance

        :param raw_instances:
        :return: the extended and related node instances
        """
        modified_raw_instances = []
        modify_related_raw_instances = []

        for raw_node_instance in instances:
            if raw_node_instance.get('modification') == 'extended':

                # adding new relationships to the current relationships
                modified_raw_instances.append(raw_node_instance)
                node_instance = manager_rest.models.DeploymentNodeInstance(
                            **raw_node_instance)
                self._update_node_instance(node_instance.to_dict())
            else:
                modify_related_raw_instances.append(raw_node_instance)

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

        for raw_node_instance in instances:
            if raw_node_instance.get('modification') == 'reduced':
                modified_node = \
                    self.sm.get_node_instance(raw_node_instance['id']) \
                        .to_dict()
                # changing the new state of relationships on the instance
                # to not include the removed relationship
                target_ids = [rel['target_id']
                              for rel in raw_node_instance['relationships']]
                relationships = [rel for rel in modified_node['relationships']
                                 if rel['target_id'] not in target_ids]
                modified_node['relationships'] = relationships

                modified_raw_instances.append(modified_node)
            else:
                modify_related_raw_instances.append(raw_node_instance)

        return {
            NODE_MOD_TYPES.AFFECTED: modified_raw_instances,
            NODE_MOD_TYPES.RELATED: modify_related_raw_instances
        }

    def finalize(self, dep_update):
        """update any removed entity from node instances

        :param dep_update: the deploymend update object
        :return:
        """
        reduced_node_instances = \
            dep_update.deployment_update_node_instances[
                NODE_MOD_TYPES.REDUCED_AND_RELATED].get(
                    NODE_MOD_TYPES.AFFECTED, [])
        removed_node_instances = \
            dep_update.deployment_update_node_instances[
                NODE_MOD_TYPES.REMOVED_AND_RELATED].get(
                    NODE_MOD_TYPES.AFFECTED, [])

        for reduced_node_instance in reduced_node_instances:
            self._update_node_instance(reduced_node_instance,
                                       overwrite_relationships=True)

        for removed_node_instance in removed_node_instances:
            self.sm.delete_node_instance(removed_node_instance['id'])

    def _update_node_instance(self, raw_node_instance,
                              overwrite_relationships=False):
        current = self.sm.get_node_instance(raw_node_instance['id'])
        raw_node_instance['version'] = current.version
        if not overwrite_relationships:
            raw_relationship_target_id = \
                [r['target_id']
                 for r in raw_node_instance.get('relationships', {})]
            if raw_relationship_target_id:
                new_relationships = \
                    [r for r in current.relationships
                     if r['target_id'] not in raw_relationship_target_id]
                raw_node_instance['relationships'].extend(new_relationships)
        self.sm.update_node_instance(
                manager_rest.models.DeploymentNodeInstance(**raw_node_instance)
        )


class DeploymentUpdateDeploymentHandler(UpdateHandler):

    def __init__(self):
        super(DeploymentUpdateDeploymentHandler, self).__init__()
        self.modified_entities = {
            ENTITY_TYPES.WORKFLOW: [],
            ENTITY_TYPES.OUTPUT: [],
            ENTITY_TYPES.DESCRIPTION: []
        }
        self._supported_entity_types = {ENTITY_TYPES.WORKFLOW,
                                        ENTITY_TYPES.OUTPUT,
                                        ENTITY_TYPES.DESCRIPTION}

        self._entities_update_mapper = {
            ACTION_TYPES.ADD: self._add_entity,
            ACTION_TYPES.REMOVE: self._remove_entity,
            ACTION_TYPES.MODIFY: self._modify_entity
        }

        self._add_entity_mapper = {
            ENTITY_TYPES.WORKFLOW: self._add_workflow,
            ENTITY_TYPES.OUTPUT: self._add_output,
            ENTITY_TYPES.DESCRIPTION: self._add_description
        }

        self._modify_update_mapper = {
            ENTITY_TYPES.WORKFLOW: self._modify_workflow,
            ENTITY_TYPES.OUTPUT: self._modify_output,
            ENTITY_TYPES.DESCRIPTION: self._modify_description

        }

        self._remove_remove_mapper = {
            ENTITY_TYPES.WORKFLOW: self._remove_workflow,
            ENTITY_TYPES.OUTPUT: self._remove_output,
            ENTITY_TYPES.DESCRIPTION: self._remove_description
        }

    def handle(self, dep_update):

        deployment = self.sm.get_deployment(dep_update.deployment_id).to_dict()
        for step in dep_update.steps:
            if step.entity_type in self._supported_entity_types:
                entity_updater = self._entities_update_mapper[step.operation]
                entity_context = get_entity_context(dep_update.blueprint,
                                                    dep_update.deployment_id,
                                                    step.entity_type,
                                                    step.entity_id)
                entity_id = entity_updater(entity_context, deployment)

                self.modified_entities[step.entity_type].append(entity_id)

        return self.modified_entities, deployment

    def _add_entity(self, ctx, deployment):
        add_entity_handler = self._add_entity_mapper[ctx.entity_type]
        entity_id = add_entity_handler(ctx, deployment)
        return entity_id

    def _add_workflow(self, ctx, deployment):
        new_workflow = utils.create_dict(ctx.modification_breadcrumbs,
                                         ctx.raw_entity_value)
        changes = {ctx.WORKFLOWS: {ctx.workflow_id: new_workflow}}

        self.sm.update_deployment(ctx.deployment_id, changes)
        deployment[ctx.WORKFLOWS][ctx.workflow_id] = new_workflow

        return ctx.entity_id

    def _add_output(self, ctx, deployment):

        new_output = utils.create_dict(ctx.modification_breadcrumbs,
                                       ctx.raw_entity_value)

        changes = {ctx.OUTPUTS: {ctx.output_id: new_output}}

        self.sm.update_deployment(ctx.deployment_id, changes)
        deployment[ctx.OUTPUTS][ctx.output_id] = ctx.raw_entity_value

        return ctx.entity_id

    def _add_description(self, ctx, deployment):

        new_description = ctx.raw_entity_value
        changes = {ctx.DESCRIPTION: new_description}
        self.sm.update_deployment(ctx.deployment_id, changes)

        deployment[ctx.DESCRIPTION] = new_description

        return ctx.entity_id

    def _remove_entity(self, ctx, deployment):

        remove_entity_handler = self._remove_remove_mapper[ctx.entity_type]

        updated_entity = remove_entity_handler(ctx, deployment)

        return ctx.entity_id, updated_entity

    @staticmethod
    def _remove_workflow(ctx, deployment):
        del(deployment[ctx.WORKFLOWS][ctx.workflow_id])

        return ctx.entity_id

    @staticmethod
    def _remove_output(ctx, deployment):
        del(deployment[ctx.OUTPUTS][ctx.output_id])

        return ctx.entity_id

    @staticmethod
    def _remove_description(ctx, deployment):
        del(deployment[ctx.DESCRIPTION])

        return ctx.entity_id

    def _modify_entity(self, ctx, deployment):
        modify_entity_handler = self._modify_update_mapper[ctx.entity_type]

        entity_id = modify_entity_handler(ctx, deployment)

        return entity_id

    def _modify_workflow(self, ctx, deployment):
        return self._add_workflow(ctx, deployment)

    def _modify_output(self, ctx, deployment):
        return self._add_output(ctx, deployment)

    def _modify_description(self, ctx, deployment):
        return self._add_description(ctx, deployment)

    def finalize(self, dep_update):

        # Clean slate for the update
        self.sm.update_deployment(dep_update.deployment_id,
                                  {'workflows': [],
                                   'outputs': [],
                                   'description': []})

        # updating the changed items
        changes = {
            'workflows': dep_update.deployment_update_deployment['workflows'],
            'outputs': dep_update.deployment_update_deployment.get('outputs'),
            'description':
                dep_update.deployment_update_deployment.get('description')
        }

        self.sm.update_deployment(dep_update.deployment_id, changes)
