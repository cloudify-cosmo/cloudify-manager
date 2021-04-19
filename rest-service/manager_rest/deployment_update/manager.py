########
# Copyright (c) 2017-2019 Cloudify Platform Ltd. All rights reserved
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

from cloudify.models_states import ExecutionState
from cloudify.utils import extract_and_merge_plugins

from dsl_parser import constants, tasks

from manager_rest import manager_exceptions
from manager_rest.resource_manager import get_resource_manager
from manager_rest.deployment_update import step_extractor
from manager_rest.deployment_update.utils import extract_ids
from manager_rest.deployment_update.validator import StepValidator
from manager_rest.storage import (get_storage_manager,
                                  models,
                                  get_read_only_storage_manager,
                                  db)
from manager_rest.deployment_update.constants import (
    STATES,
    ENTITY_TYPES,
    NODE_MOD_TYPES,
    DEFAULT_DEPLOYMENT_UPDATE_WORKFLOW
)
from manager_rest.deployment_update.handlers import (
    DeploymentDependencies,
    DeploymentUpdateNodeHandler,
    DeploymentUpdateDeploymentHandler,
    DeploymentUpdateNodeInstanceHandler)
from manager_rest.utils import get_formatted_timestamp

from manager_rest.rest.rest_utils import (
    get_deployment_plan,
    get_labels_from_plan,
    get_parsed_deployment,
    RecursiveDeploymentDependencies,
    RecursiveDeploymentLabelsDependencies,
    verify_blueprint_uploaded_state,
)
from manager_rest.execution_token import current_execution


class DeploymentUpdateManager(object):

    def __init__(self, sm):
        self.sm = sm
        self._node_handler = DeploymentUpdateNodeHandler(sm)
        self._node_instance_handler = DeploymentUpdateNodeInstanceHandler(sm)
        self._deployment_handler = DeploymentUpdateDeploymentHandler(sm)
        self._deployment_dependency_handler = DeploymentDependencies(sm)
        self._step_validator = StepValidator(sm)

    def get_deployment_update(self, deployment_update_id, include=None):
        return self.sm.get(
            models.DeploymentUpdate, deployment_update_id, include=include)

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
                                new_blueprint_id=None,
                                preview=False,
                                runtime_only_evaluation=False,
                                auto_correct_types=False,
                                reevaluate_active_statuses=False):

        # validate no active updates are running for a deployment_id
        if reevaluate_active_statuses:
            self.reevaluate_updates_statuses_per_deployment(deployment_id)
        self.validate_no_active_updates_per_deployment(deployment_id)

        # enables reverting to original blueprint resources
        deployment = self.sm.get(models.Deployment, deployment_id)
        old_blueprint = deployment.blueprint
        runtime_only_evaluation = (runtime_only_evaluation or
                                   deployment.runtime_only_evaluation)
        parsed_deployment = get_parsed_deployment(old_blueprint,
                                                  app_dir,
                                                  app_blueprint)

        # Updating the new inputs with the deployment inputs
        # (overriding old values and adding new ones)
        old_inputs = copy.deepcopy(deployment.inputs)
        new_inputs = {k: old_inputs[k]
                      for k in parsed_deployment.inputs if k in old_inputs}
        new_inputs.update(additional_inputs)

        # applying intrinsic functions
        plan = get_deployment_plan(parsed_deployment, new_inputs,
                                   runtime_only_evaluation,
                                   auto_correct_types)

        deployment_update_id = '{0}-{1}'.format(deployment.id, uuid.uuid4())
        deployment_update = models.DeploymentUpdate(
            id=deployment_update_id,
            deployment_plan=plan,
            runtime_only_evaluation=runtime_only_evaluation,
            created_at=get_formatted_timestamp()
        )
        deployment_update.set_deployment(deployment)
        deployment_update.preview = preview
        deployment_update.old_inputs = old_inputs
        deployment_update.new_inputs = new_inputs
        if new_blueprint_id:
            new_blueprint = self.sm.get(models.Blueprint, new_blueprint_id)
            verify_blueprint_uploaded_state(new_blueprint)
            deployment_update.old_blueprint = old_blueprint
            deployment_update.new_blueprint = new_blueprint
        self.sm.put(deployment_update)
        return deployment_update

    def reevaluate_updates_statuses_per_deployment(self, deployment_id: str):
        for active_update in self.list_deployment_updates(
                filters={'deployment_id': deployment_id,
                         'state': [STATES.UPDATING,
                                   STATES.EXECUTING_WORKFLOW,
                                   STATES.FINALIZING]}):
            reevaluated_state = _map_execution_to_deployment_update_status(
                active_update.execution.status)
            if reevaluated_state and active_update.state != reevaluated_state:
                current_app.logger.info("Deployment update %s status "
                                        "reevaluation: `%s` -> `%s`",
                                        active_update.id,
                                        active_update.state,
                                        reevaluated_state)
                active_update.state = reevaluated_state
                self.sm.update(active_update)

    def create_deployment_update_step(self,
                                      deployment_update,
                                      action,
                                      entity_type,
                                      entity_id,
                                      topology_order):
        step = models.DeploymentUpdateStep(id=str(uuid.uuid4()),
                                           action=action,
                                           entity_type=entity_type,
                                           entity_id=entity_id,
                                           topology_order=topology_order)
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
            self.create_deployment_update_step(deployment_update,
                                               step.action,
                                               step.entity_type,
                                               step.entity_id,
                                               step.topology_order)

    def delete_input_label_after_deployment_update(self,
                                                   rm,
                                                   dep_graph,
                                                   dep,
                                                   old_csys_environment):
        rm.delete_deployment_from_labels_graph(
            dep_graph, dep, old_csys_environment
        )
        self._delete_single_label_from_deployment(
            'csys-obj-parent',
            old_csys_environment,
            dep
        )

    @staticmethod
    def add_input_label_after_deployment_update(rm,
                                                dep_graph,
                                                dep,
                                                new_csys_environment):
        labels_to_add = rm.get_deployment_parents_from_inputs(
            new_csys_environment
        )
        if labels_to_add:
            rm.create_resource_labels(
                models.DeploymentLabel,
                dep,
                labels_to_add
            )
            rm.add_deployment_to_labels_graph(
                dep_graph,
                dep,
                new_csys_environment
            )
            dep_graph.propagate_deployment_statuses(
                new_csys_environment
            )

    def update_deployment_parents_from_input(self,
                                             rm,
                                             dep,
                                             old_inputs,
                                             new_inputs):
        old_inputs = old_inputs or {}
        new_inputs = new_inputs or {}
        old_csys_environment = old_inputs.get('csys-environment')
        new_csys_environment = new_inputs.get('csys-environment')
        if old_csys_environment or new_csys_environment:
            dep_graph = RecursiveDeploymentLabelsDependencies(self.sm)
            dep_graph.create_dependencies_graph()

            if new_csys_environment and not old_csys_environment:
                self.add_input_label_after_deployment_update(
                    rm,
                    dep_graph,
                    dep,
                    new_csys_environment
                )

            elif old_csys_environment and not new_csys_environment:
                self.delete_input_label_after_deployment_update(
                    rm,
                    dep_graph,
                    dep,
                    old_csys_environment
                )

            elif old_csys_environment and new_csys_environment and \
                    old_csys_environment != new_csys_environment:
                self.delete_input_label_after_deployment_update(
                    rm,
                    dep_graph,
                    dep,
                    old_csys_environment
                )
                self.add_input_label_after_deployment_update(
                    rm,
                    dep_graph,
                    dep,
                    new_csys_environment
                )

    def commit_deployment_update(self,
                                 dep_update,
                                 skip_install=False,
                                 skip_uninstall=False,
                                 skip_reinstall=False,
                                 workflow_id=None,
                                 ignore_failure=False,
                                 install_first=False,
                                 reinstall_list=None,
                                 update_plugins=True,
                                 force=False):
        # Mark deployment update as committing
        rm = get_resource_manager()
        dep_update.keep_old_deployment_dependencies = skip_uninstall
        dep_update.state = STATES.UPDATING
        self.sm.update(dep_update)

        # Handle any deployment related changes. i.e. workflows and deployments
        modified_deployment_entities, raw_updated_deployment = \
            self._deployment_handler.handle(dep_update)

        # Retrieve previous_nodes
        previous_nodes = [node.to_dict() for node in self.sm.list(
            models.Node, filters={'deployment_id': dep_update.deployment_id},
            get_all_results=True
        )]

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

        # Calculate which plugins to install and which to uninstall
        central_plugins_to_install, central_plugins_to_uninstall = \
            self._extract_plugins_changes(dep_update, update_plugins)

        # Calculate which deployment schedules need to be added or deleted
        schedules_to_create, schedules_to_delete = \
            self._extract_schedules_changes(dep_update)

        # Saving the needed changes back to the storage manager for future use
        # (removing entities).
        dep_update.deployment_update_deployment = raw_updated_deployment
        dep_update.deployment_update_nodes = depup_nodes
        dep_update.deployment_update_node_instances = depup_node_instances
        dep_update.modified_entity_ids = modified_entity_ids.to_dict(
            include_rel_order=True)
        dep_update.central_plugins_to_install = central_plugins_to_install
        dep_update.central_plugins_to_uninstall = central_plugins_to_uninstall
        deployment = self.sm.get(models.Deployment, dep_update.deployment_id)
        labels_to_create = self._get_deployment_labels_to_create(dep_update)
        csys_environment = dep_update.new_inputs.get('csys-environment')
        new_inputs = dep_update.new_inputs.copy()
        old_inputs = deployment.inputs.copy()
        rm.verify_csys_environment_input(deployment, csys_environment)
        parents_labels = []
        if labels_to_create:
            parents_labels = rm.get_deployment_parents_from_labels(
                labels_to_create
            )
            dep_graph = RecursiveDeploymentLabelsDependencies(self.sm)
            dep_graph.create_dependencies_graph()
            rm.verify_attaching_deployment_to_parents(
                dep_graph,
                parents_labels,
                deployment.id
            )
        self.sm.update(dep_update)
        # If this is a preview, no need to run workflow and update DB
        if dep_update.preview:
            dep_update.state = STATES.PREVIEW
            dep_update.id = None

            # retrieving recursive dependencies for the updated deployment
            dep_graph = RecursiveDeploymentDependencies(self.sm)
            dep_graph.create_dependencies_graph()
            deployment_dependencies = dep_graph.retrieve_dependent_deployments(
                dep_update.deployment_id)
            dep_update.set_recursive_dependencies(deployment_dependencies)
            dep_update.schedules_to_create = \
                self.list_schedules(schedules_to_create)
            dep_update.schedules_to_delete = schedules_to_delete
            dep_update.labels_to_create = [{'key': label[0], 'value': label[1]}
                                           for label in labels_to_create]
            return dep_update

        # Handle inter-deployment dependencies changes
        self._deployment_dependency_handler.handle(dep_update)

        # Execute the default 'update' workflow or a custom workflow using
        # added and related instances. Any workflow executed should call
        # finalize_update, since removing entities should be done after the
        # executions.
        # The raw_node_instances are being used only for their ids, thus
        # they should really hold the finished version for the node instance.
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
            reinstall_list=reinstall_list,
            central_plugins_to_install=central_plugins_to_install,
            central_plugins_to_uninstall=central_plugins_to_uninstall,
            update_plugins=update_plugins,
            force=force
        )

        # Update deployment attributes in the storage manager
        deployment.inputs = dep_update.new_inputs
        deployment.runtime_only_evaluation = dep_update.runtime_only_evaluation
        if dep_update.new_blueprint:
            deployment.blueprint = dep_update.new_blueprint
        self.sm.update(deployment)

        # Update deployment update attributes in the storage manager
        dep_update.execution = execution
        dep_update.state = STATES.EXECUTING_WORKFLOW
        self.sm.update(dep_update)

        # First, delete old deployment schedules
        for schedule_id in schedules_to_delete:
            schedule = self.sm.get(
                models.ExecutionSchedule,
                None,
                filters={'id': schedule_id, 'deployment_id': deployment.id})
            self.sm.delete(schedule)

        # Then, create new deployment schedules
        deployment_creation_time = datetime.strptime(
            deployment.created_at.split('.')[0], '%Y-%m-%dT%H:%M:%S'
        ).replace(second=0)
        rm.create_deployment_schedules_from_dict(
            schedules_to_create, deployment, deployment_creation_time)

        rm.create_resource_labels(
            models.DeploymentLabel,
            deployment,
            labels_to_create
        )
        if parents_labels:
            for parent in parents_labels:
                rm.add_deployment_to_labels_graph(
                    dep_graph,
                    deployment,
                    parent
                )
        self.update_deployment_parents_from_input(
            rm,
            deployment,
            old_inputs,
            new_inputs
        )
        return self.get_deployment_update(dep_update.id)

    def validate_no_active_updates_per_deployment(self, deployment_id):
        existing_updates = self.list_deployment_updates(
            filters={'deployment_id': deployment_id}).items
        active_updates = [u for u in existing_updates
                          if u.state not in (STATES.SUCCESSFUL, STATES.FAILED)]
        if not active_updates:
            return
        raise manager_exceptions.ConflictError(
            'there are deployment updates still active; update IDs: {0}'
            .format(', '.join([u.id for u in active_updates])))

    @staticmethod
    def list_schedules(schedules_dict):
        schedules_list = []
        for k, v in schedules_dict.items():
            list_item = v
            list_item['id'] = k
            schedules_list.append(list_item)
        return schedules_list

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
                                                filters=deployment_id_filter,
                                                get_all_results=True)]

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

    def _validate_reinstall_list(self,
                                 reinstall,
                                 add,
                                 remove,
                                 dep_update):
        """validate node-instances explicitly supplied to reinstall list exist
        and are not about to be installed or uninstalled in this update"""
        node_instances = self.sm.list(
            models.NodeInstance,
            filters={'deployment_id': dep_update.deployment_id},
            get_all_results=True
        )
        node_instances_ids = [n.id for n in node_instances]
        add_conflict = [n for n in reinstall if n in add]
        remove_conflict = [n for n in reinstall if n in remove]
        not_existing = [n for n in reinstall if n not in node_instances_ids]
        msg = 'Invalid reinstall list supplied.'
        if not_existing:
            msg += '\nFollowing node instances do not exist in this ' \
                   'deployment: ' + ', '.join(not_existing)
        if add_conflict:
            msg += '\nFollowing node instances are just being added in the ' \
                   'update: ' + ', '.join(add_conflict)
        if remove_conflict:
            msg += '\nFollowing node instances are just being removed in ' \
                   'the update: ' + ', '.join(remove_conflict)
        if any([not_existing, add_conflict, remove_conflict]):
            dep_update.state = STATES.FAILED
            self.sm.update(dep_update)
            raise manager_exceptions.BadParametersError(msg)

    def _update_reinstall_list(self,
                               reinstall_list,
                               add_list,
                               remove_list,
                               modified_entity_ids,
                               dep_update,
                               skip_reinstall):
        """Add nodes that their properties have been updated to the list of
        node instances to reinstall, unless skip_reinstall is true"""
        reinstall_list = reinstall_list or []
        self._validate_reinstall_list(reinstall_list,
                                      add_list,
                                      remove_list,
                                      dep_update)
        if skip_reinstall:
            return reinstall_list

        # get all entities with modifications in properties or operations
        for change_type in (ENTITY_TYPES.PROPERTY, ENTITY_TYPES.OPERATION):
            for modified in modified_entity_ids[change_type]:
                modified = modified.split(':')

                # pick only entities that are part of nodes
                if modified[0].lower() != 'nodes':
                    continue

                # list instances of each node
                node_instances = self.sm.list(
                    models.NodeInstance,
                    filters={'deployment_id': dep_update.deployment_id,
                             'node_id': modified[1]},
                    get_all_results=True
                )

                # add instances ids to the reinstall list, if they are not in
                # the install/uninstall list
                reinstall_list += [e.id for e in node_instances.items
                                   if e.id not in add_list
                                   and e.id not in remove_list]
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
                                 reinstall_list=None,
                                 central_plugins_to_install=None,
                                 central_plugins_to_uninstall=None,
                                 update_plugins=True,
                                 force=False):
        """Executed the update workflow or a custom workflow

        :param dep_update: deployment update object
        :param node_instances: a dictionary of modification type and
        add_node.modification instances
        :param modified_entity_ids: the entire add_node.modification entities
        list (by id)
        :param skip_install: if to skip installation of node instances.
        :param skip_uninstall: if to skip uninstallation of node instances.
        :param skip_reinstall: if to skip reinstallation of node instances.
        :param workflow_id: the update workflow id
        :param ignore_failure: if to ignore failures.
        :param install_first: if to install the node instances before
        uninstalling them.
        :param reinstall_list: list of node instances to reinstall.
        :param central_plugins_to_install: plugins to install that have the
        central_deployment_agent as the executor.
        :param central_plugins_to_uninstall: plugins to uninstall that have the
        central_deployment_agent as the executor.
        :param update_plugins: whether or not to perform plugin updates.
        :param force: force update (i.e. even if the blueprint is used to
        create components).

        :return: an Execution object.
        """
        added_instances = node_instances[NODE_MOD_TYPES.ADDED_AND_RELATED]
        extended_instances = \
            node_instances[NODE_MOD_TYPES.EXTENDED_AND_RELATED]
        reduced_instances = node_instances[NODE_MOD_TYPES.REDUCED_AND_RELATED]
        removed_instances = node_instances[NODE_MOD_TYPES.REMOVED_AND_RELATED]
        added_instance_ids = extract_ids(
            added_instances.get(NODE_MOD_TYPES.AFFECTED))
        removed_instance_ids = extract_ids(
            removed_instances.get(NODE_MOD_TYPES.AFFECTED))
        reinstall_list = self._update_reinstall_list(reinstall_list,
                                                     added_instance_ids,
                                                     removed_instance_ids,
                                                     modified_entity_ids,
                                                     dep_update,
                                                     skip_reinstall)
        parameters = {
            # needed in order to finalize the commit
            'update_id': dep_update.id,

            # For any added node instance
            'added_instance_ids': added_instance_ids,
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
            'removed_instance_ids': removed_instance_ids,
            'remove_target_instance_ids':
                extract_ids(removed_instances.get(NODE_MOD_TYPES.RELATED)),

            # Whether or not execute install/uninstall/reinstall,
            # order of execution, behavior in failure while uninstalling, and
            # whether or not to update the plugins.
            'skip_install': skip_install,
            'skip_uninstall': skip_uninstall,
            'ignore_failure': ignore_failure,
            'install_first': install_first,
            'update_plugins': update_plugins,

            # Plugins that are executed by the central deployment agent and
            # need to be un/installed
            'central_plugins_to_install': central_plugins_to_install,
            'central_plugins_to_uninstall': central_plugins_to_uninstall,

            # List of node-instances to reinstall
            'node_instances_to_reinstall': reinstall_list
        }
        execution = models.Execution(
            workflow_id=workflow_id or DEFAULT_DEPLOYMENT_UPDATE_WORKFLOW,
            deployment=dep_update.deployment,
            allow_custom_parameters=True,
            blueprint_id=dep_update.new_blueprint_id,
            parameters=parameters,
            status=ExecutionState.PENDING,
        )
        self.sm.put(execution)
        if current_execution and \
                current_execution.workflow_id == 'csys_update_deployment':
            # if we're created from a update_deployment workflow, join its
            # exec-groups, for easy tracking
            for exec_group in current_execution.execution_groups:
                exec_group.executions.append(execution)
            db.session.commit()
        return get_resource_manager().execute_workflow(
            execution,
            allow_overlapping_running_wf=True,
            force=force,
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
        self._deployment_handler.finalize(dep_update)
        self._node_instance_handler.finalize(dep_update)
        self._node_handler.finalize(dep_update)
        self._deployment_dependency_handler.finalize(dep_update)

        # mark deployment update as successful
        dep_update.state = STATES.SUCCESSFUL
        self.sm.update(dep_update)
        return dep_update

    def _extract_plugins_changes(self, dep_update, update_plugins):
        """Extracts plugins that need to be installed or uninstalled.

        :param dep_update: a DeploymentUpdate object.
        :param update_plugins: whether to update the plugins or not.
        :return: plugins that need installation and uninstallation (a tuple).
        """

        def get_plugins_to_install(plan, is_old_plan):
            return extract_and_merge_plugins(
                plan[constants.DEPLOYMENT_PLUGINS_TO_INSTALL],
                plan[constants.WORKFLOW_PLUGINS_TO_INSTALL],
                filter_func=is_centrally_deployed,
                with_repetition=is_old_plan)

        def is_centrally_deployed(plugin):
            return (plugin[constants.PLUGIN_EXECUTOR_KEY]
                    == constants.CENTRAL_DEPLOYMENT_AGENT)

        def extend_list_from_dict(source_dict, filter_out_dict, target_list):
            target_list.extend(
                source_dict[k]
                for k in source_dict if k not in filter_out_dict)

        if not update_plugins:
            return [], []

        deployment = self.sm.get(models.Deployment, dep_update.deployment_id)
        old_plan = deployment.blueprint.plan
        new_plan = dep_update.deployment_plan
        plugins_to_install_old = get_plugins_to_install(old_plan, True)
        plugins_to_install_new = get_plugins_to_install(new_plan, False)
        # Convert to plugin_name->plugin dict
        new_plugins = {p[constants.PLUGIN_NAME_KEY]: p
                       for p in plugins_to_install_new}
        old_plugins = {p[constants.PLUGIN_NAME_KEY]: p
                       for p in plugins_to_install_old}

        central_plugins_to_install, central_plugins_to_uninstall = [], []
        extend_list_from_dict(source_dict=new_plugins,
                              filter_out_dict=old_plugins,
                              target_list=central_plugins_to_install)
        extend_list_from_dict(source_dict=old_plugins,
                              filter_out_dict=new_plugins,
                              target_list=central_plugins_to_uninstall)
        # Deal with the intersection between the old and new plugins
        intersection = (k for k in new_plugins if k in old_plugins)
        for plugin_name in intersection:
            old_plugin = old_plugins[plugin_name]
            new_plugin = new_plugins[plugin_name]
            if new_plugin == old_plugin:
                continue
            central_plugins_to_install.append(new_plugin)
            central_plugins_to_uninstall.append(old_plugin)

        return central_plugins_to_install, central_plugins_to_uninstall

    def _extract_schedules_changes(self, dep_update):
        deployment = self.sm.get(models.Deployment, dep_update.deployment_id)
        old_settings = deployment.blueprint.plan.get('deployment_settings')
        new_settings = dep_update.deployment_plan.get('deployment_settings')
        schedules_to_delete = []
        schedules_to_create = {}
        if old_settings:
            for schedule_id in old_settings.get('default_schedules', {}):
                try:
                    schedule = self.sm.get(
                        models.ExecutionSchedule,
                        None,
                        filters={'id': schedule_id,
                                 'deployment_id': deployment.id})
                    if schedule.deployment_id == deployment.id:
                        schedules_to_delete.append(schedule_id)
                except manager_exceptions.NotFoundError:
                    continue
        if new_settings:
            name_conflict_error_msg = \
                'The Blueprint used for the deployment update contains a ' \
                'default schedule `{0}`, but a deployment schedule `{0}` ' \
                'already exists for the deployment `{1}` . Please either ' \
                'delete the existing schedule or fix the blueprint.'
            schedules_to_create = new_settings.get('default_schedules', {})
            for schedule_id in schedules_to_create:
                try:
                    self.sm.get(models.ExecutionSchedule,
                                None,
                                filters={'id': schedule_id,
                                         'deployment_id': deployment.id})
                    if schedule_id not in schedules_to_delete:
                        raise manager_exceptions.InvalidBlueprintError(
                            name_conflict_error_msg.format(schedule_id,
                                                           deployment.id))
                except manager_exceptions.NotFoundError:
                    continue
        return schedules_to_create, schedules_to_delete

    def _get_deployment_labels_to_create(self, dep_update):
        deployment = self.sm.get(models.Deployment, dep_update.deployment_id)
        new_labels = get_labels_from_plan(dep_update.deployment_plan,
                                          constants.LABELS)
        return get_resource_manager().get_labels_to_create(deployment,
                                                           new_labels)

    def _delete_single_label_from_deployment(self,
                                             label_key,
                                             label_value,
                                             deployment):
        dep_label = self.sm.get(
            models.DeploymentLabel,
            None,
            filters={
                '_labeled_model_fk': deployment._storage_id,
                'key': label_key,
                'value': label_value
            }
        )
        self.sm.delete(dep_label)


# What we need to access this manager in Flask
def get_deployment_updates_manager(preview=False):
    """
    Get the current app's deployment updates manager, create if necessary
    """
    if preview:
        return current_app.config.setdefault(
            'deployment_updates_preview_manager',
            DeploymentUpdateManager(get_read_only_storage_manager())
        )
    return current_app.config.setdefault(
        'deployment_updates_manager',
        DeploymentUpdateManager(get_storage_manager())
    )


def _map_execution_to_deployment_update_status(execution_status: str) -> str:
    if execution_status == ExecutionState.TERMINATED:
        return STATES.SUCCESSFUL
    if execution_status in [ExecutionState.FAILED,
                            ExecutionState.CANCELLED,
                            ExecutionState.CANCELLING,
                            ExecutionState.FORCE_CANCELLING,
                            ExecutionState.KILL_CANCELLING]:
        return STATES.FAILED
