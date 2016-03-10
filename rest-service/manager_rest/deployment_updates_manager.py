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


class DeploymentUpdateManager(object):

    def __init__(self):
        self.sm = storage_manager.get_storage_manager()
        self.workflow_client = wf_client.get_workflow_client()

    def get_deployment_update(self, deployment_update_id, include=None):
        return self.sm.get_deployment_update(deployment_update_id,
                                             include=include)

    def deployment_updates_list(self, include=None, filters=None,
                                pagination=None, sort=None):
        return self.sm.deployment_updates_list(include=include,
                                               filters=filters,
                                               pagination=pagination,
                                               sort=sort)

    def stage_deployment_update(self, deployment_id, staged_blueprint):

        self._validate_no_active_updates_per_deployment(deployment_id)

        deployment_update = models.DeploymentUpdate(deployment_id,
                                                    staged_blueprint)
        self.sm.put_deployment_update(deployment_update)
        return deployment_update

    def create_deployment_update_step(self, deployment_update_id,
                                      operation, entity_type, entity_id):
        step = models.DeploymentUpdateStep(operation,
                                           entity_type,
                                           entity_id)
        dep_update = self.sm.get_deployment_update(deployment_update_id)

        self._validate_entity_id(dep_update.blueprint,
                                 entity_type,
                                 entity_id)

        self.sm.put_deployment_update_step(deployment_update_id, step)
        return step

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

    @staticmethod
    def _validate_entity_id(blueprint, entity_type, entity_id):
        """
        validate an entity id of provided type exists in provided blueprint.
        raises error if id doesn't exist
        :param blueprint: a blueprint (plan)
        :param entity_type: singular entity type name, e.g. 'node'
        :param entity_id: id of the entity, e.g. 'node1'
        """
        entity_type_plural = _pluralize(entity_type)
        entity_ids = [e['id'] for e in blueprint[entity_type_plural]]
        if entity_id not in entity_ids:
            raise manager_exceptions.UnknownModificationStageError(
                "entity id {} doesn't exist".format(entity_id))

    @staticmethod
    def _process_deployment_update_step(deployment_id, step, blueprint):
        if step.operation == 'add' and step.entity_type == 'node':
            get_blueprints_manager()\
                ._create_deployment_nodes(deployment_id=deployment_id,
                                          blueprint_id='N/A',
                                          plan=blueprint,
                                          node_ids=step.entity_id)

    def commit_deployment_update(self, deployment_update_id):
        deployment_update = self.sm.get_deployment_update(deployment_update_id)

        # mark deployment update as committing
        deployment_update.state = models.DeploymentUpdate.COMMITTING
        self.sm.update_deployment_update(deployment_update)

        deployment_id = deployment_update.deployment_id
        blueprint = deployment_update.blueprint

        deployment_id_filter = {'deployment_id': deployment_id}

        node_instances = [instance.to_dict() for instance
                          in self.sm.get_node_instances(
                          filters=deployment_id_filter).items]

        for step in deployment_update.steps:
            self._process_deployment_update_step(deployment_id,
                                                 step,
                                                 blueprint)
        nodes = [node.to_dict() for node in self.sm.get_nodes(
            filters=deployment_id_filter).items]

        # project changes in deployment
        changes = tasks.modify_deployment(
            nodes=nodes,
            previous_node_instances=node_instances,
            modified_nodes={})
        added_raw_instances = []
        related_raw_instances = []

        # act on changes, which are either new instances or new relationships
        for node_instance in changes['added_and_related']:
            if node_instance.get('modification') == 'added':
                added_raw_instances.append(node_instance)
            else:
                related_raw_instances.append(node_instance)
                current = self.sm.get_node_instance(node_instance['id'])
                new_relationships = current.relationships
                new_relationships += node_instance['relationships']
                self.sm.update_node_instance(models.DeploymentNodeInstance(
                    id=node_instance['id'],
                    relationships=new_relationships,
                    version=current.version,
                    node_id=None,
                    host_id=None,
                    deployment_id=None,
                    state=None,
                    runtime_properties=None))

        # create added instances
        get_blueprints_manager().\
            _create_deployment_node_instances(deployment_id,
                                              added_raw_instances)

        # execute update workflow using added and related instances
        added_instance_ids = \
            [instance['id'] for instance in added_raw_instances]
        related_instance_ids = \
            [instance['id'] for instance in related_raw_instances]
        self.execute_workflow(deployment_id=deployment_id,
                              workflow_id='update',
                              parameters={
                                  'added_instance_ids': added_instance_ids,
                                  'related_instance_ids': related_instance_ids
                              })

        # mark deployment update as committed
        deployment_update.state = models.DeploymentUpdate.COMMITTED
        self.sm.update_deployment_update(deployment_update)

        return models.DeploymentUpdate(deployment_id, blueprint)

    def execute_workflow(self, deployment_id, workflow_id,
                         parameters=None,
                         allow_custom_parameters=False, force=False):
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
    return '{}s'.format(input)
