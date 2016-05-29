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
from os import path

from flask import current_app

from dsl_parser import constants
from manager_rest.deployment_update import step_extractor
import manager_rest.manager_exceptions
import manager_rest.workflow_client as wf_client

from manager_rest import app_context
from manager_rest import config
from manager_rest import models, storage_manager
from manager_rest.deployment_update.utils import extract_ids
from manager_rest.deployment_update.validator import StepValidator
from manager_rest.blueprints_manager import tasks, BlueprintsManager
from manager_rest.deployment_update.constants import (
    STATES,
    NODE_MOD_TYPES,
    DEFAULT_DEPLOYMENT_UPDATE_WORKFLOW
)
from manager_rest.deployment_update.handlers import (
    DeploymentUpdateNodeHandler,
    DeploymentUpdateNodeInstanceHandler,
    DeploymentUpdateDeploymentHandler
)


class DeploymentUpdateManager(object):

    def __init__(self):
        self.sm = storage_manager.get_storage_manager()
        self.workflow_client = wf_client.get_workflow_client()
        self._node_handler = DeploymentUpdateNodeHandler()
        self._node_instance_handler = DeploymentUpdateNodeInstanceHandler()
        self._deployment_handler = DeploymentUpdateDeploymentHandler()

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

    def stage_deployment_update(self,
                                deployment_id,
                                app_dir,
                                app_blueprint,
                                additional_inputs):
        """Stage a deployment update

        :param app_blueprint:
        :param app_dir:
        :param deployment_id: the deployment id for the update
        :return:
        """

        self._validate_no_active_updates_per_deployment(deployment_id)

        # enables reverting to original blueprint resources
        deployment = self.sm.get_deployment(deployment_id)
        blueprint_id = deployment.blueprint_id

        conflicted_inputs = [i for i in additional_inputs
                             if i in deployment.base_inputs]

        if conflicted_inputs:
            raise manager_rest.manager_exceptions.ConflictError(
                'The following deployment update inputs conflict with '
                'original deployment inputs: {0}'.format(conflicted_inputs)
            )

        # enables reverting to original blueprint resources
        file_server_base_url = \
            '{0}/'.format(config.instance().file_server_base_uri)

        blueprint_resource_dir = path.join(file_server_base_url,
                                           'blueprints',
                                           blueprint_id)

        app_path = path.join(file_server_base_url, app_dir, app_blueprint)

        # parsing the blueprint from here
        plan = tasks.parse_dsl(app_path,
                               resources_base_url=file_server_base_url,
                               additional_resources=[blueprint_resource_dir],
                               **app_context.get_parser_context())
        # Updating the new inputs with the deployment inputs # (overriding old
        # values and adding new ones)
        additional_inputs.update(deployment.base_inputs)

        # applying intrinsic functions
        prepared_plan = tasks.prepare_deployment_plan(plan,
                                                      inputs=additional_inputs)

        deployment_update = models.DeploymentUpdate(deployment_id,
                                                    prepared_plan)
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

    def extract_steps_from_deployment_update(self, deployment_update_id):

        deployment_update = self.get_deployment_update(deployment_update_id)

        steps = step_extractor.extract_steps(deployment_update)
        deployment_update.steps = steps
        self.sm.update_deployment_update(deployment_update)

        # return the deployment update with its new steps from the storage
        return self.get_deployment_update(deployment_update_id)

    def commit_deployment_update(self, deployment_update_id, workflow_id=None):
        """commit the deployment update steps

        :param deployment_update_id:
        :param workflow_id:
        :return:
        """
        dep_update = self.get_deployment_update(deployment_update_id)

        # mark deployment update as committing
        dep_update.state = STATES.COMMITTING
        self.sm.update_deployment_update(dep_update)

        # Handle any deployment related changes. i.e. workflows and deployments
        modified_deployment_entities, raw_updated_deployment = \
            self._deployment_handler.handle(dep_update)

        # Retrieve previous_nodes
        previous_nodes = \
            [node.to_dict() for node in self.sm.get_nodes(
                filters={'deployment_id': dep_update.deployment_id}).items]

        # Update the nodes on the storage
        modified_entity_ids, depup_nodes = \
            self._node_handler.handle(dep_update)

        # Extract changes from raw nodes
        node_instance_changes = self._extract_changes(
            dep_update,
            depup_nodes,
            previous_nodes=previous_nodes)

        # Create (and update for adding step type) node instances
        # according to the changes in raw_nodes
        depup_node_instances = \
            self._node_instance_handler.handle(dep_update,
                                               node_instance_changes)

        # Saving the needed changes back to sm for future use
        # (removing entities).
        dep_update.deployment_update_deployment = raw_updated_deployment
        dep_update.deployment_update_nodes = depup_nodes
        dep_update.deployment_update_node_instances = depup_node_instances
        dep_update.modified_entity_ids = modified_entity_ids.to_dict()
        self.sm.update_deployment_update(dep_update)

        # Execute the default 'update' workflow or a custom workflow using
        # added and related instances. Any workflow executed should call
        # finalize_update, since removing entities should be done after the
        # executions.
        # The raw_node_instances are being used only for their ids, Thus
        # They should really hold the finished version for the node instance.
        self._execute_update_workflow(dep_update,
                                      depup_node_instances,
                                      modified_entity_ids.to_dict(),
                                      workflow_id)

        return self.get_deployment_update(dep_update.id)

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
                 if u.state != STATES.COMMITTED]), None)

        if active_update:
            raise manager_rest.manager_exceptions.ConflictError(
                'deployment update {0} is not committed yet'
                .format(active_update.id)
            )

    def _extract_changes(self, dep_update, raw_nodes, previous_nodes):
        """Extracts the changes between the current node_instances and
        the raw_nodes specified

        :param dep_update:
        :param raw_nodes:
        :return: a dictionary of modification type and node instanced modifed
        """
        deployment_id_filter = \
            {'deployment_id': dep_update.deployment_id}

        # By this point the node_instances aren't updated yet
        previous_node_instances = \
            [instance.to_dict() for instance in
             self.sm.get_node_instances(filters=deployment_id_filter).items]

        # project changes in deployment
        return tasks.modify_deployment(
                nodes=raw_nodes,
                # TODO: fix it
                previous_nodes=previous_nodes,

                previous_node_instances=previous_node_instances,
                modified_nodes=(),
                # TODO: fix it
                scaling_groups={}
        )

    def _execute_update_workflow(self,
                                 dep_update,
                                 node_instances,
                                 modified_entity_ids,
                                 workflow_id=None):
        """Executed the update workflow or a custom workflow

        :param dep_update:
        :param node_instances: a dictionary of modification type and
        add_node.modification instances
        :param modified_entity_ids: the entire add_node.modification entities
        list (by id)
        :return:
        """
        added_instances = node_instances[NODE_MOD_TYPES.ADDED_AND_RELATED]
        extended_instances = \
            node_instances[NODE_MOD_TYPES.EXTENDED_AND_RELATED]
        reduced_instances = node_instances[NODE_MOD_TYPES.REDUCED_AND_RELATED]
        removed_instances = node_instances[NODE_MOD_TYPES.REMOVED_AND_RELATED]

        parameters = {
            # needed in order to finalize the commit
            'update_id': dep_update.id,

            # For any added node instance
            'added_instance_ids':
                extract_ids(added_instances.get(NODE_MOD_TYPES.AFFECTED)),
            'added_target_instances_ids':
                extract_ids(added_instances.get(NODE_MOD_TYPES.RELATED)),

            # encapsulated all the change entity_ids (in a dictionary with
            # 'node' and 'relationship' keys.
            'modified_entity_ids': modified_entity_ids,

            # Any nodes which were extended (positive modification)
            'extended_instance_ids':
                extract_ids(extended_instances.get(NODE_MOD_TYPES.AFFECTED)),
            'extend_target_instance_ids':
                extract_ids(extended_instances.get(NODE_MOD_TYPES.RELATED)),

            # Any nodes which were reduced (negative modification)
            'reduced_instance_ids':
                extract_ids(reduced_instances.get(NODE_MOD_TYPES.AFFECTED)),
            'reduce_target_instance_ids':
                extract_ids(reduced_instances.get(NODE_MOD_TYPES.RELATED)),

            # Any nodes which were removed as a whole
            'removed_instance_ids':
                extract_ids(removed_instances.get(NODE_MOD_TYPES.AFFECTED)),
            'remove_target_instance_ids':
                extract_ids(removed_instances.get(NODE_MOD_TYPES.RELATED))
        }

        return self.execute_workflow(
                deployment_update=dep_update,
                workflow_id=workflow_id or DEFAULT_DEPLOYMENT_UPDATE_WORKFLOW,
                parameters=parameters)

    def finalize_commit(self, deployment_update_id):
        """ finalizes the update process by removing any removed
        node/node instances and updating any reduced node

        :param deployment_update_id:
        :return:
        """

        dep_update = self.get_deployment_update(deployment_update_id)

        # The order of these matter
        for finalize in [self._deployment_handler.finalize,
                         self._node_instance_handler.finalize,
                         self._node_handler.finalize]:
            finalize(dep_update)

        # mark deployment update as committed
        dep_update.state = STATES.COMMITTED
        self.sm.update_deployment_update(dep_update)

        return models.DeploymentUpdate(deployment_update_id,
                                       dep_update.blueprint)

    def execute_workflow(self,
                         deployment_update,
                         workflow_id,
                         parameters=None,
                         allow_custom_parameters=False,
                         force=False):
        """Executes the specified workflow

        :param deployment_update:
        :param workflow_id:
        :param parameters:
        :param allow_custom_parameters:
        :param force:
        :return:
        """
        deployment_id = deployment_update.deployment_id
        deployment = self.sm.get_deployment(deployment_id)
        blueprint_id = deployment.blueprint_id

        if workflow_id not in deployment.workflows:
            raise manager_rest.manager_exceptions.NonexistentWorkflowError(
                'Workflow {0} does not exist in deployment {1}'
                .format(workflow_id, deployment_id))
        workflow = deployment.workflows[workflow_id]

        execution_parameters = \
            BlueprintsManager._merge_and_validate_execution_parameters(
                workflow, workflow_id, parameters, allow_custom_parameters)

        execution_id = str(uuid.uuid4())

        new_execution = models.Execution(
            id=execution_id,
            status=models.Execution.PENDING,
            created_at=str(datetime.now()),
            blueprint_id=blueprint_id,
            workflow_id=workflow_id,
            deployment_id=deployment_id,
            error='',
            parameters=BlueprintsManager._get_only_user_execution_parameters(
                execution_parameters),
            is_system_workflow=False)

        self.sm.put_execution(new_execution.id, new_execution)

        # executing the user workflow
        workflow_plugins = \
            deployment_update.blueprint[constants.WORKFLOW_PLUGINS_TO_INSTALL]
        self.workflow_client.execute_workflow(
            workflow_id,
            workflow,
            workflow_plugins=workflow_plugins,
            blueprint_id=blueprint_id,
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
