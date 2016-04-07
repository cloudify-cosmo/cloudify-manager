########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.
import copy
import uuid

from datetime import datetime
from flask import current_app

from manager_rest import storage_manager
from manager_rest import models

from manager_rest.blueprints_manager import tasks, BlueprintsManager
from manager_rest.blueprints_manager import get_blueprints_manager
import manager_exceptions
import manager_rest.workflow_client as wf_client

from dsl_parser import constants

RELATIONSHIP_TYPE = 'relationship'
NODE_TYPE = 'node'
PROPERTY_TYPE = 'property'

RELATIONSHIP_SEPARATOR = '|'
SUBSECTION_SEPARATOR = ':'


class UpdateHandler(object):
    def __init__(self):
        self.sm = storage_manager.get_storage_manager()


class DeploymentUpdateNodeHandler(UpdateHandler):

    def __init__(self):
        super(DeploymentUpdateNodeHandler, self).__init__()
        self.modified_entities = ModifiedEntities()

    def handle(self, dep_update):
        current_nodes = self.sm.get_nodes(
                filters={'deployment_id': dep_update.deployment_id}).items
        nodes = {node.id: node.to_dict() for node in current_nodes}

        entities_update_mapper = {
            'add': self._add_entity,
            'remove': self._remove_entity,
            'modify': self._modify_entity
        }

        for step in dep_update.steps:
            entity_updater = entities_update_mapper[step.operation]
            entity_id, affected_node = entity_updater(dep_update,
                                                      step.entity_type,
                                                      step.entity_id)

            self.modified_entities[step.entity_type].append(entity_id)

            if step.entity_type == 'node':
                if step.operation == 'remove':
                    del(nodes[affected_node['id']])
                else:
                    nodes[affected_node['id']] = affected_node
            else:
                # The changes should focus on the step.entity_type. This
                # enables accumulating changes.
                entity_key = _pluralize(step.entity_type)
                nodes[affected_node['id']][entity_key] = \
                    affected_node[entity_key]

        return self.modified_entities, nodes.values()

    def _add_entity(self, dep_update, entity_type, entity_id):
        """ handles adding an entity

        :param dep_update:
        :param entity_type:
        :param entity_id:
        :return: the entity id and the node which contains the added entity
        """
        add_entity_mapper = {
            NODE_TYPE: self._add_node,
            RELATIONSHIP_TYPE: self._add_relationship,
            PROPERTY_TYPE: self._add_property
        }

        add_entity_handler = add_entity_mapper[entity_type]

        updated_node = add_entity_handler(dep_update, entity_id)

        return entity_id, updated_node.to_dict()

    def _add_node(self, dep_update, entity_id):
        """ handles adding a node

        :param dep_update:
        :param entity_id:
        :return: the new node
        """
        get_blueprints_manager()._create_deployment_nodes(
                deployment_id=dep_update.deployment_id,
                blueprint_id='N/A',
                plan=dep_update.blueprint,
                node_ids=entity_id
        )

        # Update new node relationships target nodes
        raw_node = [n for n in dep_update.blueprint['nodes']
                    if n['id'] == entity_id][0]

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

        return self.sm.get_node(dep_update.deployment_id, entity_id)

    def _add_relationship(self, dep_update, entity_id):
        """Handles adding a relationship

        :param dep_update:
        :param entity_id:
        :return: the modified node
        """
        source_node_id, target_node_id = \
            entity_id.split(RELATIONSHIP_SEPARATOR)
        pluralized_entity_type = _pluralize(NODE_TYPE)
        raw_nodes = dep_update.blueprint[pluralized_entity_type]
        source_raw_node = \
            [n for n in raw_nodes if n['id'] == source_node_id][0]
        target_raw_node = \
            [n for n in raw_nodes if n['id'] == target_node_id][0]

        # This currently assures that only new plugins could be inserted,
        # no new implementation of an old plugin is currently allowed

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

        return self.sm.get_node(dep_update.deployment_id, source_node_id)

    def _add_property(self, dep_update, entity_id):
        node_id, property_name = entity_id.split(SUBSECTION_SEPARATOR)

        new_node = [n for n in dep_update.blueprint['nodes']
                    if n['id'] == node_id][0]

        changes = {
            'properties': {
                property_name: new_node['properties'][property_name]
            }
        }

        self.sm.update_node(deployment_id=dep_update.deployment_id,
                            node_id=node_id,
                            changes=changes)

        return self.sm.get_node(dep_update.deployment_id, node_id)

    def _remove_entity(self, dep_update, entity_type, entity_id):
        """Handles removing an entity

        :param dep_update:
        :param entity_type:
        :param entity_id:
        :return: entity id and it's modified node
        """
        remove_entity_mapper = {
            NODE_TYPE: self._remove_node,
            RELATIONSHIP_TYPE: self._remove_relationship,
            PROPERTY_TYPE: self._remove_property
        }

        add_entity_handler = remove_entity_mapper[entity_type]

        updated_node = add_entity_handler(dep_update, entity_id)

        return entity_id, updated_node.to_dict()

    def _remove_node(self, dep_update, entity_id):
        """Handles removing a node

        :param dep_update:
        :param entity_id:
        :return: the removed node
        """
        return self.sm.get_node(dep_update.deployment_id, entity_id)

    def _remove_relationship(self, dep_update, entity_id):
        """Handles removing a relationship

        :param dep_update:
        :param entity_id:
        :return: the modified node
        """
        source_node_id, target_node_id = \
            entity_id.split(RELATIONSHIP_SEPARATOR)
        node = self.sm.get_node(dep_update.deployment_id, source_node_id)

        modified_relationship = [r for r in node.relationships
                                 if r['target_id'] == target_node_id][0]

        node.relationships.remove(modified_relationship)

        return node

    def _remove_property(self, dep_update, entity_id):
        node_id, property_name = entity_id.split(SUBSECTION_SEPARATOR)

        node = self.sm.get_node(dep_update.deployment_id, node_id)
        del(node.properties[property_name])

        return node

    def _modify_entity(self, dep_update, entity_type, entity_id):
        modify_entity_mapper = {
            PROPERTY_TYPE: self._modify_property
        }

        add_entity_handler = modify_entity_mapper[entity_type]

        updated_node = add_entity_handler(dep_update, entity_id)

        return entity_id, updated_node.to_dict()

    def _modify_property(self, dep_update, entity_id):
        return self._add_property(dep_update, entity_id)

    def finalize_nodes(self, dep_update):
        """update any removed entity from nodes

        :param dep_update: the deployment update object itself.
        :param deployment_update_nodes:
        :param deployment_update_node_instances:
        :return:
        """

        deleted_node_instances = \
            dep_update.deployment_update_node_instances[
                models.DeploymentUpdate.REMOVED_AND_RELATED].get(
                    models.DeploymentUpdate.AFFECTED, [])

        deleted_node_ids = _extract_ids(deleted_node_instances, 'node_id')

        modified_nodes = [n for n in dep_update.deployment_update_nodes
                          if n['id'] not in deleted_node_ids]

        for raw_node in modified_nodes:
            # Since there is no good way deleting a specific value from
            # elasticsearch, we first remove it, and than re-enter it.
            self.sm.delete_node(dep_update.deployment_id, raw_node['id'])
            node = models.DeploymentNode(**raw_node)
            self.sm.put_node(node)

        for deleted_node_instance in deleted_node_instances:
            self.sm.delete_node(dep_update.deployment_id,
                                deleted_node_instance['node_id'])


class DeploymentUpdateNodeInstanceHandler(UpdateHandler):

    def __init__(self):
        super(DeploymentUpdateNodeInstanceHandler, self).__init__()
        self.modified_entities = {
            NODE_TYPE: [],
            RELATIONSHIP_TYPE: [],
            PROPERTY_TYPE: []
        }

    def handle(self, dep_update, updated_instances):
        """Handles updating node instances according to the updated_instances

        :param dep_update:
        :param updated_instances:
        :return: dictionary of modified node instances with key as modification
        type
        """
        handlers_mapper = {
            models.DeploymentUpdate.ADDED_AND_RELATED:
                self._handle_node_instance_adding,
            models.DeploymentUpdate.EXTENDED_AND_RELATED:
                self._handle_relationship_instance_adding,
            models.DeploymentUpdate.REDUCED_AND_RELATED:
                self._handle_relationship_instance_removing,
            models.DeploymentUpdate.REMOVED_AND_RELATED:
                self._handle_node_instance_removing
        }

        instances = \
            {k: {} for k, _ in handlers_mapper.iteritems()}

        for change_type, handler in handlers_mapper.iteritems():
            if updated_instances[change_type]:
                instances[change_type] = \
                    handler(updated_instances[change_type], dep_update)

        return instances

    def _handle_node_instance_adding(self, raw_instances, dep_update):
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
            models.DeploymentUpdate.AFFECTED: added_instances,
            models.DeploymentUpdate.RELATED: add_related_instances
        }

    def _handle_relationship_instance_adding(self, instances, *_):
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
                node_instance = \
                    models.DeploymentNodeInstance(**raw_node_instance)
                self._update_node_instance(node_instance.to_dict())
            else:
                modify_related_raw_instances.append(raw_node_instance)

        return \
            {
                models.DeploymentUpdate.AFFECTED: modified_raw_instances,
                models.DeploymentUpdate.RELATED: modify_related_raw_instances
            }

    def _handle_property_instance_adding(self, instances, *_):
        pass

    @staticmethod
    def _handle_node_instance_removing(instances, *_):
        """Handles removing a node instance

        :param raw_instances:
        :return: the removed and related node instances
        """
        removed_raw_instanes = []
        remove_related_raw_instances = []

        for raw_node_instance in instances:
            if raw_node_instance.get('modification') == 'removed':
                removed_raw_instanes.append(raw_node_instance)
            else:
                remove_related_raw_instances.append(raw_node_instance)

        return {
            models.DeploymentUpdate.AFFECTED: removed_raw_instanes,
            models.DeploymentUpdate.RELATED: remove_related_raw_instances
        }

    def _handle_relationship_instance_removing(self, instances, *_):
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
            models.DeploymentUpdate.AFFECTED: modified_raw_instances,
            models.DeploymentUpdate.RELATED: modify_related_raw_instances
        }

    def _handle_property_instance_removing(self, instances, *_):
        pass

    def finalize_node_instances(self, dep_update):
        """update any removed entity from node instances

        :param deployment_update_node_instances: the required final for
        reduced node instances, and the removed nodes for any removed node
        :return:
        """

        reduced_node_instances = \
            dep_update.deployment_update_node_instances[
                models.DeploymentUpdate.REDUCED_AND_RELATED].get(
                    models.DeploymentUpdate.AFFECTED, [])
        removed_node_instances = \
            dep_update.deployment_update_node_instances[
                models.DeploymentUpdate.REMOVED_AND_RELATED].get(
                    models.DeploymentUpdate.AFFECTED, [])

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
                models.DeploymentNodeInstance(**raw_node_instance)
        )


class StepValidator(UpdateHandler):

    def validate(self, dep_update, step):
        """
        validate an entity id of provided type exists in provided blueprint.
        raises error if id doesn't exist
        :param blueprint: a blueprint (plan)
        :param entity_type: singular entity type name, e.g.NODE_TYPE
        :param entity_id: id of the entity, e.g. 'node1'
        """

        validation_mapper = {
            NODE_TYPE: self._validate_node_entity_id,
            RELATIONSHIP_TYPE: self._validate_relationship_entity_id,
            PROPERTY_TYPE: self._validate_property_entity_id
        }

        validator = validation_mapper[step.entity_type]

        if validator(dep_update, step):
            return
        else:
            raise manager_exceptions.UnknownModificationStageError(
                    "entity id {} doesn't exist".format(step.entity_id))

    def _validate_relationship_entity_id(self, dep_update, step):
        """ validates relation type entity id

        :param dep_update:
        :param step: deployment update step
        :return:
        """
        if RELATIONSHIP_SEPARATOR not in step.entity_id:
            return False

        source_id, target_id = step.entity_id.split(RELATIONSHIP_SEPARATOR)

        if step.operation == 'remove':
            current_nodes = self.sm.get_nodes().items
            source_node = [n for n in current_nodes if n.id == source_id][0]

            conditions = [n.id for n in current_nodes if n.id == target_id]
            conditions += filter(lambda r: r['target_id'] == target_id,
                                 source_node.relationships)
        else:
            new_nodes = dep_update.blueprint['nodes']

            source_node = [n for n in new_nodes if n['id'] == source_id][0]

            conditions = [n['id'] for n in new_nodes if n['id'] == target_id]
            conditions += filter(lambda r: r['target_id'] == target_id,
                                 source_node['relationships'])

        return any(conditions)

    def _validate_node_entity_id(self, dep_update, step):
        """ validates node type entity id

        :param dep_update:
        :param step: deployment update step
        :return:
        """
        if step.operation == 'remove':
            current_node_instnaces = self.sm.get_node_instances(
                    filters={'deployment_id': dep_update.deployment_id}
            )
            return step.entity_id in \
                [i.node_id for i in current_node_instnaces.items]
        else:
            new_nodes = dep_update.blueprint[_pluralize('node')]
            return step.entity_id in _extract_ids(new_nodes)

    def _validate_property_entity_id(self, dep_update, step):
        node_id, property_id = step.entity_id.split(SUBSECTION_SEPARATOR)
        if step.operation == 'remove':
            node_properties = \
                self.sm.get_node(dep_update.deployment_id, node_id).properties
        else:
            node = [n for n in dep_update.blueprint['nodes']
                    if n['id'] == node_id][0]
            node_properties = node['properties']

        return property_id in node_properties


class DeploymentUpdateManager(object):

    def __init__(self):
        self.sm = storage_manager.get_storage_manager()
        self.workflow_client = wf_client.get_workflow_client()
        self._node_handler = DeploymentUpdateNodeHandler()
        self._node_instance_handler = DeploymentUpdateNodeInstanceHandler()
        self._step_validator = StepValidator()

    def get_deployment_update(self, deployment_update_id):
        """Return the deployment update object

        :param deployment_update_id:
        :return:
        """
        return self.sm.get_deployment_update(deployment_update_id)

    def deployment_updates_list(self, include=None, filters=None,
                                pagination=None, sort=None):
        """Return a list of deployment updates.

        :param include:
        :param filters:
        :param pagination:
        :param sort:
        :return:
        """
        return self.sm.deployment_updates_list(include=include,
                                               filters=filters,
                                               pagination=pagination,
                                               sort=sort)

    def stage_deployment_update(self, deployment_id, staged_blueprint):
        """Stage a deployment update

        :param deployment_id: the deployment id for the update
        :param staged_blueprint: the modified blueprint
        :return:
        """

        self._validate_no_active_updates_per_deployment(deployment_id)

        deployment_update = models.DeploymentUpdate(deployment_id,
                                                    staged_blueprint)
        self.sm.put_deployment_update(deployment_update)
        return deployment_update

    def create_deployment_update_step(self, deployment_update_id,
                                      operation, entity_type, entity_id):
        """Create deployment update step

        :param deployment_update_id:
        :param operation: add/remove/modify
        :param entity_type: add/relationship
        :param entity_id:
        :return:
        """
        step = models.DeploymentUpdateStep(operation,
                                           entity_type,
                                           entity_id)
        dep_update = self.get_deployment_update(deployment_update_id)

        self._step_validator.validate(dep_update, step)

        self.sm.put_deployment_update_step(deployment_update_id, step)
        return step

    def commit_deployment_update(self, deployment_update_id):
        """commit the deployment update steps

        :param deployment_update_id:
        :return:
        """
        dep_update = self.get_deployment_update(deployment_update_id)

        # mark deployment update as committing
        dep_update.state = models.DeploymentUpdate.COMMITTING
        self.sm.update_deployment_update(dep_update)

        # Update the nodes on the storage
        modified_entity_ids, depup_nodes = \
            self._node_handler.handle(dep_update)

        # Extract changes from raw nodes
        node_instance_changes = self._extract_changes(dep_update,
                                                      depup_nodes)

        # Create (and update for adding step type) node instances
        # according to the changes in raw_nodes
        depup_node_instances = \
            self._node_instance_handler.handle(dep_update,
                                               node_instance_changes)

        # Saving the needed changes back to sm for future use
        # (removing entities).
        dep_update.deployment_update_nodes = depup_nodes
        dep_update.deployment_update_node_instances = depup_node_instances
        dep_update.modified_entity_ids = modified_entity_ids.to_dict()
        self.sm.update_deployment_update(dep_update)

        # Execute update workflow using added and related instances
        # This workflow will call a finalize_update, since removing entities
        # should be done after the executions.
        # The raw_node_instances are being used only for their ids, Thus
        # They should really hold the finished version for the node instance.
        self._execute_update_workflow(dep_update,
                                      depup_node_instances,
                                      modified_entity_ids.to_dict())

        return models.DeploymentUpdate(deployment_update_id,
                                       dep_update.blueprint)

    def _validate_no_active_updates_per_deployment(self, deployment_id):
        """
        Validate there are no uncommitted updates for provided deployment.
        raises conflict error if there are.
        :param deployment_id: deployment id
        """
        existing_updates = \
            self.deployment_updates_list(filters={
                'deployment_id': deployment_id
            }).items

        active_update = \
            next(iter(
                [u for u in existing_updates
                 if u.state != models.DeploymentUpdate.COMMITTED]), None)

        if active_update:
            raise manager_exceptions.ConflictError(
                'deployment update {} is not committed yet'
                .format(active_update.id)
            )

    def _extract_changes(self, dep_update, raw_nodes):
        """Extracts the changes between the current node_instances and
        the raw_nodes specified

        :param dep_update:
        :param raw_nodes:
        :return: a dictionary of modification type and node instanced modifed
        """
        deployment_id_filter = \
            {'deployment_id': dep_update.deployment_id}

        # By this point the node_instances aren't updated yet
        raw_node_instances = \
            [instance.to_dict() for instance in
             self.sm.get_node_instances(filters=deployment_id_filter).items]

        # project changes in deployment
        return tasks.modify_deployment(
                nodes=raw_nodes,
                previous_node_instances=raw_node_instances,
                modified_nodes=()
        )

    def _execute_update_workflow(self,
                                 dep_update,
                                 node_instances,
                                 modified_entity_ids):
        """Executed the update workflow

        :param dep_update:
        :param node_instances: a dictionary of modification type and
        modified instances
        :param modified_entity_ids: the entire modified entities list (by id)
        :return:
        """

        added_instances = \
            node_instances[models.DeploymentUpdate.ADDED_AND_RELATED]
        extended_instances = \
            node_instances[models.DeploymentUpdate.EXTENDED_AND_RELATED]
        reduced_instances = \
            node_instances[models.DeploymentUpdate.REDUCED_AND_RELATED]
        removed_instances = \
            node_instances[models.DeploymentUpdate.REMOVED_AND_RELATED]

        instance_ids = {
            # needed in order to finalize the commit
            'update_id': dep_update.id,

            # For any added node instance
            'added_instance_ids':
                _extract_ids(added_instances.get(
                        models.DeploymentUpdate.AFFECTED)),
            'add_related_instance_ids':
                _extract_ids(added_instances.get(
                        models.DeploymentUpdate.RELATED)),

            # encapsulated all the change entity_ids (in a dictionary with
            # 'node' and 'relationship' keys.
            'modified_entity_ids': modified_entity_ids,

            # Any nodes which were extended (positive modification)
            'extended_instance_ids':
                _extract_ids(extended_instances.get(
                        models.DeploymentUpdate.AFFECTED)),
            'extend_related_instance_ids':
                _extract_ids(extended_instances.get(
                        models.DeploymentUpdate.RELATED)),

            # Any nodes which were reduced (negative modification)
            'reduced_instance_ids':
                _extract_ids(reduced_instances.get(
                        models.DeploymentUpdate.AFFECTED)),
            'reduce_related_instance_ids':
                _extract_ids(reduced_instances.get(
                        models.DeploymentUpdate.RELATED)),

            # Any nodes which were removed as a whole
            'removed_instance_ids':
                _extract_ids(removed_instances.get(
                        models.DeploymentUpdate.AFFECTED)),
            'remove_related_instance_ids':
                _extract_ids(removed_instances.get(
                        models.DeploymentUpdate.RELATED))
        }

        return self.execute_workflow(deployment_id=dep_update.deployment_id,
                                     workflow_id='update',
                                     parameters=instance_ids)

    def finalize_commit(self, deployment_update_id):
        """ finalizes the update process by removing any removed
        node/node instances and updating any reduced node

        :param deployment_update_id:
        :return:
        """

        dep_update = self.get_deployment_update(deployment_update_id)

        self._node_instance_handler.finalize_node_instances(dep_update)

        self._node_handler.finalize_nodes(dep_update)

        # mark deployment update as committed
        dep_update.state = models.DeploymentUpdate.COMMITTED
        self.sm.update_deployment_update(dep_update)

        return models.DeploymentUpdate(deployment_update_id,
                                       dep_update.blueprint)

    def execute_workflow(self,
                         deployment_id,
                         workflow_id,
                         parameters=None,
                         allow_custom_parameters=False,
                         force=False):
        """Executes the specified workflow

        :param deployment_id:
        :param workflow_id:
        :param parameters:
        :param allow_custom_parameters:
        :param force:
        :return:
        """
        deployment = self.sm.get_deployment(deployment_id)
        blueprint = self.sm.get_blueprint(deployment.blueprint_id)

        if workflow_id not in deployment.workflows:
            raise manager_exceptions.NonexistentWorkflowError(
                'Workflow {0} does not exist in deployment {1}'.format(
                    workflow_id, deployment_id))
        workflow = deployment.workflows[workflow_id]

        execution_parameters = \
            BlueprintsManager._merge_and_validate_execution_parameters(
                workflow, workflow_id, parameters, allow_custom_parameters)

        execution_id = str(uuid.uuid4())

        new_execution = models.Execution(
            id=execution_id,
            status=models.Execution.PENDING,
            created_at=str(datetime.now()),
            blueprint_id=deployment.blueprint_id,
            workflow_id=workflow_id,
            deployment_id=deployment_id,
            error='',
            parameters=BlueprintsManager._get_only_user_execution_parameters(
                execution_parameters),
            is_system_workflow=False)

        self.sm.put_execution(new_execution.id, new_execution)

        # executing the user workflow
        workflow_plugins = blueprint.plan[
            constants.WORKFLOW_PLUGINS_TO_INSTALL]
        self.workflow_client.execute_workflow(
            workflow_id,
            workflow,
            workflow_plugins=workflow_plugins,
            blueprint_id=deployment.blueprint_id,
            deployment_id=deployment_id,
            execution_id=execution_id,
            execution_parameters=execution_parameters)

        return new_execution


# What we need to access this manager in Flask
def get_deployment_updates_manager():
    """
    Get the current app's deployment updates manager, create if necessary
    """
    manager = current_app.config.get('deployment_updates_manager')
    if not manager:
        current_app.config['deployment_updates_manager'] = \
            DeploymentUpdateManager()
        manager = current_app.config.get('deployment_updates_manager')
    return manager


def _pluralize(input):
    if input[-1] == 'y':
        return '{0}ies'.format(input[:-1])
    else:
        return '{}s'.format(input)


def _extract_ids(node_instances, key='id'):
    if node_instances:
        return [instance[key]
                if isinstance(instance, dict) else getattr(instance, key)
                for instance in node_instances]
    else:
        return []


def get_relationship_source_target(relationship_id):
    return relationship_id.split(RELATIONSHIP_SEPARATOR)


def get_entity_id_list(entity_id):
    return entity_id.split(SUBSECTION_SEPARATOR)


class ModifiedEntities(object):

    entity_types = {NODE_TYPE, RELATIONSHIP_TYPE, PROPERTY_TYPE}

    def __init__(self):
        self.modified_entity_ids = \
            {entity_type: [] for entity_type in self.entity_types}

    def __setitem__(self, entity_type, entity_id):
        if entity_type == RELATIONSHIP_TYPE:
            entity_id = entity_id.split(RELATIONSHIP_SEPARATOR)

        self.modified_entity_ids[entity_type].append(entity_id)

    def __getitem__(self, entity_type):
        return self.modified_entity_ids[entity_type]

    def __iter__(self):
        return iter(self.modified_entity_ids)

    def to_dict(self):

        relationships = {}
        for rel in self.modified_entity_ids[RELATIONSHIP_TYPE]:
            s_id, t_id = rel.split(RELATIONSHIP_SEPARATOR)
            if s_id in relationships:
                relationships[s_id].append(t_id)
            else:
                relationships[s_id] = [t_id]

        modified_entities_to_return = copy.deepcopy(self.modified_entity_ids)
        modified_entities_to_return[RELATIONSHIP_TYPE] = relationships

        return modified_entities_to_return
