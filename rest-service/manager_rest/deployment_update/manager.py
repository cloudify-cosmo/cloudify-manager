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

from manager_rest import models, storage_manager
from manager_rest.blueprints_manager import tasks, BlueprintsManager
import manager_rest.manager_exceptions
import manager_rest.workflow_client as wf_client

from dsl_parser import constants
from handlers import (DeploymentUpdateNodeHandler,
                      DeploymentUpdateNodeInstanceHandler)
from validator import StepValidator
from utils import extract_ids
from constants import STATE, CHANGE_TYPE


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
        dep_update.state = STATE.COMMITTING
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
                 if u.state != STATE.COMMITTED]), None)

        if active_update:
            raise manager_rest.manager_exceptions.ConflictError(
                'deployment update {0} is not committed yet'
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

        added_instances = node_instances[CHANGE_TYPE.ADDED_AND_RELATED]
        extended_instances = node_instances[CHANGE_TYPE.EXTENDED_AND_RELATED]
        reduced_instances = node_instances[CHANGE_TYPE.REDUCED_AND_RELATED]
        removed_instances = node_instances[CHANGE_TYPE.REMOVED_AND_RELATED]

        instance_ids = {
            # needed in order to finalize the commit
            'update_id': dep_update.id,

            # For any added node instance
            'added_instance_ids':
                extract_ids(added_instances.get(CHANGE_TYPE.AFFECTED)),
            'added_target_instances_ids':
                extract_ids(added_instances.get(CHANGE_TYPE.RELATED)),

            # encapsulated all the change entity_ids (in a dictionary with
            # 'node' and 'relationship' keys.
            'modified_entity_ids': modified_entity_ids,

            # Any nodes which were extended (positive modification)
            'extended_instance_ids':
                extract_ids(extended_instances.get(CHANGE_TYPE.AFFECTED)),
            'extend_target_instance_ids':
                extract_ids(extended_instances.get(CHANGE_TYPE.RELATED)),

            # Any nodes which were reduced (negative modification)
            'reduced_instance_ids':
                extract_ids(reduced_instances.get(CHANGE_TYPE.AFFECTED)),
            'reduce_target_instance_ids':
                extract_ids(reduced_instances.get(CHANGE_TYPE.RELATED)),

            # Any nodes which were removed as a whole
            'removed_instance_ids':
                extract_ids(removed_instances.get(CHANGE_TYPE.AFFECTED)),
            'remove_target_instance_ids':
                extract_ids(removed_instances.get(CHANGE_TYPE.RELATED))
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

        self._node_instance_handler.finalize(dep_update)

        self._node_handler.finalize(dep_update)

        # mark deployment update as committed
        dep_update.state = STATE.COMMITTED
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
            raise manager_rest.manager_exceptions.NonexistentWorkflowError(
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
