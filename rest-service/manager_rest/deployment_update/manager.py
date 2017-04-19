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
import os
import uuid

from flask import current_app

from dsl_parser import constants, tasks
from dsl_parser import exceptions as parser_exceptions

from manager_rest import config
from manager_rest.constants import CURRENT_TENANT_CONFIG
from manager_rest import app_context, manager_exceptions
from manager_rest.storage import get_storage_manager, models
from manager_rest.storage.models_states import ExecutionState
from manager_rest import workflow_executor
from manager_rest import utils
from manager_rest.resource_manager import ResourceManager
from manager_rest.deployment_update import step_extractor
from manager_rest.deployment_update.utils import extract_ids
from manager_rest.deployment_update.validator import StepValidator
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
        self.sm = get_storage_manager()
        self._node_handler = DeploymentUpdateNodeHandler()
        self._node_instance_handler = DeploymentUpdateNodeInstanceHandler()
        self._deployment_handler = DeploymentUpdateDeploymentHandler()
        self._step_validator = StepValidator()

    def get_deployment_update(self, deployment_update_id):
        """Return the deployment update object

        :param deployment_update_id:
        :return:
        """
        return self.sm.get(models.DeploymentUpdate, deployment_update_id)

    def list_deployment_updates(self, include=None, filters=None,
                                pagination=None, sort=None):
        """Return a list of deployment updates.

        :param include:
        :param filters:
        :param pagination:
        :param sort:
        :return:
        """
        return self.sm.list(
            models.DeploymentUpdate,
            include=include,
            filters=filters,
            pagination=pagination,
            sort=sort
        )

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

        # enables reverting to original blueprint resources
        deployment = self.sm.get(models.Deployment, deployment_id)
        blueprint_id = deployment.blueprint_id
        file_server_root = config.instance.file_server_root

        blueprint_resource_dir = os.path.join(
            file_server_root,
            'blueprints',
            current_app.config[CURRENT_TENANT_CONFIG].name,
            blueprint_id)
        # The dsl parser expects a URL
        blueprint_resource_dir_url = 'file:{0}'.format(blueprint_resource_dir)

        app_path = os.path.join(file_server_root, app_dir, app_blueprint)

        # parsing the blueprint from here
        try:
            plan = tasks.parse_dsl(
                app_path,
                resources_base_path=file_server_root,
                additional_resources=[blueprint_resource_dir_url],
                **app_context.get_parser_context())

        except parser_exceptions.DSLParsingException as ex:
            raise manager_exceptions.InvalidBlueprintError(
                'Invalid blueprint - {0}'.format(ex))

        # Updating the new inputs with the deployment inputs
        # (overriding old values and adding new ones)
        inputs = copy.deepcopy(deployment.inputs)
        inputs.update(additional_inputs)

        # applying intrinsic functions
        try:
            prepared_plan = tasks.prepare_deployment_plan(plan, inputs=inputs)
        except parser_exceptions.MissingRequiredInputError, e:
            raise manager_exceptions.MissingRequiredDeploymentInputError(
                str(e))
        except parser_exceptions.UnknownInputError, e:
            raise manager_exceptions.UnknownDeploymentInputError(str(e))

        deployment_update_id = '{0}-{1}'.format(deployment.id, uuid.uuid4())
        deployment_update = models.DeploymentUpdate(
            id=deployment_update_id,
            deployment_plan=prepared_plan,
            created_at=utils.get_formatted_timestamp()
        )
        deployment_update.set_deployment(deployment)
        self.sm.put(deployment_update)
        return deployment_update

    def create_deployment_update_step(self,
                                      deployment_update_id,
                                      action,
                                      entity_type,
                                      entity_id):
        """Create deployment update step

        :param deployment_update_id:
        :param action: add/remove/modify
        :param entity_type: add/relationship
        :param entity_id:
        :return:
        """
        step = models.DeploymentUpdateStep(
            id=str(uuid.uuid4()),
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        deployment_update = self.get_deployment_update(deployment_update_id)
        step.set_deployment_update(deployment_update)
        return self.sm.put(step)

    def extract_steps_from_deployment_update(self, deployment_update):
        supported_steps, unsupported_steps = \
            step_extractor.extract_steps(deployment_update)

        if not unsupported_steps:
            for step in supported_steps:
                self.create_deployment_update_step(
                    deployment_update_id=deployment_update.id,
                    action=step.action,
                    entity_type=step.entity_type,
                    entity_id=step.entity_id,
                )

        # if there are unsupported steps, raise an exception telling the user
        # about these unsupported steps
        else:
            deployment_update.state = STATES.FAILED
            self.sm.update(deployment_update)
            unsupported_entity_ids = [step.entity_id
                                      for step in unsupported_steps]
            raise \
                manager_exceptions.UnsupportedChangeInDeploymentUpdate(
                    'The blueprint you provided for the deployment update '
                    'contains changes currently unsupported by the deployment '
                    'update mechanism.\n'
                    'Unsupported changes: {0}'
                    .format('\n'.join(unsupported_entity_ids)))

    def commit_deployment_update(self,
                                 dep_update,
                                 skip_install=False,
                                 skip_uninstall=False,
                                 workflow_id=None):
        """commit the deployment update steps

        :param dep_update:
        :param skip_install:
        :param skip_uninstall:
        :param workflow_id:
        :return:
        """
        # mark deployment update as committing
        dep_update.state = STATES.UPDATING
        self.sm.update(dep_update)

        # Handle any deployment related changes. i.e. workflows and deployments
        modified_deployment_entities, raw_updated_deployment = \
            self._deployment_handler.handle(dep_update)

        # Retrieve previous_nodes
        previous_nodes = \
            [node.to_dict() for node in self.sm.list(
                models.Node,
                filters={'deployment_id': dep_update.deployment_id})]

        # Update the nodes on the storage
        modified_entity_ids, depup_nodes = \
            self._node_handler.handle(dep_update)

        # Extract changes from raw nodes
        node_instance_changes = self._extract_changes(dep_update,
                                                      depup_nodes,
                                                      previous_nodes)

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
        dep_update.modified_entity_ids = \
            modified_entity_ids.to_dict(include_rel_order=True)
        self.sm.update(dep_update)

        # Execute the default 'update' workflow or a custom workflow using
        # added and related instances. Any workflow executed should call
        # finalize_update, since removing entities should be done after the
        # executions.
        # The raw_node_instances are being used only for their ids, Thus
        # They should really hold the finished version for the node instance.

        execution = self._execute_update_workflow(
            dep_update,
            depup_node_instances,
            modified_entity_ids.to_dict(),
            skip_install=skip_install,
            skip_uninstall=skip_uninstall,
            workflow_id=workflow_id)

        dep_update.execution = execution
        dep_update.state = STATES.EXECUTING_WORKFLOW
        self.sm.update(dep_update)

        return self.get_deployment_update(dep_update.id)

    def validate_no_active_updates_per_deployment(self,
                                                  deployment_id,
                                                  force=False):
        """
        Validate there are no active updates for provided deployment.
        raises conflict error if there are any.
        :param deployment_id: deployment id
        :param force: force
        """
        existing_updates = \
            self.list_deployment_updates(filters={
                'deployment_id': deployment_id
            }).items

        active_updates = [u for u in existing_updates if u.state
                          not in (STATES.SUCCESSFUL, STATES.FAILED)]

        if active_updates:
            if not force:
                raise manager_exceptions.ConflictError(
                    'there are deployment updates still active; '
                    'update IDs: {0}'.format(
                        ', '.join([u.id for u in active_updates])))

            # real active updates are those with
            # an execution in a running status
            real_active_updates = \
                [u for u in active_updates if u.execution_id is not None and
                 self.sm.get(models.Execution, u.execution_id).status not in
                 ExecutionState.END_STATES]

            if real_active_updates:
                raise manager_exceptions.ConflictError(
                    'there are deployment updates still active; the "force" '
                    'flag was used yet these updates have actual executions '
                    'running update IDs: {0}'.format(
                        ', '.join([u.id for u in real_active_updates])))
            else:
                # the active updates aren't really active - either their
                # executions were failed/cancelled, or the update failed at
                # the finalizing stage.
                # updating their states to failed and continuing.
                for dep_update in active_updates:
                    dep_update.state = STATES.FAILED
                    self.sm.update(dep_update)

    def _extract_changes(self,
                         dep_update,
                         raw_nodes,
                         previous_nodes):
        """Extracts the changes between the current node_instances and
        the raw_nodes specified

        :param dep_update:
        :param raw_nodes:
        :return: a dictionary of modification type and node instanced modified
        """
        deployment = self.sm.get(models.Deployment, dep_update.deployment_id)

        deployment_id_filter = {'deployment_id': deployment.id}

        # By this point the node_instances aren't updated yet
        previous_node_instances = \
            [instance.to_dict() for instance in
             self.sm.list(models.NodeInstance, filters=deployment_id_filter)]

        # extract all the None relationships from the depup nodes in order
        # to use in the extract changes
        no_none_relationships_nodes = copy.deepcopy(raw_nodes)
        for node in no_none_relationships_nodes:
            node['relationships'] = [r for r in node['relationships'] if r]

        # project changes in deployment
        changes = tasks.modify_deployment(
                nodes=no_none_relationships_nodes,
                previous_nodes=previous_nodes,
                previous_node_instances=previous_node_instances,
                scaling_groups=deployment.scaling_groups,
                modified_nodes=()
        )

        self._patch_changes_with_relationship_index(
                changes[NODE_MOD_TYPES.EXTENDED_AND_RELATED],
                raw_nodes)
        return changes

    @staticmethod
    def _patch_changes_with_relationship_index(raw_node_instances, raw_nodes):
        for raw_node_instance in (i for i in raw_node_instances
                                  if 'modification' in i):
            raw_node = next(n for n in raw_nodes
                            if n['id'] == raw_node_instance['node_id'])
            for relationship in raw_node_instance['relationships']:
                target_node_id = relationship['target_name']
                rel_index = \
                    next(i for i, d in enumerate(raw_node['relationships'])
                         if d['target_id'] == target_node_id)

                relationship['rel_index'] = rel_index

    def _execute_update_workflow(self,
                                 dep_update,
                                 node_instances,
                                 modified_entity_ids,
                                 skip_install=False,
                                 skip_uninstall=False,
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

        if not workflow_id:
            # Whether or not execute install or uninstall
            parameters['skip_install'] = skip_install
            parameters['skip_uninstall'] = skip_uninstall

        return self._execute_workflow(
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

        # mark deployment update as finalizing
        dep_update.state = STATES.FINALIZING
        self.sm.update(dep_update)

        # The order of these matter
        for finalize in [self._deployment_handler.finalize,
                         self._node_instance_handler.finalize,
                         self._node_handler.finalize]:
            finalize(dep_update)

        # mark deployment update as successful
        dep_update.state = STATES.SUCCESSFUL
        self.sm.update(dep_update)

        return self.get_deployment_update(deployment_update_id)

    def _execute_workflow(self,
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
        deployment = self.sm.get(models.Deployment, deployment_id)
        blueprint_id = deployment.blueprint_id

        if workflow_id not in deployment.workflows:
            raise manager_exceptions.NonexistentWorkflowError(
                'Workflow {0} does not exist in deployment {1}'
                .format(workflow_id, deployment_id))
        workflow = deployment.workflows[workflow_id]

        execution_parameters = \
            ResourceManager._merge_and_validate_execution_parameters(
                workflow, workflow_id, parameters, allow_custom_parameters)

        execution_id = str(uuid.uuid4())

        new_execution = models.Execution(
            id=execution_id,
            status=ExecutionState.PENDING,
            created_at=utils.get_formatted_timestamp(),
            workflow_id=workflow_id,
            error='',
            parameters=ResourceManager._get_only_user_execution_parameters(
                execution_parameters),
            is_system_workflow=False)

        if deployment:
            new_execution.set_deployment(deployment)
            deployment_update.execution = new_execution
        self.sm.put(new_execution)

        # executing the user workflow
        workflow_plugins = \
            deployment_update.deployment_plan[
                constants.WORKFLOW_PLUGINS_TO_INSTALL]
        workflow_executor.execute_workflow(
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
    return current_app.config.setdefault('deployment_updates_manager',
                                         DeploymentUpdateManager())
