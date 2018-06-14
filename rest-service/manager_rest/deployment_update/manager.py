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

import os
import copy
import uuid

from flask import current_app

from manager_rest import utils
from manager_rest import config
from dsl_parser import constants, tasks
from manager_rest import workflow_executor
from dsl_parser import exceptions as parser_exceptions
from manager_rest.dsl_functions import get_secret_method
from manager_rest import app_context, manager_exceptions
from manager_rest.resource_manager import ResourceManager
from manager_rest.deployment_update import step_extractor
from manager_rest.deployment_update.utils import extract_ids
from manager_rest.storage import get_storage_manager, models
from manager_rest.storage.models_states import ExecutionState
from manager_rest.deployment_update.validator import StepValidator
from manager_rest.deployment_update.constants import (
    STATES,
    ENTITY_TYPES,
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
        return self.sm.get(models.DeploymentUpdate, deployment_update_id)

    def list_deployment_updates(self,
                                include=None,
                                filters=None,
                                pagination=None,
                                sort=None,
                                substr_filters=None):
        return self.sm.list(models.DeploymentUpdate,
                            include=include,
                            filters=filters,
                            pagination=pagination,
                            substr_filters=substr_filters,
                            sort=sort)

    def stage_deployment_update(self,
                                deployment_id,
                                app_dir,
                                app_blueprint,
                                additional_inputs,
                                new_blueprint_id=None):
        # enables reverting to original blueprint resources
        deployment = self.sm.get(models.Deployment, deployment_id)
        old_blueprint = deployment.blueprint
        file_server_root = config.instance.file_server_root
        blueprint_resource_dir = os.path.join(file_server_root,
                                              'blueprints',
                                              old_blueprint.tenant_name,
                                              old_blueprint.id)
        # The dsl parser expects a URL
        blueprint_resource_dir_url = 'file:{0}'.format(blueprint_resource_dir)
        app_path = os.path.join(file_server_root, app_dir, app_blueprint)

        # parsing the blueprint from here
        try:
            plan = tasks.parse_dsl(
                app_path,
                resources_base_path=file_server_root,
                additional_resources=[blueprint_resource_dir_url],
                **app_context.get_parser_context()
            )
        except parser_exceptions.DSLParsingException as ex:
            raise manager_exceptions.InvalidBlueprintError(
                'Invalid blueprint - {0}'.format(ex))

        # Updating the new inputs with the deployment inputs
        # (overriding old values and adding new ones)
        old_inputs = copy.deepcopy(deployment.inputs)
        new_inputs = {k: old_inputs[k]
                      for k in plan.inputs.keys() if k in old_inputs}
        new_inputs.update(additional_inputs)

        # applying intrinsic functions
        try:
            prepared_plan = tasks.prepare_deployment_plan(plan,
                                                          get_secret_method(),
                                                          inputs=new_inputs)
        except parser_exceptions.MissingRequiredInputError, e:
            raise manager_exceptions.MissingRequiredDeploymentInputError(
                str(e))
        except parser_exceptions.UnknownInputError, e:
            raise manager_exceptions.UnknownDeploymentInputError(str(e))
        except parser_exceptions.UnknownSecretError, e:
            raise manager_exceptions.UnknownDeploymentSecretError(str(e))
        except parser_exceptions.UnsupportedGetSecretError, e:
            raise manager_exceptions.UnsupportedDeploymentGetSecretError(
                str(e))

        deployment_update_id = '{0}-{1}'.format(deployment.id, uuid.uuid4())
        deployment_update = models.DeploymentUpdate(
            id=deployment_update_id,
            deployment_plan=prepared_plan,
            created_at=utils.get_formatted_timestamp()
        )
        deployment_update.set_deployment(deployment)
        deployment_update.old_inputs = old_inputs
        deployment_update.new_inputs = new_inputs
        if new_blueprint_id:
            new_blueprint = self.sm.get(models.Blueprint, new_blueprint_id)
            deployment_update.old_blueprint = old_blueprint
            deployment_update.new_blueprint = new_blueprint
        self.sm.put(deployment_update)
        return deployment_update

    def create_deployment_update_step(self,
                                      deployment_update_id,
                                      action,
                                      entity_type,
                                      entity_id):
        step = models.DeploymentUpdateStep(id=str(uuid.uuid4()),
                                           action=action,
                                           entity_type=entity_type,
                                           entity_id=entity_id)
        deployment_update = self.get_deployment_update(deployment_update_id)
        step.set_deployment_update(deployment_update)
        return self.sm.put(step)

    def extract_steps_from_deployment_update(self, deployment_update):
        supported_steps, unsupported_steps = step_extractor.extract_steps(
            deployment_update)

        if unsupported_steps:
            deployment_update.state = STATES.FAILED
            self.sm.update(deployment_update)
            unsupported_entity_ids = [step.entity_id
                                      for step in unsupported_steps]
            raise manager_exceptions.UnsupportedChangeInDeploymentUpdate(
                'The blueprint you provided for the deployment update '
                'contains changes currently unsupported by the deployment '
                'update mechanism.\n'
                'Unsupported changes: {0}'.format('\n'.join(
                    unsupported_entity_ids)))

        for step in supported_steps:
            self.create_deployment_update_step(deployment_update.id,
                                               step.action,
                                               step.entity_type,
                                               step.entity_id)

    def commit_deployment_update(self,
                                 dep_update,
                                 skip_install=False,
                                 skip_uninstall=False,
                                 skip_reinstall=False,
                                 workflow_id=None,
                                 ignore_failure=False,
                                 install_first=False,
                                 reinstall_list=None):
        # Mark deployment update as committing
        dep_update.state = STATES.UPDATING
        self.sm.update(dep_update)

        # Handle any deployment related changes. i.e. workflows and deployments
        modified_deployment_entities, raw_updated_deployment = \
            self._deployment_handler.handle(dep_update)

        # Retrieve previous_nodes
        previous_nodes = [node.to_dict() for node in self.sm.list(
            models.Node, filters={'deployment_id': dep_update.deployment_id})]

        # Update the nodes on the storage
        modified_entity_ids, depup_nodes = self._node_handler.handle(
            dep_update)

        # Extract changes from raw nodes
        node_instance_changes = self._extract_changes(dep_update,
                                                      depup_nodes,
                                                      previous_nodes)

        # Create (and update for adding step type) node instances
        # according to the changes in raw_nodes
        depup_node_instances = self._node_instance_handler.handle(
            dep_update, node_instance_changes)

        # Saving the needed changes back to the storage manager for future use
        # (removing entities).
        dep_update.deployment_update_deployment = raw_updated_deployment
        dep_update.deployment_update_nodes = depup_nodes
        dep_update.deployment_update_node_instances = depup_node_instances
        dep_update.modified_entity_ids = modified_entity_ids.to_dict(
            include_rel_order=True)
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
            skip_reinstall=skip_reinstall,
            workflow_id=workflow_id,
            ignore_failure=ignore_failure,
            install_first=install_first,
            reinstall_list=reinstall_list
        )

        # Update deployment attributes in the storage manager
        deployment = self.sm.get(models.Deployment, dep_update.deployment_id)
        deployment.inputs = dep_update.new_inputs
        if dep_update.new_blueprint:
            deployment.blueprint = dep_update.new_blueprint
        self.sm.update(deployment)

        # Update deployment update attributes in the storage manager
        dep_update.execution = execution
        dep_update.state = STATES.EXECUTING_WORKFLOW
        self.sm.update(dep_update)

        # Return the deployment update object
        return self.get_deployment_update(dep_update.id)

    def validate_no_active_updates_per_deployment(self,
                                                  deployment_id,
                                                  force=False):
        existing_updates = self.list_deployment_updates(
            filters={'deployment_id': deployment_id}).items
        active_updates = [u for u in existing_updates
                          if u.state not in (STATES.SUCCESSFUL, STATES.FAILED)]
        if not active_updates:
            return

        if not force:
            raise manager_exceptions.ConflictError(
                'there are deployment updates still active; update IDs: {0}'
                .format(', '.join([u.id for u in active_updates])))

        # real active updates are those with an execution in a running status
        real_active_updates = [
            u for u in active_updates if u.execution_id is not None
            and self.sm.get(models.Execution, u.execution_id).status
            not in ExecutionState.END_STATES
        ]

        if real_active_updates:
            raise manager_exceptions.ConflictError(
                'there are deployment updates still active; the "force" flag '
                'was used yet these updates have actual executions running '
                'update IDs: {0}'.format(', '.join(
                    [u.id for u in real_active_updates])))
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

        :param dep_update: deployment update object
        :param raw_nodes: node objects from deployment update
        :return: a dictionary of modification type and node instanced modified
        """
        deployment = self.sm.get(models.Deployment, dep_update.deployment_id)
        deployment_id_filter = {'deployment_id': deployment.id}

        # By this point the node_instances aren't updated yet
        previous_node_instances = [instance.to_dict() for instance in
                                   self.sm.list(models.NodeInstance,
                                                filters=deployment_id_filter)]

        # extract all the None relationships from the deployment update nodes
        # in order to use in the extract changes
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
                changes[NODE_MOD_TYPES.EXTENDED_AND_RELATED], raw_nodes)
        return changes

    @staticmethod
    def _patch_changes_with_relationship_index(raw_node_instances, raw_nodes):
        for raw_node_instance in (i for i in raw_node_instances
                                  if 'modification' in i):
            raw_node = next(n for n in raw_nodes
                            if n['id'] == raw_node_instance['node_id'])
            for relationship in raw_node_instance['relationships']:
                target_node_id = relationship['target_name']
                rel_index = next(i for i, d
                                 in enumerate(raw_node['relationships'])
                                 if d['target_id'] == target_node_id)
                relationship['rel_index'] = rel_index

    @staticmethod
    def _update_reinstall_list(reinstall_list,
                               modified_entity_ids,
                               dep_update,
                               skip_reinstall):
        """Add nodes that their properties have been updated to the list of
        node instances to reinstall, unless skip_reinstall is true"""
        reinstall_list = reinstall_list or []
        if skip_reinstall:
            return reinstall_list
        sm = get_storage_manager()

        # get all entities with modifications in properties or operations
        for change_type in (ENTITY_TYPES.PROPERTY, ENTITY_TYPES.OPERATION):
            for modified in modified_entity_ids[change_type]:
                modified = modified.split(':')

                # pick only entities that are part of nodes
                if modified[0].lower() != 'nodes':
                    continue

                # list instances of each node
                node_instances = sm.list(
                    models.NodeInstance,
                    filters={'deployment_id': dep_update.deployment_id,
                             'node_id': modified[1]}
                )

                # add instances ids to the reinstall list
                reinstall_list += [e.id for e in node_instances.items]
        return reinstall_list

    def _execute_update_workflow(self,
                                 dep_update,
                                 node_instances,
                                 modified_entity_ids,
                                 skip_install=False,
                                 skip_uninstall=False,
                                 skip_reinstall=False,
                                 workflow_id=None,
                                 ignore_failure=False,
                                 install_first=False,
                                 reinstall_list=None):
        """Executed the update workflow or a custom workflow

        :param dep_update: deployment update object
        :param node_instances: a dictionary of modification type and
        add_node.modification instances
        :param modified_entity_ids: the entire add_node.modification entities
        list (by id)
        :return: Execution object
        """
        added_instances = node_instances[NODE_MOD_TYPES.ADDED_AND_RELATED]
        extended_instances = \
            node_instances[NODE_MOD_TYPES.EXTENDED_AND_RELATED]
        reduced_instances = node_instances[NODE_MOD_TYPES.REDUCED_AND_RELATED]
        removed_instances = node_instances[NODE_MOD_TYPES.REMOVED_AND_RELATED]
        reinstall_list = self._update_reinstall_list(reinstall_list,
                                                     modified_entity_ids,
                                                     dep_update,
                                                     skip_reinstall)
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
                extract_ids(removed_instances.get(NODE_MOD_TYPES.RELATED)),

            # Whether or not execute install/uninstall/reinstall,
            # order of execution, and behavior in failure while uninstalling
            'skip_install': skip_install,
            'skip_uninstall': skip_uninstall,
            'ignore_failure': ignore_failure,
            'install_first': install_first,

            # List of node-instances to reinstall
            'node_instances_to_reinstall': reinstall_list
        }
        return self._execute_workflow(
            deployment_update=dep_update,
            workflow_id=workflow_id or DEFAULT_DEPLOYMENT_UPDATE_WORKFLOW,
            parameters=parameters,
            allow_custom_parameters=True
        )

    def finalize_commit(self, deployment_update_id):
        """ finalizes the update process by removing any removed
        node/node-instances and updating any reduced node
        """
        # mark deployment update as finalizing
        dep_update = self.get_deployment_update(deployment_update_id)
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
        return dep_update

    def _execute_workflow(self,
                          deployment_update,
                          workflow_id,
                          parameters=None,
                          allow_custom_parameters=False):
        deployment = deployment_update.deployment
        if workflow_id not in deployment.workflows:
            raise manager_exceptions.NonexistentWorkflowError(
                'Workflow {0} does not exist in deployment {1}'.format(
                    workflow_id, deployment.id))
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
            is_system_workflow=False
        )
        if deployment:
            new_execution.set_deployment(deployment)
            deployment_update.execution = new_execution
        self.sm.put(new_execution)

        # executing the user workflow
        workflow_plugins = deployment_update.deployment_plan[
            constants.WORKFLOW_PLUGINS_TO_INSTALL]
        workflow_executor.execute_workflow(
            workflow_id,
            workflow,
            workflow_plugins=workflow_plugins,
            blueprint_id=deployment.blueprint_id,
            deployment_id=deployment.id,
            execution_id=execution_id,
            execution_parameters=execution_parameters
        )
        return new_execution


# What we need to access this manager in Flask
def get_deployment_updates_manager():
    """
    Get the current app's deployment updates manager, create if necessary
    """
    return current_app.config.setdefault('deployment_updates_manager',
                                         DeploymentUpdateManager())
