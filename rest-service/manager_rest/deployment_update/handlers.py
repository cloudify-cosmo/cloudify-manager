import manager_rest.models
import manager_rest.manager_exceptions
from manager_rest import storage_manager
from manager_rest.blueprints_manager import get_blueprints_manager
from constants import (OPERATIONS,
                       ENTITY_TYPES,
                       CHANGE_TYPE)
import utils


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

    def handle(self, dep_update):
        """handles updating new and extended nodes onto the storage.

        :param dep_update:
        :return: a list of all of the nodes (including the non modified nodes)
        """
        current_nodes = self.sm.get_nodes(
                filters={'deployment_id': dep_update.deployment_id}).items
        nodes_dict = {node.id: node.to_dict() for node in current_nodes}

        entities_update_mapper = {
            OPERATIONS.ADD: self._add_entity,
            OPERATIONS.REMOVE: self._remove_entity,
            OPERATIONS.MODIFY: self._modify_entity
        }

        # Iterate over the steps of the deployment update and handle each
        # step according to its operation, passing the deployment update
        # object, step entity type, entity id and a dict of updated nodes.
        # Each handler updated the dict of updated nodes, which enables
        # accumulating changes.
        for step in dep_update.steps:
            entity_updater = entities_update_mapper[step.operation]
            entity_id = entity_updater(dep_update,
                                       step.entity_type,
                                       step.entity_id,
                                       nodes_dict)

            self.modified_entities[step.entity_type].append(entity_id)

        return self.modified_entities, nodes_dict.values()

    def _add_entity(self, dep_update, entity_type, entity_id, current_nodes):
        """ handles adding an entity

        :param dep_update:
        :param entity_type:
        :param entity_id:
        :return: the entity id and the node which contains the added entity
        """
        add_entity_mapper = {
            ENTITY_TYPES.NODE: self._add_node,
            ENTITY_TYPES.RELATIONSHIP: self._add_relationship,
            ENTITY_TYPES.PROPERTY: self._add_property
        }

        add_entity_handler = add_entity_mapper[entity_type]

        entity_id = add_entity_handler(dep_update, entity_id, current_nodes)

        return entity_id

    def _add_node(self, dep_update, entity_id, current_nodes):
        """ handles adding a node

        :param dep_update:
        :param entity_id:
        :return: the new node
        """
        _, node_id = utils.get_entity_id_list(entity_id)

        get_blueprints_manager()._create_deployment_nodes(
                deployment_id=dep_update.deployment_id,
                blueprint_id='N/A',
                plan=dep_update.blueprint,
                node_ids=node_id
        )

        # Update new node relationships target nodes. Since any relationship
        # with target interface requires the target node to hold a plugin
        # which supports the operation, we should update the mapping for
        # this plugin under the target node.
        raw_node = [n for n in dep_update.blueprint['nodes']
                    if n['id'] == node_id][0]

        target_ids = [r['target_id'] for r in raw_node['relationships']]

        target_raw_nodes = {n['id']: n for n in dep_update.blueprint['nodes']
                            if n['id'] in target_ids}

        for target_id in target_ids:
            self.sm.update_node(deployment_id=dep_update.deployment_id,
                                node_id=target_id,
                                changes={
                                    'plugins':
                                        target_raw_nodes[target_id]['plugins']
                                })

        new_node = self.sm.get_node(dep_update.deployment_id, node_id)
        current_nodes[new_node.id] = new_node.to_dict()

        return node_id

    def _add_relationship(self, dep_update, entity_id, current_nodes):
        """Handles adding a relationship

        :param dep_update:
        :param entity_id:
        :return: the modified node
        """
        source_entity_id, target_entity_id = \
            utils.get_relationship_source_and_target(entity_id)
        _, source_node_id = utils.get_entity_id_list(source_entity_id)
        _, target_node_id = utils.get_entity_id_list(target_entity_id)
        pluralized_entity_type = utils.pluralize(ENTITY_TYPES.NODE)
        raw_nodes = dep_update.blueprint[pluralized_entity_type]
        source_raw_node = \
            [n for n in raw_nodes if n['id'] == source_node_id][0]
        target_raw_node = \
            [n for n in raw_nodes if n['id'] == target_node_id][0]

        # Update source relationships and plugins
        source_plugins = \
            self.sm.get_node(dep_update.deployment_id, source_node_id).plugins
        source_plugins += source_raw_node['plugins']
        source_changes = {
            'relationships': source_raw_node['relationships'],
            'plugins': source_plugins
        }
        self.sm.update_node(deployment_id=dep_update.deployment_id,
                            node_id=source_node_id,
                            changes=source_changes)

        new_source_node = \
            self.sm.get_node(dep_update.deployment_id, source_node_id)
        current_nodes[new_source_node.id] = new_source_node.to_dict()

        # Update target plugins
        target_plugins = \
            self.sm.get_node(dep_update.deployment_id, target_node_id).plugins
        target_plugins += target_raw_node['plugins']

        target_changes = {
            'plugins': target_plugins
        }

        self.sm.update_node(deployment_id=dep_update.deployment_id,
                            node_id=target_node_id,
                            changes=target_changes)

        new_target_node = \
            self.sm.get_node(dep_update.deployment_id, target_node_id)
        current_nodes[new_target_node.id] = new_target_node.to_dict()

        return source_node_id, target_node_id

    def _add_property(self, dep_update, entity_id, current_nodes):
        entity_id_list = utils.get_entity_id_list(entity_id)
        _, node_id, properties_id, property_id = entity_id_list

        new_node = [n for n in dep_update.blueprint['nodes']
                    if n['id'] == node_id][0]

        new_property_value = new_node[properties_id][property_id]

        changes = {
            'properties': {
                property_id: new_property_value
            }
        }

        self.sm.update_node(deployment_id=dep_update.deployment_id,
                            node_id=node_id,
                            changes=changes)

        current_nodes[node_id][properties_id][property_id] = new_property_value

        return entity_id

    def _remove_entity(self,
                       dep_update,
                       entity_type,
                       entity_id,
                       current_nodes):
        """Handles removing an entity

        :param dep_update:
        :param entity_type:
        :param entity_id:
        :return: entity id and it's modified node
        """
        remove_entity_mapper = {
            ENTITY_TYPES.NODE: self._remove_node,
            ENTITY_TYPES.RELATIONSHIP: self._remove_relationship,
            ENTITY_TYPES.PROPERTY: self._remove_property
        }

        remove_entity_handler = remove_entity_mapper[entity_type]
        entity_id = remove_entity_handler(dep_update, entity_id, current_nodes)

        return entity_id

    @staticmethod
    def _remove_node(dep_update, entity_id, current_nodes):
        """Handles removing a node

        :param dep_update:
        :param entity_id:
        :return: the removed node
        """
        _, node_id = utils.get_entity_id_list(entity_id)
        del(current_nodes[node_id])
        return node_id

    @staticmethod
    def _remove_relationship(dep_update, entity_id, current_nodes):
        """Handles removing a relationship

        :param dep_update:
        :param entity_id:
        :return: the modified node
        """
        source_entity_id, target_entity_id = \
            utils.get_relationship_source_and_target(entity_id)
        _, source_node_id = utils.get_entity_id_list(source_entity_id)
        _, target_node_id = utils.get_entity_id_list(target_entity_id)

        node = current_nodes[source_node_id]

        modified_relationship_id = [r for r in node['relationships']
                                    if r['target_id'] == target_node_id][0]

        node['relationships'].remove(modified_relationship_id)

        return source_node_id, target_node_id

    @staticmethod
    def _remove_property(dep_update, entity_id, current_nodes):
        entity_id_list = utils.get_entity_id_list(entity_id)
        _, node_id, properties_id, property_id = entity_id_list

        del(current_nodes[node_id][properties_id][property_id])

        return entity_id

    def _modify_entity(self,
                       dep_update,
                       entity_type,
                       entity_id,
                       current_nodes):
        modify_entity_mapper = {
            ENTITY_TYPES.PROPERTY: self._modify_property
        }

        add_entity_handler = modify_entity_mapper[entity_type]

        entity_id = add_entity_handler(dep_update, entity_id, current_nodes)

        return entity_id

    def _modify_property(self, dep_update, entity_id, current_nodes):
        return self._add_property(dep_update, entity_id, current_nodes)

    def finalize(self, dep_update):
        """update any removed entity from nodes

        :param dep_update: the deployment update object itself.
        :param deployment_update_nodes:
        :param deployment_update_node_instances:
        :return:
        """
        deleted_node_instances = \
            dep_update.deployment_update_node_instances[
                CHANGE_TYPE.REMOVED_AND_RELATED].get(CHANGE_TYPE.AFFECTED, [])

        deleted_node_ids = utils.extract_ids(deleted_node_instances, 'node_id')

        modified_nodes = [n for n in dep_update.deployment_update_nodes
                          if n['id'] not in deleted_node_ids]

        for raw_node in modified_nodes:
            # Since there is no good way deleting a specific value from
            # elasticsearch, we first remove it, and than re-enter it.
            self.sm.delete_node(dep_update.deployment_id, raw_node['id'])
            node = manager_rest.models.DeploymentNode(**raw_node)
            self.sm.put_node(node)

        for deleted_node_instance in deleted_node_instances:
            self.sm.delete_node(dep_update.deployment_id,
                                deleted_node_instance['node_id'])


class DeploymentUpdateNodeInstanceHandler(UpdateHandler):

    def __init__(self):
        super(DeploymentUpdateNodeInstanceHandler, self).__init__()

    def handle(self, dep_update, updated_instances):
        """Handles updating node instances according to the updated_instances

        :param dep_update:
        :param updated_instances:
        :return: dictionary of modified node instances with key as modification
        type
        """
        handlers_mapper = {
            CHANGE_TYPE.ADDED_AND_RELATED:
                self._handle_adding_node_instance,
            CHANGE_TYPE.EXTENDED_AND_RELATED:
                self._handle_adding_relationship_instance,
            CHANGE_TYPE.REDUCED_AND_RELATED:
                self._handle_removing_relationship_instance,
            CHANGE_TYPE.REMOVED_AND_RELATED:
                self._handle_removing_node_instance
        }

        instances = \
            {k: {} for k, _ in handlers_mapper.iteritems()}

        for change_type, handler in handlers_mapper.iteritems():
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
            CHANGE_TYPE.AFFECTED: added_instances,
            CHANGE_TYPE.RELATED: add_related_instances
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
            CHANGE_TYPE.AFFECTED: removed_raw_instances,
            CHANGE_TYPE.RELATED: remove_related_raw_instances
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
                CHANGE_TYPE.AFFECTED: modified_raw_instances,
                CHANGE_TYPE.RELATED: modify_related_raw_instances
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
            CHANGE_TYPE.AFFECTED: modified_raw_instances,
            CHANGE_TYPE.RELATED: modify_related_raw_instances
        }

    def finalize(self, dep_update):
        """update any removed entity from node instances

        :param dep_update: the deploymend update object
        :return:
        """
        reduced_node_instances = \
            dep_update.deployment_update_node_instances[
                CHANGE_TYPE.REDUCED_AND_RELATED].get(
                    CHANGE_TYPE.AFFECTED, [])
        removed_node_instances = \
            dep_update.deployment_update_node_instances[
                CHANGE_TYPE.REMOVED_AND_RELATED].get(
                    CHANGE_TYPE.AFFECTED, [])

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
