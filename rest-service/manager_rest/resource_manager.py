#########
# Copyright (c) 2017-2019 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

import os
import uuid
import yaml
import json
import shutil
import itertools
from copy import deepcopy
from datetime import datetime
from collections import defaultdict

from flask import current_app
from flask_security import current_user
from sqlalchemy.orm import aliased
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import or_ as sql_or, and_ as sql_and

from cloudify.constants import TERMINATED_STATES as TERMINATED_TASK_STATES
from cloudify.cryptography_utils import encrypt
from cloudify.workflows import tasks as cloudify_tasks
from cloudify.utils import parse_utc_datetime_relative
from cloudify.models_states import (SnapshotState,
                                    ExecutionState,
                                    VisibilityState,
                                    BlueprintUploadState,
                                    DeploymentModificationState,
                                    PluginInstallationState,
                                    DeploymentState)
from cloudify_rest_client.client import CloudifyClient

from dsl_parser import constants, tasks

from manager_rest import premium_enabled
from manager_rest.constants import (DEFAULT_TENANT_NAME,
                                    FILE_SERVER_BLUEPRINTS_FOLDER,
                                    FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
                                    FILE_SERVER_DEPLOYMENTS_FOLDER)
from manager_rest.utils import (send_event,
                                get_formatted_timestamp,
                                is_create_global_permitted,
                                validate_global_modification,
                                validate_deployment_and_site_visibility,
                                extract_host_agent_plugins_from_plan)
from manager_rest.rest.rest_utils import (
    RecursiveDeploymentDependencies,
    RecursiveDeploymentLabelsDependencies,
    update_inter_deployment_dependencies,
    verify_blueprint_uploaded_state,
    compute_rule_from_scheduling_params,
)
from manager_rest.deployment_update.constants import STATES as UpdateStates
from manager_rest.plugins_update.constants import STATES as PluginsUpdateStates

from manager_rest.storage import (db,
                                  get_storage_manager,
                                  models,
                                  get_node)

from . import utils
from . import config
from . import app_context
from . import workflow_executor
from . import manager_exceptions


class ResourceManager(object):

    def __init__(self, sm=None):
        self.sm = sm or get_storage_manager()

    def list_executions(self, include=None, is_include_system_workflows=False,
                        filters=None, pagination=None, sort=None,
                        all_tenants=False, get_all_results=False,
                        load_relationships=False):
        filters = filters or {}
        is_system_workflow = filters.get('is_system_workflow')
        if is_system_workflow:
            filters['is_system_workflow'] = []
            for value in is_system_workflow:
                value = str(value).lower() == 'true'
                filters['is_system_workflow'].append(value)
        elif not is_include_system_workflows:
            filters['is_system_workflow'] = [False]
        return self.sm.list(
            models.Execution,
            include=include,
            filters=filters,
            pagination=pagination,
            sort=sort,
            all_tenants=all_tenants,
            get_all_results=get_all_results,
            load_relationships=load_relationships,
        )

    def update_deployment_statuses(self, latest_execution):
        """
        Update deployment statuses based on latest execution
        :param latest_execution: Latest execution object
        """
        if latest_execution.workflow_id == 'delete_deployment_environment' or\
                not latest_execution.deployment_id:
            return

        node_instances = self.sm.list(
            models.NodeInstance,
            filters={
                'deployment_id': latest_execution.deployment_id,
                'state': lambda col: col != 'started'
            },
            get_all_results=True
        )
        installation_status = DeploymentState.ACTIVE
        if node_instances:
            installation_status = DeploymentState.INACTIVE

        dep = latest_execution.deployment
        dep.installation_status = installation_status
        dep.latest_execution = latest_execution
        dep.deployment_status = dep.evaluate_deployment_status()
        self.sm.update(dep)
        if dep.deployment_parents:
            graph = RecursiveDeploymentLabelsDependencies(self.sm)
            graph.create_dependencies_graph()
            graph.propagate_deployment_statuses(dep.id)

    def update_execution_status(self, execution_id, status, error):
        with self.sm.transaction():
            execution = self.sm.get(models.Execution, execution_id,
                                    locking=True)
            if execution._deployment_fk:
                deployment = execution.deployment
            else:
                deployment = None
            deployment_storage_id = execution._deployment_fk
            workflow_id = execution.workflow_id
            if not self._validate_execution_update(execution.status, status):
                raise manager_exceptions.InvalidExecutionUpdateStatus(
                    f"Invalid relationship - can't change status from "
                    f'{execution.status} to {status} for "{execution.id}" '
                    f'execution while running "{workflow_id}" workflow.')
            execution.status = status
            execution.error = error
            self._update_execution_group(execution)

            if status == ExecutionState.STARTED:
                execution.started_at = utils.get_formatted_timestamp()
                if deployment:
                    execution.deployment.deployment_status = \
                        DeploymentState.IN_PROGRESS
                    execution.deployment.latest_execution = execution
                    self.sm.update(deployment)

            if status in ExecutionState.END_STATES:
                execution.ended_at = utils.get_formatted_timestamp()

            execution = self.sm.update(execution)
            self.update_deployment_statuses(execution)
            self._send_hook(execution)
            res = execution.to_response()
            # do not use `execution` after this transaction ends, because it
            # would possibly require refetching the related objects, and by
            # then, the execution could've been deleted already
            del execution

        if status in ExecutionState.END_STATES:
            update_inter_deployment_dependencies(self.sm)
            self.start_queued_executions(deployment_storage_id)

        # If the execution is a deployment update, and the status we're
        # updating to is one which should cause the update to fail - do it here
        if workflow_id in ('update', 'csys_new_deployment_update') and \
                status in [ExecutionState.FAILED, ExecutionState.CANCELLED]:
            dep_update = self.sm.get(models.DeploymentUpdate, None,
                                     filters={'execution_id': execution_id})
            dep_update.state = UpdateStates.FAILED
            self.sm.update(dep_update)

        # Similarly for a plugin update
        if workflow_id == 'update_plugin' and \
                status in [ExecutionState.FAILED,
                           ExecutionState.CANCELLED]:
            plugin_update = self.sm.get(models.PluginsUpdate, None,
                                        filters={'execution_id': execution_id})
            if plugin_update:
                plugin_update.state = PluginsUpdateStates.FAILED
                self.sm.update(plugin_update)
            if plugin_update.blueprint:
                for dep_id in plugin_update.deployments_to_update:
                    dep = self.sm.get(models.Deployment, dep_id)
                    dep.blueprint = plugin_update.blueprint  # original bp
                    self.sm.update(dep)
            if plugin_update.temp_blueprint:
                # Delete the temporary blueprint
                if not plugin_update.temp_blueprint.deployments:
                    self.sm.delete(plugin_update.temp_blueprint)
                else:
                    plugin_update.temp_blueprint.is_hidden = False
                    self.sm.update(plugin_update.temp_blueprint)

        if workflow_id == 'delete_deployment_environment' and \
                status == ExecutionState.TERMINATED:
            # render the execution here, because immediately afterwards
            # we'll delete it, and then we won't be able to render it anymore
            self.delete_deployment(deployment)
        return res

    def start_queued_executions(self, deployment_storage_id):
        """Dequeue and start executions.

        Attempt to fetch and run as many executions as we can, and if
        any of those fail to run, try running more.
        """
        to_run = []
        while True:
            with self.sm.transaction():
                dequeued = self._get_queued_executions(deployment_storage_id)
                all_started = True
                for execution in dequeued:
                    refreshed, messages = self._refresh_execution(execution)
                    to_run.extend(messages)
                    all_started &= refreshed
                if all_started:
                    break
        workflow_executor.execute_workflow(to_run)

    def _refresh_execution(self, execution: models.Execution) -> (bool, list):
        """Prepare the execution to be started.

        Re-evaluate parameters, and return if the execution can run.
        """
        execution.status = ExecutionState.PENDING
        if not execution.deployment:
            return True, self._prepare_execution_or_log(execution)
        self.sm.refresh(execution.deployment)
        try:
            if execution and execution.deployment and \
                    execution.deployment.create_execution:
                create_execution = execution.deployment.create_execution
                delete_dep_env = 'delete_deployment_environment'
                if (create_execution.status == ExecutionState.FAILED and
                        execution.workflow_id != delete_dep_env):
                    raise RuntimeError('create_deployment_environment failed')

            execution.merge_workflow_parameters(
                execution.parameters,
                execution.deployment,
                execution.workflow_id
            )
            execution.get_workflow()  # try this here to fail early
        except Exception as e:
            execution.status = ExecutionState.FAILED
            execution.error = str(e)
            return False, []
        else:
            flag_modified(execution, 'parameters')
        finally:
            self.sm.update(execution)
            db.session.flush([execution])
        return True, self._prepare_execution_or_log(execution)

    def _prepare_execution_or_log(self, execution: models.Execution) -> list:
        try:
            return self.prepare_executions([execution], queue=True)
        except Exception as e:
            current_app.logger.warning(
                'Could not dequeue execution %s: %s',
                execution, e)
            return []

    def _get_queued_executions(self, deployment_storage_id):
        sort_by = {'created_at': 'asc'}
        system_executions = self.sm.list(
            models.Execution, filters={
                'status': ExecutionState.QUEUED_STATE,
                'is_system_workflow': True,
            },
            sort=sort_by,
            get_all_results=True,
            all_tenants=True,
            locking=True,
        ).items
        if system_executions:
            yield system_executions[0]
            return

        executions = aliased(models.Execution)
        queued_query = (
            db.session.query(executions)
            .filter_by(
                status=ExecutionState.QUEUED,
                is_system_workflow=False,
            )
            .filter(
                # fetch only execution belonging to deployments who have
                # no active executions
                ~models.Execution.query.filter(
                    models.Execution._deployment_fk == \
                    executions._deployment_fk,
                    models.Execution.status.in_(ExecutionState.ACTIVE_STATES)
                ).exists()
            )
        )
        if deployment_storage_id:
            queued_query = queued_query.order_by(
                executions._deployment_fk != deployment_storage_id
            )
        queued_executions = (
            queued_query
            .outerjoin(executions.execution_groups)
            .order_by(executions.created_at.asc())
            .limit(5)
            .with_for_update(of=executions)
            .all()
        )
        # deployments we've already emitted an execution for - only emit 1
        # execution per deployment
        seen_deployments = set()
        # {group: how many executions can it still run}
        group_can_run = {}
        for execution in queued_executions:
            for group in execution.execution_groups:
                if group not in group_can_run:
                    group_can_run[group] = group.concurrency -\
                        len(group.currently_running_executions())

            if any(group_can_run[g] <= 0 for g in execution.execution_groups):
                # this execution cannot run, because it would exceed one
                # of its' groups concurrency limit
                continue
            if execution._deployment_fk in seen_deployments:
                continue

            for group in execution.execution_groups:
                group_can_run[group] -= 1
            seen_deployments.add(execution._deployment_fk)
            yield execution

    def _validate_execution_update(self, current_status, future_status):
        if current_status in ExecutionState.END_STATES:
            return False

        invalid_cancel_statuses = ExecutionState.ACTIVE_STATES + [
            ExecutionState.TERMINATED]
        if all((current_status == ExecutionState.CANCELLING,
                future_status in invalid_cancel_statuses)):
            return False

        invalid_force_cancel_statuses = invalid_cancel_statuses + [
            ExecutionState.CANCELLING]
        if all((current_status == ExecutionState.FORCE_CANCELLING,
                future_status in invalid_force_cancel_statuses)):
            return False

        return True

    def _update_execution_group(self, execution: models.Execution):
        for execution_group in execution.execution_groups:
            event = models.Event(
                event_type="execution_state_change",
                reported_timestamp=utils.get_formatted_timestamp(),
                execution_group=execution_group,
                message=f"execution '{execution.id}' changed state "
                        f"to '{execution.status}'",
            )
            if execution.error:
                event.message += f" with error '{execution.error}'"
            self.sm.put(event)
            if execution.deployment:
                if execution.status == ExecutionState.TERMINATED and \
                        execution_group.success_group:
                    execution_group.success_group.deployments.append(
                        execution.deployment)
                if execution.status == ExecutionState.FAILED and \
                        execution_group.failed_group:
                    execution_group.failed_group.deployments.append(
                        execution.deployment)

    @staticmethod
    def _get_conf_for_snapshots_wf():
        config_instance = config.instance
        return {
            'file_server_root': config_instance.file_server_root,
            'created_status': SnapshotState.CREATED,
            'failed_status': SnapshotState.FAILED,
            'postgresql_bin_path': config_instance.postgresql_bin_path,
            'postgresql_username': config_instance.postgresql_username,
            'postgresql_password': config_instance.postgresql_password,
            'postgresql_db_name': config_instance.postgresql_db_name,
            'db_host': config.instance.db_host,
            'default_tenant_name': DEFAULT_TENANT_NAME,
            'snapshot_restore_threads':
                config_instance.snapshot_restore_threads
        }

    def create_snapshot_model(self,
                              snapshot_id,
                              status=SnapshotState.CREATING):
        now = utils.get_formatted_timestamp()
        visibility = VisibilityState.PRIVATE
        new_snapshot = models.Snapshot(id=snapshot_id,
                                       created_at=now,
                                       status=status,
                                       visibility=visibility,
                                       error='')
        return self.sm.put(new_snapshot)

    def create_snapshot(self,
                        snapshot_id,
                        include_credentials,
                        include_logs,
                        include_events,
                        bypass_maintenance,
                        queue):

        self.create_snapshot_model(snapshot_id)
        try:
            execution = models.Execution(
                workflow_id='create_snapshot',
                parameters={
                    'snapshot_id': snapshot_id,
                    'include_credentials': include_credentials,
                    'include_logs': include_logs,
                    'include_events': include_events,
                    'config': self._get_conf_for_snapshots_wf()
                },
                is_system_workflow=True,
                status=ExecutionState.PENDING,
            )
            self.sm.put(execution)
            return execution, self.prepare_executions(
                [execution],
                queue=queue,
                bypass_maintenance=bypass_maintenance)
        except manager_exceptions.ExistingRunningExecutionError:
            snapshot = self.sm.get(models.Snapshot, snapshot_id)
            self.sm.delete(snapshot)
            self.sm.delete(execution)
            raise

    def restore_snapshot(self,
                         snapshot_id,
                         force,
                         bypass_maintenance,
                         timeout,
                         restore_certificates,
                         no_reboot):
        # Throws error if no snapshot found
        snapshot = self.sm.get(models.Snapshot, snapshot_id)
        if snapshot.status == SnapshotState.FAILED:
            raise manager_exceptions.SnapshotActionError(
                'Failed snapshot cannot be restored'
            )

        execution = models.Execution(
            workflow_id='restore_snapshot',
            parameters={
                'snapshot_id': snapshot_id,
                'config': self._get_conf_for_snapshots_wf(),
                'force': force,
                'timeout': timeout,
                'restore_certificates': restore_certificates,
                'no_reboot': no_reboot,
                'premium_enabled': premium_enabled,
                'user_is_bootstrap_admin': current_user.is_bootstrap_admin
            },
            is_system_workflow=True,
            status=ExecutionState.PENDING,
        )
        self.sm.put(execution)
        return execution, self.prepare_executions(
            [execution],
            bypass_maintenance=bypass_maintenance)

    def _validate_plugin_yaml(self, plugin):
        """Is the plugin YAML file valid?"""

        with open(plugin.yaml_file_path()) as f:
            plugin_yaml = yaml.safe_load(f)

        plugins = plugin_yaml.get(constants.PLUGINS, {})
        if not plugins:
            raise manager_exceptions.InvalidPluginError(
                'Plugin YAML file must contain "plugins" key.'
            )
        for plugin_spec in plugins.values():
            if not plugin_spec.get(constants.PLUGIN_PACKAGE_NAME) == \
                    plugin.package_name:
                raise manager_exceptions.InvalidPluginError(
                    'Plugin package name in YAML file must '
                    'match plugin package name in Wagon archive. '
                    'YAML package name:{0},'
                    'Wagon package name:{1}'.format(plugin_spec.get(
                        constants.PLUGIN_PACKAGE_NAME), plugin.package_name)
                )
        return True

    def update_plugins(self, plugins_update,
                       no_changes_required=False,
                       auto_correct_types=False,
                       reevaluate_active_statuses=False):
        """Executes the plugin update workflow.

        :param plugins_update: a PluginUpdate object.
        :param no_changes_required: True if a fake execution should be created.
        :return: execution ID.
        """
        execution = models.Execution(
            workflow_id='update_plugin',
            parameters={
                'update_id': plugins_update.id,
                'deployments_to_update': plugins_update.deployments_to_update,
                'temp_blueprint_id': plugins_update.temp_blueprint_id,
                'force': plugins_update.forced,
                'auto_correct_types': auto_correct_types,
                'reevaluate_active_statuses': reevaluate_active_statuses,
            },
            status=ExecutionState.PENDING,
            is_system_workflow=True
        )
        if no_changes_required:
            execution.status = ExecutionState.TERMINATED
            self.sm.put(execution)
            return execution, []
        else:
            self.sm.put(execution)
            return execution, self.prepare_executions(
                [execution],
                allow_overlapping_running_wf=True)

    def remove_plugin(self, plugin_id, force):
        # Verify plugin exists and can be removed
        plugin = self.sm.get(models.Plugin, plugin_id)
        validate_global_modification(plugin)
        self._check_for_running_executions(
            self._active_system_wide_execution_filter(), queue=False)

        if not force:
            affected_blueprint_ids = []
            for b in self.sm.list(
                models.Blueprint,
                include=['id', 'plan'],
                filters={'state': BlueprintUploadState.UPLOADED},
                get_all_results=True,
            ):
                if any(plugin.package_name == p.get('package_name')
                       and plugin.package_version == p.get('package_version')
                       for p in self._blueprint_plugins(b)):
                    affected_blueprint_ids.append(b.id)
            if affected_blueprint_ids:
                raise manager_exceptions.PluginInUseError(
                    'Plugin "{0}" is currently in use in blueprints: {1}. '
                    'You can "force" plugin removal if needed.'.format(
                        plugin.id, ', '.join(affected_blueprint_ids)))
        workflow_executor.uninstall_plugin(plugin)

        # Remove from storage
        self.sm.delete(plugin)

        # Remove from file system
        archive_path = utils.get_plugin_archive_path(plugin_id,
                                                     plugin.archive_name)
        shutil.rmtree(os.path.dirname(archive_path), ignore_errors=True)

    @staticmethod
    def _blueprint_plugins(blueprint):
        return blueprint.plan[constants.WORKFLOW_PLUGINS_TO_INSTALL] + \
               blueprint.plan[constants.DEPLOYMENT_PLUGINS_TO_INSTALL] + \
               extract_host_agent_plugins_from_plan(blueprint.plan)

    def upload_blueprint(self, blueprint_id, app_file_name, blueprint_url,
                         file_server_root, validate_only=False, labels=None):
        execution = models.Execution(
            workflow_id='upload_blueprint',
            parameters={
                'blueprint_id': blueprint_id,
                'app_file_name': app_file_name,
                'url': blueprint_url,
                'file_server_root': file_server_root,
                'validate_only': validate_only,
                'labels': labels,
            },
            status=ExecutionState.PENDING,
        )
        self.sm.put(execution)
        messages = self.prepare_executions([execution])
        return execution, messages

    def publish_blueprint(self,
                          application_dir,
                          application_file_name,
                          resources_base,
                          blueprint_id,
                          private_resource,
                          visibility):
        plan = self.parse_plan(
            application_dir, application_file_name, resources_base)

        return self.publish_blueprint_from_plan(application_file_name,
                                                blueprint_id,
                                                plan,
                                                private_resource,
                                                visibility)

    def publish_blueprint_from_plan(self,
                                    application_file_name,
                                    blueprint_id,
                                    plan,
                                    private_resource,
                                    visibility,
                                    state=None):
        now = utils.get_formatted_timestamp()
        visibility = self.get_resource_visibility(models.Blueprint,
                                                  blueprint_id,
                                                  visibility,
                                                  private_resource)
        new_blueprint = models.Blueprint(
            plan=plan,
            id=blueprint_id,
            description=plan.get('description'),
            created_at=now,
            updated_at=now,
            main_file_name=application_file_name,
            visibility=visibility,
            state=state
        )
        return self.sm.put(new_blueprint)

    def validate_blueprint(self,
                           application_dir,
                           application_file_name,
                           resources_base):
        self.parse_plan(application_dir, application_file_name, resources_base)

    @staticmethod
    def parse_plan(application_dir, application_file_name, resources_base,
                   resolver_parameters=None):
        dsl_location = os.path.join(
            resources_base,
            application_dir,
            application_file_name
        )
        try:
            return tasks.parse_dsl(
                dsl_location,
                resources_base,
                **app_context.get_parser_context(
                    resolver_parameters=resolver_parameters)
            )
        except Exception as ex:
            raise manager_exceptions.DslParseException(str(ex))

    @staticmethod
    def _remove_folder(folder_name, blueprints_location):
        blueprint_folder = os.path.join(
            config.instance.file_server_root,
            blueprints_location,
            utils.current_tenant.name,
            folder_name.id)
        # Don't cry if the blueprint folder never got created
        if os.path.exists(blueprint_folder):
            shutil.rmtree(blueprint_folder)

    def delete_blueprint(self, blueprint_id, force, remove_files=True):
        blueprint = self.sm.get(models.Blueprint, blueprint_id)
        validate_global_modification(blueprint)

        if blueprint.state in BlueprintUploadState.FAILED_STATES:
            return self.sm.delete(blueprint)
        if (blueprint.state and not force and
                blueprint.state != BlueprintUploadState.UPLOADED):
            # don't allow deleting blueprints while still uploading,
            # so we don't leave a dirty file system
            raise manager_exceptions.InvalidBlueprintError(
                'Blueprint `{}` is still {}.'.format(blueprint.id,
                                                     blueprint.state))

        if not force:
            for b in self.sm.list(models.Blueprint,
                                  include=['id', 'plan', 'state'],
                                  get_all_results=True):
                # we can't know whether the blueprint's plan will use the
                # blueprint we try to delete, before we actually have a plan
                if b.state not in BlueprintUploadState.FAILED_STATES \
                        and b.plan \
                        and blueprint_id in \
                            b.plan.get(constants.IMPORTED_BLUEPRINTS, []):
                    raise manager_exceptions.BlueprintInUseError(
                        'Blueprint {} is currently in use. You can "force" '
                        'blueprint removal.'.format(blueprint_id))

        if len(blueprint.deployments) > 0:
            raise manager_exceptions.DependentExistsError(
                "Can't delete blueprint {0} - There exist "
                "deployments for this blueprint; Deployments ids: {1}"
                .format(blueprint_id,
                        ','.join(dep.id for dep in blueprint.deployments)))
        if remove_files:
            # Delete blueprint resources from file server
            self._remove_folder(
                folder_name=blueprint,
                blueprints_location=FILE_SERVER_BLUEPRINTS_FOLDER)
            self._remove_folder(
                folder_name=blueprint,
                blueprints_location=FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER)

        return self.sm.delete(blueprint)

    def retrieve_and_display_dependencies(self, deployment):
        dep_graph = RecursiveDeploymentDependencies(self.sm)
        excluded_ids = self._excluded_component_creator_ids(deployment)
        deployment_dependencies = \
            dep_graph.retrieve_and_display_dependencies(
                deployment.id,
                excluded_component_creator_ids=excluded_ids)

        if deployment.has_sub_deployments:
            dep_graph = RecursiveDeploymentLabelsDependencies(self.sm)
            labels_dependencies = \
                dep_graph.retrieve_and_display_dependencies(
                    deployment
                )
            if deployment_dependencies:
                deployment_dependencies = deployment_dependencies\
                                          + labels_dependencies
            else:
                deployment_dependencies = labels_dependencies

        return deployment_dependencies

    def check_deployment_delete(self, deployment, force=False):
        """Check that deployment can be deleted"""
        executions = self.sm.list(models.Execution, filters={
            'deployment_id': deployment.id,
            'status': (
                ExecutionState.ACTIVE_STATES + ExecutionState.QUEUED_STATE
            )
        }, get_all_results=True)
        deployment_dependencies = self.retrieve_and_display_dependencies(
            deployment)
        if deployment_dependencies:
            if force:
                current_app.logger.warning(
                    "Force-deleting deployment %s despite having the "
                    "following existing dependent installations\n%s",
                    deployment.id, deployment_dependencies
                )
            else:
                raise manager_exceptions.DependentExistsError(
                    f"Can't delete deployment {deployment.id} - the following "
                    f"existing installations depend on it:\n"
                    f"{deployment_dependencies}"
                )
        if executions:
            running_ids = ','.join(
                execution.id for execution in executions
                if execution.status not in ExecutionState.END_STATES
            )
            raise manager_exceptions.DependentExistsError(
                f"Can't delete deployment {deployment.id} - There are "
                f"running or queued executions for this deployment. "
                f"Running executions ids: {running_ids}"
            )

        if not force:
            # validate either all nodes for this deployment are still
            # uninitialized or have been deleted
            node_instances = self.sm.list(models.NodeInstance, filters={
                'deployment_id': deployment.id,
                'state': lambda col: ~col.in_(['uninitialized', 'deleted']),
            }, include=['id'], get_all_results=True)
            if node_instances:
                raise manager_exceptions.DependentExistsError(
                    f"Can't delete deployment {deployment.id} - There are "
                    f"live nodes for this deployment. Live nodes ids: "
                    f"{ ','.join(ni.id for ni in node_instances) }"
                )

    def delete_deployment(self, deployment):
        """Delete the deployment.

        This is run when delete-dep-env finishes.
        """
        # check for external targets
        deployment_dependencies = self.sm.list(
            models.InterDeploymentDependencies,
            filters={'source_deployment': deployment})
        external_targets = set(
            json.dumps(dependency.external_target) for dependency in
            deployment_dependencies if dependency.external_target)
        if external_targets:
            self._clean_dependencies_from_external_targets(
                deployment, external_targets)

        parents = deployment.deployment_parents
        if parents:
            total_services, total_environments = \
                self._get_total_services_and_environments_from_sources(
                    [deployment]
                )
            dep_graph = RecursiveDeploymentLabelsDependencies(self.sm)
            dep_graph.create_dependencies_graph()
            dep_graph.decrease_deployment_counts_in_graph(
                parents,
                total_services,
                total_environments
            )
            for _parent in parents:
                _parent_obj = self.sm.get(
                    models.Deployment,
                    _parent,
                    fail_silently=True
                )
                if _parent_obj:
                    dep_graph.remove_dependency_from_graph(
                        deployment.id, _parent)
                    self._remove_deployment_label_dependency(
                        deployment,
                        _parent_obj
                    )
                    from_dependencies = self.sm.list(
                        models.DeploymentLabelsDependencies,
                        filters={'target_deployment_id': _parent_obj.id}
                    )
                    if not from_dependencies:
                        _parent_obj.sub_services_status = None
                        _parent_obj.sub_environments_status = None
                        _parent_obj.deployment_status = \
                            _parent_obj.evaluate_deployment_status()
                        self.sm.update(_parent_obj)
                    else:
                        dep_graph.propagate_deployment_statuses(_parent)

        deployment_folder = os.path.join(
            config.instance.file_server_root,
            FILE_SERVER_DEPLOYMENTS_FOLDER,
            utils.current_tenant.name,
            deployment.id)
        if os.path.exists(deployment_folder):
            shutil.rmtree(deployment_folder)

        self.sm.delete(deployment)

    def _clean_dependencies_from_external_targets(self,
                                                  deployment,
                                                  external_targets):
        manager_ips = [manager.private_ip for manager in self.sm.list(
            models.Manager)]
        external_source = {
            'deployment': deployment.id,
            'tenant': deployment.tenant_name,
            'host': manager_ips
        }
        for target in external_targets:
            target_client_config = json.loads(target)['client_config']
            external_client = CloudifyClient(**target_client_config)
            dep = external_client.inter_deployment_dependencies.list()
            dep_for_removal = [d for d in dep if
                               d['external_source'] == external_source]
            for d in dep_for_removal:
                external_client.inter_deployment_dependencies.delete(
                    dependency_creator=d['dependency_creator'],
                    source_deployment=d['source_deployment_id'] or ' ',
                    target_deployment=d['target_deployment_id'] or ' ',
                    external_source=external_source
                )

    def reset_operations(self, execution, force=False):
        """Resume the execution: restart failed operations.

        All operations that were failed are going to be retried,
        the execution itself is going to be set to pending again.
        Operations that were retried by another operation, will
        not be reset.
        """
        from_states = {
            cloudify_tasks.TASK_RESCHEDULED,
            cloudify_tasks.TASK_FAILED
        }
        if force:
            # with force, we resend all tasks which haven't finished yet
            from_states |= {
                cloudify_tasks.TASK_STARTED,
                cloudify_tasks.TASK_SENT,
                cloudify_tasks.TASK_SENDING,
            }

        tasks_graphs = self.sm.list(models.TasksGraph,
                                    filters={'execution': execution},
                                    get_all_results=True)
        for graph in tasks_graphs:
            operations = self.sm.list(models.Operation,
                                      filters={'tasks_graph': graph},
                                      get_all_results=True)
            retried_operations = set(
                op.parameters['retried_task']
                for op in operations
                if op.parameters.get('retried_task'))
            for operation in operations:
                if operation.id in retried_operations:
                    continue

                if operation.state in from_states:
                    operation.state = cloudify_tasks.TASK_PENDING
                    operation.parameters['current_retries'] = 0
                    self.sm.update(operation,
                                   modified_attrs=('parameters', 'state'))

    def resume_execution(self, execution_id, force=False):
        execution = self.sm.get(models.Execution, execution_id)
        if execution.status in {ExecutionState.CANCELLED,
                                ExecutionState.FAILED}:
            self.reset_operations(execution, force=force)
        elif force:
            raise manager_exceptions.ConflictError(
                'Cannot force-resume execution: `{0}` in state: `{1}`'
                .format(execution.id, execution.status))
        elif execution.status != ExecutionState.STARTED:
            # not force and not cancelled/failed/started - invalid:
            raise manager_exceptions.ConflictError(
                'Cannot resume execution: `{0}` in state: `{1}`'
                .format(execution.id, execution.status))

        execution.status = ExecutionState.PENDING
        execution.ended_at = None
        execution.resume = True
        message = execution.render_message(bypass_maintenance=False)
        db.session.commit()
        workflow_executor.execute_workflow([message])

        # Dealing with the inner Components' deployments
        components_executions = self._find_all_components_executions(
            execution.deployment_id)
        for exec_id in components_executions:
            execution = self.sm.get(models.Execution, exec_id)
            if execution.status in [ExecutionState.CANCELLED,
                                    ExecutionState.FAILED]:
                self.resume_execution(exec_id, force)

        return execution

    def get_component_executions(self, execution):
        workflow = execution.get_workflow()
        if not workflow.get('is_cascading', False):
            return []

        component_executions = []
        components_dep_ids = self._find_all_components_deployment_id(
            execution.deployment.id)

        for component_dep_id in components_dep_ids:
            dep = self.sm.get(models.Deployment, component_dep_id)
            component_execution = models.Execution(
                deployment=dep,
                workflow_id=execution.workflow_id,
                parameters=execution.parameters,
                allow_custom_parameters=execution.allow_custom_parameters,
                is_dry_run=execution.is_dry_run,
                creator=execution.creator,
                status=ExecutionState.PENDING,
            )
            self.sm.put(component_execution)
            component_executions.append(component_execution)
        return component_executions

    def prepare_executions(self, executions, *, force=False, queue=False,
                           bypass_maintenance=None, wait_after_fail=600,
                           allow_overlapping_running_wf=False,
                           commit=True):
        executions = list(executions)
        messages = []
        errors = []
        while executions:
            exc = executions.pop()
            exc.ensure_defaults()
            try:
                if exc.is_system_workflow:
                    if self._system_workflow_modifies_db(exc.workflow_id):
                        self.assert_no_snapshot_creation_running_or_queued(exc)
                elif exc.deployment:
                    self._check_allow_global_execution(exc.deployment)
                    self._verify_dependencies_not_affected(
                        exc.workflow_id, exc.deployment, force)
            except Exception as e:
                errors.append(e)
                exc.status = ExecutionState.FAILED
                exc.error = str(e)
                self.sm.update(exc)
                continue

            should_queue = queue
            if exc.is_system_workflow \
                    and exc.deployment is None \
                    and not allow_overlapping_running_wf:
                should_queue = self._check_for_running_executions(
                    self._any_active_executions_filter(exc), queue)
            elif not allow_overlapping_running_wf:
                should_queue = self.check_for_executions(
                    exc, force, queue)
            if should_queue:
                self._workflow_queued(exc)
                continue

            message = exc.render_message(
                wait_after_fail=wait_after_fail,
                bypass_maintenance=bypass_maintenance
            )
            exc.status = ExecutionState.PENDING
            messages.append(message)
            workflow = exc.get_workflow()
            if not workflow.get('is_cascading', False):
                continue
            component_executions = self.get_component_executions(exc)
            executions.extend(component_executions)
        if commit:
            db.session.commit()
        if errors:
            raise errors[0]
        return messages

    @staticmethod
    def _verify_workflow_in_deployment(wf_id, deployment, dep_id):
        if wf_id not in deployment.workflows:
            raise manager_exceptions.NonexistentWorkflowError(
                'Workflow {0} does not exist in deployment {1}'.format(
                    wf_id, dep_id))

    def check_for_executions(self, execution, force, queue):
        """Check if this execution should be queued.

        :param execution: the execution object
        :param force: allow running this execution in parallel with others
        :param queue: if the execution can't be run in parallel with others,
            and this is set, queue the execution. Otherwise, throw.
        """
        system_exec_running = self._check_for_running_executions(
            self._active_system_wide_execution_filter(), queue)
        if system_exec_running:
            return True
        if force:
            return system_exec_running
        if not execution.deployment or not execution.deployment._storage_id:
            return system_exec_running
        return self._check_for_active_executions(execution, queue)

    def _active_system_wide_execution_filter(self, *_):
        return {
            'is_system_workflow': [True],
            'status': ExecutionState.ACTIVE_STATES + [ExecutionState.QUEUED],
        }

    def _any_active_executions_filter(self, execution):
        return {
            'status': ExecutionState.ACTIVE_STATES,
            'id': lambda col: col != execution.id,
        }

    def _check_for_active_executions(self, execution, queue):
        def status_filter(col):
            if execution.created_at is not None:
                return sql_or(
                        col.in_(ExecutionState.ACTIVE_STATES),
                        sql_and(
                            col == ExecutionState.QUEUED,
                            models.Execution.created_at < execution.created_at
                        )
                    )
            else:
                return col.in_(
                    ExecutionState.ACTIVE_STATES + [ExecutionState.QUEUED]
                )

        running = self.list_executions(
            filters={
                'deployment': execution.deployment,
                'id': lambda col: col != execution.id,
                'status': status_filter
            },
            is_include_system_workflows=True
        ).items

        if not running:
            return False
        if queue or execution.scheduled_for:
            return True
        else:
            raise manager_exceptions.ExistingRunningExecutionError(
                f'The following executions are currently running for this '
                f'deployment: {running}. To execute this workflow anyway, '
                f'pass "force=true" as a query parameter to this request')

    def _check_for_running_executions(self, filters, queue):
        execution_ids = [
            e.id
            for e in self.list_executions(is_include_system_workflows=True,
                                          filters=filters,
                                          all_tenants=True,
                                          get_all_results=True).items
        ]
        if execution_ids and queue:
            return True
        elif execution_ids:
            raise manager_exceptions.ExistingRunningExecutionError(
                f'Cannot start execution because there are other executions '
                f'running: { ", ".join(execution_ids) }'
            )
        else:
            return False

    @staticmethod
    def _system_workflow_modifies_db(wf_id):
        """ Returns `True` if the workflow modifies the DB and
            needs to be blocked while a `create_snapshot` workflow
            is running or queued.
        """
        return wf_id == 'uninstall_plugin'

    def _retrieve_components_from_deployment(self, deployment_id_filter):
        return [node.id for node in
                self.sm.list(models.Node,
                             include=['type_hierarchy', 'id'],
                             filters=deployment_id_filter,
                             get_all_results=True)
                if 'cloudify.nodes.Component' in node.type_hierarchy]

    def _retrieve_all_components_dep_ids(self, components_ids, deployment_id):
        components_deployment_ids = []
        for component in components_ids:
            node_instance_filter = self.create_filters_dict(
                deployment_id=deployment_id, node_id=component)

            node_instance = self.sm.list(
                models.NodeInstance,
                filters=node_instance_filter,
                get_all_results=True,
                include=['runtime_properties',
                         'id']
            ).items[0]

            component_deployment_props = node_instance.runtime_properties.get(
                'deployment', {})

            # This runtime property is set when a Component node is starting
            # install workflow.
            component_deployment_id = component_deployment_props.get(
                'id', None)
            if component_deployment_id:
                components_deployment_ids.append(component_deployment_id)
        return components_deployment_ids

    def _retrieve_all_component_executions(self, components_deployment_ids):
        executions = []
        for deployment_id in components_deployment_ids:
            deployment_id_filter = self.create_filters_dict(
                deployment_id=deployment_id)

            # Getting the last execution associated with the Component's
            # deployment, which is the only one running now.
            executions.append([execution.id for execution
                               in self.sm.list(models.Execution,
                                               include=['id'],
                                               sort={'created_at': 'desc'},
                                               filters=deployment_id_filter,
                                               get_all_results=True)][0])
        return executions

    def _find_all_components_deployment_id(self, deployment_id):
        deployment_id_filter = self.create_filters_dict(
            deployment_id=deployment_id)
        components_node_ids = self._retrieve_components_from_deployment(
            deployment_id_filter)
        return self._retrieve_all_components_dep_ids(components_node_ids,
                                                     deployment_id)

    def _find_all_components_executions(self, deployment_id):
        components_deployment_ids = self._find_all_components_deployment_id(
            deployment_id)
        return self._retrieve_all_component_executions(
            components_deployment_ids)

    def cancel_execution(self, execution_ids, force=False, kill=False):
        """
        Cancel an execution by its id

        If force is False (default), this method will request the
        executed workflow to gracefully terminate. It is up to the workflow
        to follow up on that request.
        If force is used, this method will request the abrupt and immediate
        termination of the executed workflow. This is valid for all
        workflows, regardless of whether they provide support for graceful
        termination or not.
        If kill is used, this method means that the process executing the
        workflow is forcefully stopped, even if it is stuck or unresponsive.

        Note that in either case, the execution is not yet cancelled upon
        returning from the method. Instead, it'll be in a 'cancelling' or
        'force_cancelling' status (as can be seen in models.Execution). Once
        the execution is truly stopped, it'll be in 'cancelled' status (unless
        force was not used and the executed workflow doesn't support
        graceful termination, in which case it might simply continue
        regardless and end up with a 'terminated' status)

        :param execution_id: The execution id
        :param force: A boolean describing whether to force cancellation
        :param kill: A boolean describing whether to kill cancellation
        :return: The updated execution object
        :rtype: models.Execution
        :raises manager_exceptions.IllegalActionError
        """
        def _validate_cancel_execution(_execution: models.Execution,
                                       _kill_execution: bool,
                                       _force_execution: bool):
            if _kill_execution:
                return

            if _force_execution and \
                    _execution.status == ExecutionState.CANCELLING:
                return

            if _execution.status in (ExecutionState.PENDING,
                                     ExecutionState.STARTED,
                                     ExecutionState.SCHEDULED):
                return

            raise manager_exceptions.IllegalActionError(
                "Can't {0}cancel execution {1} because it's in "
                "status {2}".format('force-' if _force_execution else '',
                                    _execution.id, _execution.status))

        if kill:
            new_status = ExecutionState.KILL_CANCELLING
            force = True
        elif force:
            new_status = ExecutionState.FORCE_CANCELLING
        else:
            new_status = ExecutionState.CANCELLING

        if not isinstance(execution_ids, list):
            execution_ids = [execution_ids]

        # Prepare a dict of execution storage_id:(kill_execution, execution_id)
        # int-tuple pairs for executions to be cancelled.
        execution_storage_id_kill = {}
        with self.sm.transaction():
            executions = self.sm.list(models.Execution,
                                      filters={'id': lambda col:
                                               col.in_(execution_ids)})
            if len(executions) > 0:
                executions = executions.items
            else:
                raise manager_exceptions.NotFoundError(
                    f"Requested `Execution` {execution_ids} was not found")
            result = None
            while executions:
                execution = executions.pop()
                kill_execution, force_execution = kill, force
                # When a user cancels queued execution automatically
                # use the kill flag
                if execution.status in (ExecutionState.QUEUED,
                                        ExecutionState.SCHEDULED):
                    kill_execution, force_execution = True, True
                _validate_cancel_execution(execution,
                                           kill_execution, force_execution)
                execution_storage_id_kill[execution._storage_id] = \
                    kill_execution, execution.id

                # Dealing with the inner Components' deployments
                components_executions = self._find_all_components_executions(
                    execution.deployment_id)
                for exec_id in components_executions:
                    component_execution = self.sm.get(models.Execution,
                                                      exec_id)
                    if component_execution.status not in \
                            ExecutionState.END_STATES:
                        executions.append(component_execution)
                result = execution

        # Do the cancelling for a list of DB-transaction-locked executions.
        with self.sm.transaction():
            for execution in self.sm.list(
                    models.Execution, locking=True,
                    filters={'_storage_id': lambda col:
                             col.in_(execution_storage_id_kill.keys())}):
                execution.status = new_status
                execution.error = ''
                execution = self.sm.update(execution)
                if execution.deployment_id:
                    dep = execution.deployment
                    dep.latest_execution = execution
                    dep.deployment_status = \
                        dep.evaluate_deployment_status()
                    self.sm.update(dep)
                result = execution

        # Kill workflow executors if kill-cancelling
        workflow_executor.cancel_execution(
            [execution_id for storage_id, (kill_execution, execution_id)
             in execution_storage_id_kill.items() if kill_execution])

        return result

    @staticmethod
    def prepare_deployment_for_storage(deployment_id, deployment_plan):
        now = utils.get_formatted_timestamp()
        return models.Deployment(
            id=deployment_id,
            created_at=now,
            updated_at=now,
            description=deployment_plan['description'],
            workflows=deployment_plan['workflows'],
            inputs=deployment_plan['inputs'],
            policy_types=deployment_plan['policy_types'],
            policy_triggers=deployment_plan['policy_triggers'],
            groups=deployment_plan['groups'],
            scaling_groups=deployment_plan['scaling_groups'],
            outputs=deployment_plan['outputs'],
            capabilities=deployment_plan.get('capabilities', {})
        )

    def prepare_deployment_nodes_for_storage(self,
                                             deployment_plan,
                                             node_ids=None):
        """
        create deployment nodes in storage based on a provided blueprint
        :param deployment_plan: deployment_plan
        :param node_ids: optionally create only nodes with these ids
        """
        node_ids = node_ids or []
        if not isinstance(node_ids, list):
            node_ids = [node_ids]

        raw_nodes = deployment_plan['nodes']
        if node_ids:
            raw_nodes = \
                [node for node in raw_nodes if node['id'] in node_ids]
        nodes = []
        for raw_node in raw_nodes:
            scalable = raw_node['capabilities']['scalable']['properties']
            nodes.append(models.Node(
                id=raw_node['name'],
                type=raw_node['type'],
                type_hierarchy=raw_node['type_hierarchy'],
                number_of_instances=scalable['current_instances'],
                planned_number_of_instances=scalable['current_instances'],
                deploy_number_of_instances=scalable['default_instances'],
                min_number_of_instances=scalable['min_instances'],
                max_number_of_instances=scalable['max_instances'],
                host_id=raw_node['host_id'] if 'host_id' in raw_node else None,
                properties=raw_node['properties'],
                operations=raw_node['operations'],
                plugins=raw_node['plugins'],
                plugins_to_install=raw_node.get('plugins_to_install'),
                relationships=self._prepare_node_relationships(raw_node)))
        return nodes

    def _prepare_deployment_node_instances_for_storage(self,
                                                       deployment_id,
                                                       dsl_node_instances):

        # The index is the index of a node instance list for a
        # node. It is used for serial operations on node instances of the
        # same node. First we get the list of current node instances for the
        # deployment.
        deployment_id_filter = self.create_filters_dict(
            deployment_id=deployment_id)
        all_deployment_node_instances = self.sm.list(
            models.NodeInstance,
            filters=deployment_id_filter,
            get_all_results=True
        )
        # We build a dictionary in order to track the current index.
        current_node_index = defaultdict(int)
        for ni in all_deployment_node_instances:
            if ni.index > current_node_index[ni.node_id]:
                current_node_index[ni.node_id] = ni.index

        node_instances = []
        for node_instance in dsl_node_instances:
            node = get_node(deployment_id, node_instance['node_id'])
            # Update current node index.
            index = node_instance.get(
                'index', current_node_index[node.id] + 1)
            current_node_index[node.id] = index
            instance_id = node_instance['id']
            scaling_groups = node_instance.get('scaling_groups', [])
            relationships = node_instance.get('relationships', [])
            host_id = node_instance.get('host_id')
            instance = models.NodeInstance(
                id=instance_id,
                host_id=host_id,
                index=index,
                relationships=relationships,
                state='uninitialized',
                runtime_properties={},
                version=None,
                scaling_groups=scaling_groups
            )
            instance.set_node(node)
            node_instances.append(instance)

        return node_instances

    def _create_deployment_nodes(self,
                                 deployment_id,
                                 plan,
                                 node_ids=None):
        nodes = self.prepare_deployment_nodes_for_storage(plan, node_ids)
        deployment = self.sm.get(models.Deployment, deployment_id)

        for node in nodes:
            node.set_deployment(deployment)
            self.sm.put(node)

    def _create_deployment_node_instances(self,
                                          deployment_id,
                                          dsl_node_instances):
        node_instances = self._prepare_deployment_node_instances_for_storage(
            deployment_id,
            dsl_node_instances)

        for node_instance in node_instances:
            self.sm.put(node_instance)

    def assert_no_snapshot_creation_running_or_queued(self, execution=None):
        """
        Make sure no 'create_snapshot' workflow is currently running or queued.
        We do this to avoid DB modifications during snapshot creation.
        """
        status = ExecutionState.ACTIVE_STATES + ExecutionState.QUEUED_STATE
        filters = {'status': status}
        if execution is not None:
            filters['id'] = lambda col: col != execution.id
        for e in self.list_executions(is_include_system_workflows=True,
                                      filters=filters,
                                      get_all_results=True).items:
            if e.workflow_id == 'create_snapshot':
                raise manager_exceptions.ExistingRunningExecutionError(
                    'You cannot start an execution that modifies DB state'
                    ' while a `create_snapshot` workflow is running or queued'
                    ' (snapshot id: {0})'.format(e.id))

    def cleanup_failed_deployment(self, deployment_id):
        """If create-dep-env failed, delete the deployment.

        This is so that it's possible to retry creating the deployment,
        if the user eg. provided invalid inputs.
        """
        dep = self.sm.get(models.Deployment, deployment_id, fail_silently=True)
        if not dep:
            return
        if len(dep.executions) != 1:
            return
        if dep.executions[0].workflow_id != 'create_deployment_environment':
            return
        create_env_execution = dep.executions[0]
        if create_env_execution.status == ExecutionState.FAILED:
            self.delete_deployment(dep)

    def create_deployment(self,
                          blueprint,
                          deployment_id,
                          private_resource,
                          visibility,
                          site=None,
                          runtime_only_evaluation=False,
                          display_name=None):
        verify_blueprint_uploaded_state(blueprint)
        visibility = self.get_resource_visibility(models.Deployment,
                                                  deployment_id,
                                                  visibility,
                                                  private_resource)
        if (visibility == VisibilityState.GLOBAL and
                blueprint.visibility != VisibilityState.GLOBAL):
            raise manager_exceptions.ForbiddenError(
                f"Can't create global deployment {deployment_id} because "
                f"blueprint {blueprint.id} is not global"
            )
        now = datetime.utcnow()
        display_name = display_name or deployment_id
        new_deployment = models.Deployment(
            id=deployment_id,
            display_name=display_name,
            created_at=now,
            updated_at=now,
        )
        new_deployment.runtime_only_evaluation = runtime_only_evaluation
        new_deployment.blueprint = blueprint
        new_deployment.visibility = visibility

        if site:
            validate_deployment_and_site_visibility(new_deployment, site)
            new_deployment.site = site

        self.sm.put(new_deployment)
        return new_deployment

    @staticmethod
    def get_deployment_parents_from_labels(labels):
        parents = []
        labels = labels or []
        for label_key, label_value in labels:
            if label_key == 'csys-obj-parent':
                parents.append(label_value)
        return parents

    def get_object_types_from_labels(self, labels):
        obj_types = set()
        for key, value in labels:
            if key == 'csys-obj-type' and value:
                obj_types.add(value)
        return obj_types

    def get_deployment_object_types_from_labels(self, resource, labels):
        labels_to_add = self.get_labels_to_create(resource, labels)
        labels_to_delete = self.get_labels_to_delete(resource, labels)
        created_types = self.get_object_types_from_labels(labels_to_add)
        delete_types = self.get_object_types_from_labels(
            [(label.key, label.value) for label in labels_to_delete]
        )
        return created_types, delete_types

    def get_missing_deployment_parents(self, parents):
        if not parents:
            return
        result = self.sm.list(
            models.Deployment,
            include=['id'],
            filters={'id': lambda col: col.in_(parents)}
        ).items
        _existing_parents = [_parent.id for _parent in result]
        missing_parents = set(parents) - set(_existing_parents)
        return missing_parents

    def verify_deployment_parents_existence(self, parents, resource_id,
                                            resource_type):
        missing_parents = self.get_missing_deployment_parents(parents)
        if missing_parents:
            raise manager_exceptions.DeploymentParentNotFound(
                '{0} {1}: is referencing deployments'
                ' using label `csys-obj-parent` that does not exist, '
                'make sure that deployment(s) {2} exist before creating '
                '{3}'.format(resource_type.capitalize(),
                             resource_id,
                             ','.join(missing_parents), resource_type)
            )

    def verify_attaching_deployment_to_parents(self, graph, parents, dep_id):
        self.verify_deployment_parents_existence(parents, dep_id, 'deployment')
        graph.assert_cyclic_dependencies_between_targets_and_source(
            parents, dep_id
        )

    def _place_deployment_label_dependency(self, source, target):
        self.sm.put(
            models.DeploymentLabelsDependencies(
                id=str(uuid.uuid4()),
                source_deployment=source,
                target_deployment=target,
            )
        )

    def _remove_deployment_label_dependency(self, source, target):
        dld = models.DeploymentLabelsDependencies.__table__
        db.session.execute(
            dld.delete()
            .where(
                sql_and(
                    dld.c._source_deployment == source._storage_id,
                    dld.c._target_deployment == target._storage_id,
                )
            )
        )

    def _insert_deployments_into_label_graph(self, graph, source, target_id):
        self._place_deployment_label_dependency(
            source,
            self.sm.get(models.Deployment, target_id)
        )
        graph.add_dependency_to_graph(source.id, target_id)

    def _remove_deployments_from_label_graph(self, graph, source, target):
        graph.remove_dependency_from_graph(source.id, target.id)
        self._remove_deployment_label_dependency(source, target)

    def _get_total_services_and_environments_from_sources(self, deployments):
        total_services = 0
        total_environments = 0
        for dep in deployments:
            dep_services = dep.sub_services_count
            dep_environments = dep.sub_environments_count
            if dep.is_environment:
                dep_environments = dep_environments + 1
            else:
                dep_services = dep_services + 1
            total_environments += dep_environments
            total_services += dep_services

        return total_services, total_environments

    def add_deployment_to_labels_graph(self, dep_graph, source, target_id):
        total_services, total_environments = \
            self._get_total_services_and_environments_from_sources([source])
        self._insert_deployments_into_label_graph(dep_graph, source, target_id)
        dep_graph.increase_deployment_counts_in_graph(
            [target_id],
            total_services,
            total_environments
        )
        dep_graph.propagate_deployment_statuses(target_id)

    def delete_deployment_from_labels_graph(self,
                                            dep_graph,
                                            source,
                                            target_id):
        total_services, total_environments = \
            self._get_total_services_and_environments_from_sources([source])
        dep_graph.decrease_deployment_counts_in_graph(
            [target_id],
            total_services,
            total_environments
        )
        target = self.sm.get(
                models.Deployment, target_id
            )
        self._remove_deployments_from_label_graph(dep_graph, source, target)
        dep_graph.propagate_deployment_statuses(target_id)

    def add_multiple_deployments_to_labels_graph(self,
                                                 graph,
                                                 sources,
                                                 target_ids):
        total_services, total_environments = \
            self._get_total_services_and_environments_from_sources(sources)
        for target_id in target_ids:
            for source in sources:
                self._insert_deployments_into_label_graph(
                    graph, source, target_id
                )
        graph.increase_deployment_counts_in_graph(
            target_ids,
            total_services,
            total_environments
        )
        for target_id in target_ids:
            graph.propagate_deployment_statuses(target_id)

    def remove_multiple_deployments_from_labels_graph(self,
                                                      graph,
                                                      sources,
                                                      target_ids):
        total_services, total_environments = \
            self._get_total_services_and_environments_from_sources(sources)
        for target_id in target_ids:
            target = self.sm.get(models.Deployment, target_id)
            for source in sources:
                self._remove_deployments_from_label_graph(
                    graph, source, target
                )
        graph.decrease_deployment_counts_in_graph(
            target_ids,
            total_services,
            total_environments
        )
        for target_id in target_ids:
            graph.propagate_deployment_statuses(target_id)

    def handle_deployment_labels_graph(self, graph, parents, new_deployment):
        if not parents:
            return
        parents_to_add = parents.setdefault('parents_to_add', {})
        parents_to_remove = parents.setdefault('parents_to_remove', {})
        for parent in parents_to_add:
            self.add_deployment_to_labels_graph(
                graph,
                new_deployment,
                parent
            )
        for parent in parents_to_remove:
            self.delete_deployment_from_labels_graph(
                graph,
                new_deployment,
                parent
            )

    @staticmethod
    def update_resource_counts_after_source_conversion(graph,
                                                       resource,
                                                       new_types,
                                                       deleted_types):
        if not resource:
            return False
        is_converted = False
        if resource.deployment_parents and (deleted_types or new_types):
            if not graph.graph:
                graph.create_dependencies_graph()
            to_srv = resource.is_environment and 'environment' in deleted_types
            to_env = not resource.is_environment and 'environment' in new_types
            _type = 'service' if to_srv else 'environment' if to_env else None
            if _type:
                graph.update_deployment_counts_after_source_conversion(
                    resource, _type
                )
                is_converted = True
        return is_converted

    def install_plugin(self, plugin, manager_names=None, agent_names=None):
        """Send the plugin install task to the given managers or agents."""
        if manager_names:
            managers = self.sm.list(
                models.Manager, filters={'hostname': manager_names})
            existing_manager_names = {m.hostname for m in managers}
            if existing_manager_names != set(manager_names):
                missing_managers = set(manager_names) - existing_manager_names
                raise manager_exceptions.NotFoundError(
                    "Cannot install: requested managers do not exist: {0}"
                    .format(', '.join(missing_managers)))

            for name in existing_manager_names:
                manager = self.sm.get(
                    models.Manager, None, filters={'hostname': name})
                self.set_plugin_state(plugin, manager=manager,
                                      state=PluginInstallationState.PENDING)

        if agent_names:
            agents = self.sm.list(models.Agent, filters={'name': agent_names})
            existing_agent_names = {a.name for a in agents}
            if existing_agent_names != set(agent_names):
                missing_agents = set(agent_names) - existing_agent_names
                raise manager_exceptions.NotFoundError(
                    "Cannot install: requested agents do not exist: {0}"
                    .format(', '.join(missing_agents)))

            for name in existing_agent_names:
                agent = self.sm.get(models.Agent, None, filters={'name': name})
                self.set_plugin_state(plugin, agent=agent,
                                      state=PluginInstallationState.PENDING)

        if agent_names or manager_names:
            workflow_executor.install_plugin(plugin)
        return plugin

    def set_plugin_state(self, plugin, state,
                         manager=None, agent=None, error=None):
        filters = {
            '_plugin_fk': plugin._storage_id,
            '_agent_fk': agent._storage_id if agent else None,
            '_manager_fk': manager.id if manager else None
        }
        pstate = self.sm.get(models._PluginState, None, filters=filters,
                             fail_silently=True)
        if pstate is None:
            pstate = models._PluginState(state=state, error=error, **filters)
            self.sm.put(pstate)
        else:
            pstate.state = state
            pstate.error = error
            self.sm.update(pstate)

    def check_blueprint_plugins_installed(self, plan):
        plugins_list = plan.get(constants.DEPLOYMENT_PLUGINS_TO_INSTALL, [])
        # validate that all central-deployment plugins are installed
        for plugin in plugins_list:
            self.validate_plugin_is_installed(plugin)

        # validate that all host_agent plugins are installed
        host_agent_plugins = extract_host_agent_plugins_from_plan(plan)
        for plugin in host_agent_plugins:
            self.validate_plugin_is_installed(plugin)

    def validate_plugin_is_installed(self, plugin):
        """
        This method checks if a plugin is already installed on the manager,
        if not - raises an appropriate exception.
        :param plugin: A plugin from the blueprint
        """

        if plugin['package_name'] == 'cloudify-diamond-plugin':
            # It is meaningless to validate whether the diamond plugin is
            # installed on the manager because it is an agent-only plugin.
            # The name is hardcoded because it is currently the only plugin
            # of its type but this check should be improved if that changes.
            return

        if not plugin['install']:
            return
        query_parameters = {'package_name': plugin['package_name']}
        if plugin['package_version']:
            query_parameters['package_version'] = plugin['package_version']
        if plugin['distribution']:
            query_parameters['distribution'] = plugin['distribution']
        if plugin['distribution_version']:
            query_parameters['distribution_version'] =\
                plugin['distribution_version']
        if plugin['distribution_release']:
            query_parameters['distribution_release'] =\
                plugin['distribution_release']
        if plugin['supported_platform']:
            query_parameters['supported_platform'] =\
                plugin['supported_platform']

        result = self.sm.list(models.Plugin, filters=query_parameters)
        if result.metadata['pagination']['total'] == 0:
            raise manager_exceptions.\
                DeploymentPluginNotFound(
                    'Required plugin {}, version {} is not installed '
                    'on the manager'.format(
                        plugin['package_name'],
                        plugin['package_version'] or '`any`'))

    def start_deployment_modification(self,
                                      deployment_id,
                                      modified_nodes,
                                      context):
        deployment = self.sm.get(models.Deployment, deployment_id)

        deployment_id_filter = self.create_filters_dict(
            deployment_id=deployment_id)
        existing_modifications = self.sm.list(
            models.DeploymentModification,
            include=['id', 'status'],
            filters=deployment_id_filter
        )
        active_modifications = [
            m.id for m in existing_modifications
            if m.status == DeploymentModificationState.STARTED]
        if active_modifications:
            raise \
                manager_exceptions.ExistingStartedDeploymentModificationError(
                    'Cannot start deployment modification while there are '
                    'existing started deployment modifications. Currently '
                    'started deployment modifications: {0}'
                    .format(active_modifications))

        # We need to store the pre-modification state here so that it can be
        # used to roll back correctly on error.
        # We have to deepcopy it because it contains a lot of mutable children
        # which will then (sometimes) be modified by the other methods and
        # result in a rollback that breaks the deployment and snapshots.
        pre_modification = [
            deepcopy(instance.to_dict()) for instance in
            self.sm.list(models.NodeInstance,
                         filters=deployment_id_filter,
                         get_all_results=True)]

        nodes = [node.to_dict() for node
                 in self.sm.list(models.Node, filters=deployment_id_filter,
                                 get_all_results=True)]
        node_instances = [instance.to_dict() for instance
                          in self.sm.list(models.NodeInstance,
                                          filters=deployment_id_filter,
                                          get_all_results=True)]

        node_instances_modification = tasks.modify_deployment(
            nodes=nodes,
            previous_nodes=nodes,
            previous_node_instances=node_instances,
            modified_nodes=modified_nodes,
            scaling_groups=deployment.scaling_groups)
        node_instances_modification['before_modification'] = pre_modification

        now = utils.get_formatted_timestamp()
        modification_id = str(uuid.uuid4())
        modification = models.DeploymentModification(
            id=modification_id,
            created_at=now,
            ended_at=None,
            status=DeploymentModificationState.STARTED,
            modified_nodes=modified_nodes,
            node_instances=node_instances_modification,
            context=context)
        modification.set_deployment(deployment)
        self.sm.put(modification)

        scaling_groups = deepcopy(deployment.scaling_groups)
        for node_id, modified_node in modified_nodes.items():
            if node_id in deployment.scaling_groups:
                scaling_groups[node_id]['properties'].update({
                    'planned_instances': modified_node['instances']
                })
                deployment.scaling_groups = scaling_groups
            else:
                node = get_node(modification.deployment_id, node_id)
                node.planned_number_of_instances = modified_node['instances']
                self.sm.update(node)
        self.sm.update(deployment)

        added_and_related = node_instances_modification['added_and_related']
        added_node_instances = []
        for node_instance in added_and_related:
            if node_instance.get('modification') == 'added':
                added_node_instances.append(node_instance)
            else:
                node = get_node(
                    deployment_id=deployment_id,
                    node_id=node_instance['node_id']
                )
                target_names = [r['target_id'] for r in node.relationships]
                current = self.sm.get(models.NodeInstance, node_instance['id'])
                current_relationship_groups = {
                    target_name: list(group)
                    for target_name, group in itertools.groupby(
                        current.relationships,
                        key=lambda r: r['target_name'])
                }
                new_relationship_groups = {
                    target_name: list(group)
                    for target_name, group in itertools.groupby(
                        node_instance['relationships'],
                        key=lambda r: r['target_name'])
                }
                new_relationships = []
                for target_name in target_names:
                    new_relationships += current_relationship_groups.get(
                        target_name, [])
                    new_relationships += new_relationship_groups.get(
                        target_name, [])
                instance = self.sm.get(
                    models.NodeInstance,
                    node_instance['id'],
                    locking=True
                )
                instance.relationships = deepcopy(new_relationships)
                instance.version += 1
                self.sm.update(instance)
        self._create_deployment_node_instances(deployment_id,
                                               added_node_instances)
        return modification

    def finish_deployment_modification(self, modification_id):
        modification = self.sm.get(
            models.DeploymentModification,
            modification_id
        )

        if modification.status in DeploymentModificationState.END_STATES:
            raise manager_exceptions.DeploymentModificationAlreadyEndedError(
                'Cannot finish deployment modification: {0}. It is already in'
                ' {1} status.'.format(modification_id,
                                      modification.status))
        deployment = self.sm.get(models.Deployment, modification.deployment_id)

        modified_nodes = modification.modified_nodes
        scaling_groups = deepcopy(deployment.scaling_groups)
        for node_id, modified_node in modified_nodes.items():
            if node_id in deployment.scaling_groups:
                scaling_groups[node_id]['properties'].update({
                    'current_instances': modified_node['instances']
                })
                deployment.scaling_groups = scaling_groups
            else:
                node = get_node(modification.deployment_id, node_id)
                node.number_of_instances = modified_node['instances']
                self.sm.update(node)
        self.sm.update(deployment)

        node_instances = modification.node_instances
        for node_instance_dict in node_instances['removed_and_related']:
            instance = self.sm.get(
                models.NodeInstance,
                node_instance_dict['id'],
                locking=True
            )
            if node_instance_dict.get('modification') == 'removed':
                self.sm.delete(instance)
            else:
                removed_relationship_target_ids = set(
                    [rel['target_id']
                     for rel in node_instance_dict['relationships']])

                new_relationships = [rel for rel in instance.relationships
                                     if rel['target_id']
                                     not in removed_relationship_target_ids]
                instance.relationships = deepcopy(new_relationships)
                instance.version += 1
                self.sm.update(instance)

        modification.status = DeploymentModificationState.FINISHED
        modification.ended_at = utils.get_formatted_timestamp()
        self.sm.update(modification)
        return modification

    def rollback_deployment_modification(self, modification_id):
        modification = self.sm.get(
            models.DeploymentModification,
            modification_id
        )

        if modification.status in DeploymentModificationState.END_STATES:
            raise manager_exceptions.DeploymentModificationAlreadyEndedError(
                'Cannot rollback deployment modification: {0}. It is already '
                'in {1} status.'.format(modification_id,
                                        modification.status))

        deployment = self.sm.get(models.Deployment, modification.deployment_id)

        deployment_id_filter = self.create_filters_dict(
            deployment_id=modification.deployment_id)
        node_instances = self.sm.list(
            models.NodeInstance,
            filters=deployment_id_filter,
            get_all_results=True
        )
        modified_instances = deepcopy(modification.node_instances)
        modified_instances['before_rollback'] = [
            instance.to_dict() for instance in node_instances]
        for instance in node_instances:
            self.sm.delete(instance)
        for instance_dict in modified_instances['before_modification']:
            self.add_node_instance_from_dict(instance_dict)
        nodes_num_instances = {
            node.id: node for node in self.sm.list(
                models.Node,
                filters=deployment_id_filter,
                include=['id', 'number_of_instances'],
                get_all_results=True)
        }

        scaling_groups = deepcopy(deployment.scaling_groups)
        for node_id, modified_node in modification.modified_nodes.items():
            if node_id in deployment.scaling_groups:
                props = scaling_groups[node_id]['properties']
                props['planned_instances'] = props['current_instances']
                deployment.scaling_groups = scaling_groups
            else:
                node = get_node(modification.deployment_id, node_id)
                node.planned_number_of_instances = nodes_num_instances[
                    node_id].number_of_instances
                self.sm.update(node)
        self.sm.update(deployment)

        modification.status = DeploymentModificationState.ROLLEDBACK
        modification.ended_at = utils.get_formatted_timestamp()
        modification.node_instances = modified_instances
        self.sm.update(modification)
        return modification

    def add_node_instance_from_dict(self, instance_dict):
        # Remove the IDs from the dict - they don't have comparable columns
        deployment_id = instance_dict.pop('deployment_id')
        node_id = instance_dict.pop('node_id')
        tenant_name = instance_dict.pop('tenant_name')
        created_by = instance_dict.pop('created_by')
        resource_availability = instance_dict.pop('resource_availability')
        private_resource = instance_dict.pop('private_resource')

        # Link the node instance object to to the node, and add it to the DB
        new_node_instance = models.NodeInstance(**instance_dict)
        node = get_node(deployment_id, node_id)
        new_node_instance.set_node(node)
        self.sm.put(new_node_instance)

        # Manually update version, because of how `version_id_col` works in
        # SQLAlchemy (it is set to 1 automatically)
        new_node_instance.version = instance_dict['version']
        self.sm.update(new_node_instance)

        # Return the IDs to the dict for later use
        instance_dict['deployment_id'] = deployment_id
        instance_dict['node_id'] = node_id
        instance_dict['tenant_name'] = tenant_name
        instance_dict['created_by'] = created_by

        # resource_availability and private_resource are deprecated.
        # For backwards compatibility - adding it to the response.
        instance_dict['resource_availability'] = resource_availability
        instance_dict['private_resource'] = private_resource

    def create_operation(self, id, name, dependencies,
                         parameters, type, graph_id=None,
                         graph_storage_id=None, state='pending'):
        # allow passing graph_storage_id directly as an optimization, so that
        # we don't need to query for the graph based on display id
        if (graph_id and graph_storage_id) or \
                (not graph_id and not graph_storage_id):
            raise ValueError(
                'Pass exactly one of graph_id and graph_storage_id')
        if graph_id:
            graph = self.sm.list(models.TasksGraph,
                                 filters={'id': graph_id},
                                 get_all_results=True,
                                 all_tenants=True)[0]
            graph_storage_id = graph._storage_id
        operation = models.Operation(
            id=id,
            name=name,
            _tasks_graph_fk=graph_storage_id,
            created_at=utils.get_formatted_timestamp(),
            state=state,
            dependencies=dependencies,
            parameters=parameters,
            type=type,
        )
        self.sm.put(operation)
        execution = graph.execution
        if execution.total_operations is None:
            execution.total_operations = 0
            execution.finished_operations = 0
        execution.total_operations += 1
        self.sm.update(
            execution,
            modified_attrs=('total_operations', 'finished_operations'))
        return operation

    def create_tasks_graph(self, name, execution_id, operations=None):
        execution = self.sm.list(models.Execution,
                                 filters={'id': execution_id},
                                 get_all_results=True,
                                 all_tenants=True)[0]
        graph = models.TasksGraph(
            name=name,
            _execution_fk=execution._storage_id,
            created_at=utils.get_formatted_timestamp(),
            _tenant_id=execution._tenant_id,
            _creator_id=execution._creator_id
        )
        db.session.add(graph)
        if operations:
            created_ops = []
            for operation in operations:
                operation.setdefault('state', 'pending')
                op = models.Operation(
                    tenant=utils.current_tenant,
                    creator=current_user,
                    tasks_graph=graph,
                    **operation)
                created_ops.append(op)
                db.session.add(op)
        if execution.total_operations is None:
            execution.total_operations = 0
            execution.finished_operations = 0
        if operations:
            execution.total_operations += sum(
                not op.is_nop
                for op in created_ops
            )
            execution.finished_operations += sum(
                not op.is_nop and op.state in TERMINATED_TASK_STATES
                for op in created_ops
            )
        self.sm.update(
            execution,
            modified_attrs=('total_operations', 'finished_operations'))
        return graph

    @staticmethod
    def _prepare_node_relationships(raw_node):
        if 'relationships' not in raw_node:
            return []
        prepared_relationships = []
        for raw_relationship in raw_node['relationships']:
            relationship = {
                'target_id': raw_relationship['target_id'],
                'type': raw_relationship['type'],
                'type_hierarchy': raw_relationship['type_hierarchy'],
                'properties': raw_relationship['properties'],
                'source_operations': raw_relationship['source_operations'],
                'target_operations': raw_relationship['target_operations'],
            }
            prepared_relationships.append(relationship)
        return prepared_relationships

    def verify_deployment_environment_created_successfully(self, deployment):
        if not deployment.create_execution:
            # the user removed the execution, let's assume they knew
            # what they were doing and allow this
            return
        status = deployment.create_execution.status
        if status == ExecutionState.TERMINATED:
            return
        elif status == ExecutionState.PENDING:
            raise manager_exceptions \
                .DeploymentEnvironmentCreationPendingError(
                    'Deployment environment creation is still pending, '
                    'try again in a minute')
        elif status == ExecutionState.STARTED:
            raise manager_exceptions\
                .DeploymentEnvironmentCreationInProgressError(
                    'Deployment environment creation is still in progress, '
                    'try again in a minute')
        elif status == ExecutionState.FAILED:
            error_line = deployment.create_execution.error\
                .strip().split('\n')[-1]
            raise manager_exceptions.DeploymentCreationError(
                "Can't launch executions since environment creation for "
                "deployment {0} has failed: {1}".format(
                    deployment.id, error_line))
        elif status in (
            ExecutionState.CANCELLED, ExecutionState.CANCELLING,
                ExecutionState.FORCE_CANCELLING):
            raise manager_exceptions.DeploymentCreationError(
                "Can't launch executions since the environment creation for "
                "deployment {0} has been cancelled [status={1}]".format(
                    deployment.id, status))
        else:
            raise manager_exceptions.DeploymentCreationError(
                'Unexpected deployment status for deployment {0} '
                '[status={1}]'.format(deployment.id, status))

    @staticmethod
    def create_filters_dict(**kwargs):
        filters = {}
        for key, val in kwargs.items():
            if val:
                filters[key] = val
        return filters or None

    @staticmethod
    def _get_only_user_execution_parameters(execution_parameters):
        return {k: v for k, v in execution_parameters.items()
                if not k.startswith('__')}

    def update_provider_context(self, update, context_dict):
        if update:
            context_instance = self.sm.get(
                models.ProviderContext,
                context_dict['id']
            )
        else:
            context_instance = models.ProviderContext(id=context_dict['id'])

        context_instance.name = context_dict['name']
        context_instance.context = context_dict['context']
        self.sm.update(context_instance)

        app_context.update_parser_context(context_dict['context'])

    def get_resource_visibility(self,
                                model_class,
                                resource_id,
                                visibility,
                                private_resource=None,
                                plugin_info=None):
        """
        Determine the visibility of the resource.

        :param model_class: SQL DB table class
        :param resource_id: The id of the resource
        :param visibility: The new parameter for the user to set the
                           visibility of the resource.
        :param private_resource: The old parameter the user used to set
                                 the visibility, kept for backwards
                                 compatibility and it will be deprecated soon
        :param plugin_info: In case the resource is a plugin,
                            it's package_name and archive_name
        :return: The visibility to set
        """

        # Validate we're not using the old parameter with new parameter
        if private_resource is not None and visibility:
            raise manager_exceptions.BadParametersError(
                "The `private_resource` and `visibility` "
                "parameters cannot be used together"
            )

        # Handle the old parameter
        if private_resource:
            return VisibilityState.PRIVATE

        # Validate that global visibility is permitted
        if visibility == VisibilityState.GLOBAL:
            self.validate_global_permitted(model_class,
                                           resource_id,
                                           create_resource=True,
                                           plugin_info=plugin_info)

        return visibility or VisibilityState.TENANT

    def set_deployment_visibility(self, deployment_id, visibility):
        deployment = self.sm.get(models.Deployment, deployment_id)
        blueprint = deployment.blueprint
        if utils.is_visibility_wider(visibility, blueprint.visibility):
            raise manager_exceptions.IllegalActionError(
                "The visibility of deployment `{0}` can't be wider than "
                "the visibility of its blueprint `{1}`. Current "
                "blueprint visibility is {2}".format(deployment.id,
                                                     blueprint.id,
                                                     blueprint.visibility)
            )
        return self.set_visibility(models.Deployment,
                                   deployment_id,
                                   visibility)

    def set_visibility(self, model_class, resource_id, visibility):
        resource = self.sm.get(model_class, resource_id)
        self.validate_visibility_value(model_class, resource, visibility)
        # Set the visibility
        resource.visibility = visibility
        resource.updated_at = utils.get_formatted_timestamp()
        return self.sm.update(resource)

    def validate_visibility_value(self, model_class, resource, new_visibility):
        current_visibility = resource.visibility
        if utils.is_visibility_wider(current_visibility, new_visibility):
            raise manager_exceptions.IllegalActionError(
                "Can't set the visibility of `{0}` to {1} because it "
                "already has wider visibility".format(resource.id,
                                                      new_visibility)
            )

        if new_visibility == VisibilityState.GLOBAL:
            plugin_info = None
            if model_class == models.Plugin:
                plugin_info = {'package_name': resource.package_name,
                               'archive_name': resource.archive_name}
            self.validate_global_permitted(model_class,
                                           resource.id,
                                           plugin_info=plugin_info)

    def validate_global_permitted(self,
                                  model_class,
                                  resource_id,
                                  create_resource=False,
                                  plugin_info=None):
        # Only admin is allowed to set a resource to global
        if not is_create_global_permitted(self.sm.current_tenant):
            raise manager_exceptions.ForbiddenError(
                'User `{0}` is not permitted to set or create a global '
                'resource'.format(current_user.username))

        if model_class == models.Plugin:
            archive_name = plugin_info['archive_name']
            unique_filter = {
                model_class.package_name: plugin_info['package_name'],
                model_class.archive_name: archive_name
            }
        else:
            unique_filter = {model_class.id: resource_id}

        # Check if the resource is unique
        max_resource_number = 0 if create_resource else 1
        if self.sm.count(model_class, unique_filter) > max_resource_number:
            raise manager_exceptions.IllegalActionError(
                "Can't set or create the resource `{0}`, it's visibility "
                "can't be global because it also exists in other tenants"
                .format(resource_id)
            )

    def _check_allow_global_execution(self, deployment):
        if (deployment.visibility == VisibilityState.GLOBAL and
                deployment.tenant != self.sm.current_tenant and
                not utils.can_execute_global_workflow(utils.current_tenant)):
            raise manager_exceptions.ForbiddenError(
                'User `{0}` is not allowed to execute workflows on '
                'a global deployment {1} from a different tenant'.format(
                    current_user.username, deployment.id
                )
            )

    def _verify_dependencies_not_affected(self,
                                          workflow_id, deployment, force):
        if workflow_id not in ['stop', 'uninstall', 'update']:
            return
        # if we're in the middle of an execution initiated by the component
        # creator, we'd like to drop the component dependency from the list
        deployment_dependencies = self.retrieve_and_display_dependencies(
            deployment
        )
        if not deployment_dependencies:
            return
        if force:
            current_app.logger.warning(
                "Force-executing workflow `{0}` on deployment {1} despite "
                "having the following existing dependent installations\n"
                "{2}".format(
                    workflow_id, deployment.id, deployment_dependencies
                ))
            return
        # If part of a deployment update - mark the update as failed
        if workflow_id == 'update':
            dep_update = self.sm.get(
                models.DeploymentUpdate,
                None,
                filters={'deployment_id': deployment.id,
                         'state': UpdateStates.UPDATING}
            )
            if dep_update:
                dep_update.state = UpdateStates.FAILED
                self.sm.update(dep_update)

        raise manager_exceptions.DependentExistsError(
            "Can't execute workflow `{0}` on deployment {1} - the "
            "following existing installations depend on it:\n{2}".format(
                workflow_id, deployment.id, deployment_dependencies
            )
        )

    def _excluded_component_creator_ids(self, deployment):
        # collect all deployment which created this deployment as a
        # component, accounting for nesting component creation
        component_creator_deployments = []
        component_deployment = deployment
        while True:
            creator_deployment = None
            for d in component_deployment.target_of_dependency_in:
                if 'component' in d.dependency_creator.split('.'):
                    creator_deployment = d.source_deployment
                    component_creator_deployments.append(creator_deployment)
                    component_deployment = creator_deployment
                    break  # a depl. can be a component for only one depl.
            if not creator_deployment:
                break

        active_component_creator_deployment_ids = []
        for deployment in component_creator_deployments:
            component_creator_executions = self.sm.list(
                models.Execution, filters={
                    'deployment_id': deployment.id,
                    'status': 'started',
                    'workflow_id': ['stop', 'uninstall', 'update']}
            )
            if component_creator_executions:
                active_component_creator_deployment_ids.append(deployment.id)

        return active_component_creator_deployment_ids

    def _workflow_queued(self, execution):
        execution.status = ExecutionState.QUEUED
        self.sm.update(execution)
        self._send_hook(execution)

    def _send_hook(self, execution):
        try:
            event_type = {
                ExecutionState.QUEUED: 'workflow_queued',
                ExecutionState.STARTED: 'workflow_started',
                ExecutionState.TERMINATED: 'workflow_succeeded',
                ExecutionState.FAILED: 'workflow_failed',
                ExecutionState.CANCELLED: 'workflow_cancelled',
            }[execution.status]
        except KeyError:
            return
        if execution.status == ExecutionState.STARTED:
            start_resume = 'Resuming' if execution.resume else 'Starting'
            dry_run = ' (dry run)' if execution.is_dry_run else ''
            message = (
                f"{start_resume} '{execution.workflow_id}' "
                f"workflow execution{dry_run}"
            )
        else:
            message = (
                f"'{execution.workflow_id}' workflow "
                f"execution {execution.status}"
            )
        message_context = {
            'message_type': 'hook',
            'is_system_workflow': execution.is_system_workflow,
            'blueprint_id': execution.blueprint_id,
            'deployment_id': execution.deployment_id,
            'execution_id': execution.id,
            'workflow_id': execution.workflow_id,
            'tenant_name': execution.tenant_name,
            'rest_token': execution.creator.get_auth_token(),
            'tenant': {
                'name': execution.tenant_name,
            }
        }

        if not execution.is_system_workflow:
            message_context['execution_parameters'] = execution.parameters

        event = {
            'type': 'cloudify_event',
            'event_type': event_type,
            'context': message_context,
            'message': {
                'text': message,
                'arguments': None
            }
        }

        send_event(event, 'hook')

    def update_resource_labels(self,
                               labels_resource_model,
                               resource,
                               new_labels):
        """
        Updating the resource labels.

        This function replaces the existing resource labels with the new labels
        that were passed in the request.
        If a new label already exists, it won't be created again.
        If an existing label is not in the new labels list, it will be deleted.
        """
        labels_to_create = self.get_labels_to_create(resource, new_labels)
        labels_to_delete = self.get_labels_to_delete(resource, new_labels)
        for label in labels_to_delete:
            self.sm.delete(label)
            if label in resource.labels:
                resource.labels.remove(label)

        self.create_resource_labels(labels_resource_model,
                                    resource,
                                    labels_to_create)

    @staticmethod
    def get_labels_to_create(resource, new_labels):
        new_labels_set = set(new_labels)
        existing_labels = resource.labels
        existing_labels_tup = set(
            (label.key, label.value) for label in existing_labels)

        return new_labels_set - existing_labels_tup

    @staticmethod
    def get_labels_to_delete(resource, new_labels):
        labels_to_delete = set()
        new_labels_set = set(new_labels)
        for label in resource.labels:
            if (label.key, label.value) not in new_labels_set:
                labels_to_delete.add(label)
        return labels_to_delete

    def create_resource_labels(self,
                               labels_resource_model,
                               resource,
                               labels_list):
        """
        Populate the resource_labels table.

        :param labels_resource_model: A labels resource model
        :param resource: A resource element
        :param labels_list: A list of labels of the form:
                            [(key1, value1), (key2, value2)]
        """
        if not labels_list:
            return

        current_time = datetime.utcnow()
        for key, value in labels_list:
            new_label = {'key': key,
                         'value': value,
                         'created_at': current_time,
                         'creator': current_user}
            if labels_resource_model == models.DeploymentLabel:
                new_label['deployment'] = resource
            elif labels_resource_model == models.BlueprintLabel:
                new_label['blueprint'] = resource
            elif labels_resource_model == models.DeploymentGroupLabel:
                new_label['deployment_group'] = resource

            self.sm.put(labels_resource_model(**new_label))

    def create_deployment_schedules(self, deployment, plan):
        plan_deployment_settings = plan.get('deployment_settings')
        if not plan_deployment_settings:
            return
        plan_schedules_dict = plan_deployment_settings.get('default_schedules')
        if not plan_schedules_dict:
            return
        self.create_deployment_schedules_from_dict(plan_schedules_dict,
                                                   deployment)

    def create_deployment_schedules_from_dict(self, schedules_dict, deployment,
                                              base_datetime=None):
        """
        :param schedules_dict: a dict of deployment schedules to create
        :param deployment: the deployment for which the schedules are created
        :param base_datetime: a datetime object representing the absolute date
            and time to which we apply relative time deltas.
            By default: UTC now.
        """
        for schedule_id, schedule in schedules_dict.items():
            workflow_id = schedule['workflow']
            execution_arguments = schedule.get('execution_arguments', {})
            parameters = schedule.get('workflow_parameters')
            self._verify_workflow_in_deployment(
                workflow_id, deployment, deployment.id)
            since = self._get_utc_datetime_from_sched_plan(schedule['since'],
                                                           base_datetime)
            until = schedule.get('until')
            if until:
                until = self._get_utc_datetime_from_sched_plan(until,
                                                               base_datetime)
            rule = compute_rule_from_scheduling_params({
                'rrule': schedule.get('rrule'),
                'recurrence': schedule.get('recurrence'),
                'weekdays': schedule.get('weekdays'),
                'count': schedule.get('count')
            })
            slip = schedule.get('slip', 0)
            stop_on_fail = schedule.get('stop_on_fail', False)
            enabled = schedule.get('default_enabled', True)
            now = get_formatted_timestamp()
            schedule = models.ExecutionSchedule(
                id=schedule_id,
                deployment=deployment,
                created_at=now,
                since=since,
                until=until,
                rule=rule,
                slip=slip,
                workflow_id=workflow_id,
                parameters=parameters,
                execution_arguments=execution_arguments,
                stop_on_fail=stop_on_fail,
                enabled=enabled,
            )
            schedule.next_occurrence = schedule.compute_next_occurrence()
            self.sm.put(schedule)

    @staticmethod
    def _get_utc_datetime_from_sched_plan(time_expression, base_datetime=None):
        """
        :param time_expression: Either a string representing an absolute
            datetime, or a relative time delta, such as '+4 hours' or '+1y+1d'.
        :param base_datetime: a datetime object representing the absolute date
            and time to which we apply the time delta. By default: UTC now
            (relevant only for relative time).
        :return: A naive datetime object, in UTC time.
        """
        time_fmt = '%Y-%m-%d %H:%M:%S'
        if time_expression.startswith('+'):
            base_datetime = base_datetime or datetime.utcnow()
            return parse_utc_datetime_relative(time_expression, base_datetime)
        return datetime.strptime(time_expression, time_fmt)


# What we need to access this manager in Flask
def get_resource_manager(sm=None):
    """
    Get the current app's resource manager, create if necessary
    """
    if sm:
        return ResourceManager(sm)
    return current_app.config.setdefault('resource_manager',
                                         ResourceManager())


def create_secret(key, secret, tenant):
    sm = get_storage_manager()
    timestamp = utils.get_formatted_timestamp()
    new_secret = models.Secret(
        id=key,
        value=encrypt(secret['value']),
        created_at=timestamp,
        updated_at=timestamp,
        visibility=secret['visibility'],
        is_hidden_value=secret['is_hidden_value'],
        tenant=tenant
    )
    created_secret = sm.put(new_secret)
    return created_secret


def update_secret(existing_secret, secret):
    existing_secret.value = encrypt(secret['value'])
    existing_secret.updated_at = utils.get_formatted_timestamp()
    return get_storage_manager().update(existing_secret, validate_global=True)


def update_imported_secret(existing_secret, imported_secret):
    existing_secret.is_hidden_value = imported_secret['is_hidden_value']
    existing_secret.visibility = imported_secret['visibility']
    update_secret(existing_secret, imported_secret)


def add_to_dict_values(dictionary, key, value):
    if key in dictionary:
        dictionary[key].append(value)
        return
    dictionary[key] = [value]
