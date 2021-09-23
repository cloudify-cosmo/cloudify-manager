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
from collections import defaultdict

from flask import current_app
from flask_security import current_user

from cloudify._compat import StringIO, text_type
from cloudify.cryptography_utils import encrypt
from cloudify.workflows import tasks as cloudify_tasks
from cloudify.models_states import (SnapshotState,
                                    ExecutionState,
                                    VisibilityState,
                                    BlueprintUploadState,
                                    DeploymentModificationState,
                                    PluginInstallationState)
from cloudify_rest_client.client import CloudifyClient

from dsl_parser import constants, tasks
from dsl_parser import exceptions as parser_exceptions
from dsl_parser.constants import INTER_DEPLOYMENT_FUNCTIONS

from manager_rest import premium_enabled
from manager_rest.constants import (DEFAULT_TENANT_NAME,
                                    FILE_SERVER_BLUEPRINTS_FOLDER,
                                    FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
                                    FILE_SERVER_DEPLOYMENTS_FOLDER)
from manager_rest.dsl_functions import get_secret_method
from manager_rest.utils import (send_event,
                                is_create_global_permitted,
                                validate_global_modification,
                                validate_deployment_and_site_visibility,
                                extract_host_agent_plugins_from_plan)
from manager_rest.plugins_update.constants import PLUGIN_UPDATE_WORKFLOW
from manager_rest.rest.rest_utils import (
    parse_datetime_string, RecursiveDeploymentDependencies,
    update_inter_deployment_dependencies,
    verify_blueprint_uploaded_state)
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
from .workflow_executor import generate_execution_token


class ResourceManager(object):

    def __init__(self, sm=None):
        self.sm = sm or get_storage_manager()
        self.task_mapping = _create_task_mapping()

    def list_executions(self, include=None, is_include_system_workflows=False,
                        filters=None, pagination=None, sort=None,
                        all_tenants=False, get_all_results=False):
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
            get_all_results=get_all_results
        )

    def update_execution_status(self, execution_id, status, error):
        execution = self.sm.get(models.Execution, execution_id)
        if not self._validate_execution_update(execution.status, status):
            raise manager_exceptions.InvalidExecutionUpdateStatus(
                'Invalid relationship - can\'t change status from {0} to {1}'
                ' for "{2}" execution while running "{3}" workflow.'
                .format(execution.status,
                        status,
                        execution.id,
                        execution.workflow_id))
        old_status = execution.status
        execution.status = status
        execution.error = error

        # Add `started_at` to scheduled execution that just started
        if (old_status == ExecutionState.SCHEDULED
                and status == ExecutionState.STARTED):
            execution.started_at = utils.get_formatted_timestamp()

        if status in ExecutionState.END_STATES:
            execution.ended_at = utils.get_formatted_timestamp()

        res = self.sm.update(execution)
        if status in ExecutionState.END_STATES:
            update_inter_deployment_dependencies(self.sm)
            self.start_queued_executions()

        # If the execution is a deployment update, and the status we're
        # updating to is one which should cause the update to fail - do it here
        if execution.workflow_id == 'update' and \
                status in [ExecutionState.FAILED, ExecutionState.CANCELLED]:
            dep_update = self.sm.get(models.DeploymentUpdate, None,
                                     filters={'execution_id': execution_id})
            if dep_update:
                dep_update.state = UpdateStates.FAILED
                self.sm.update(dep_update)

        # Similarly for a plugin update
        if execution.workflow_id == 'update_plugin' and \
                status in [ExecutionState.FAILED,
                           ExecutionState.CANCELLED]:
            plugin_update = self.sm.get(models.PluginsUpdate, None,
                                        filters={'execution_id': execution_id})
            if plugin_update:
                plugin_update.state = PluginsUpdateStates.FAILED
                self.sm.update(plugin_update)
                # Delete a temporary blueprint
                for dep_id in plugin_update.deployments_to_update:
                    dep = self.sm.get(models.Deployment, dep_id)
                    dep.blueprint = plugin_update.blueprint  # original bp
                    self.sm.update(dep)
                if not plugin_update.temp_blueprint.deployments:
                    self.sm.delete(plugin_update.temp_blueprint)
                else:
                    plugin_update.temp_blueprint.is_hidden = False
                    self.sm.update(plugin_update.temp_blueprint)

        if execution.workflow_id == 'delete_deployment_environment' and \
                status == ExecutionState.TERMINATED:
            # render the execution here, because immediately afterwards
            # we'll delete it, and then we won't be able to render it anymore
            res = res.to_response()
            self.delete_deployment(execution.deployment)
        return res

    def start_queued_executions(self):
        queued_executions = self._get_queued_executions()
        for e in queued_executions:
            self.execute_queued_workflow(e)
            if e.is_system_workflow:  # To avoid starvation of system workflows
                break

    def _get_queued_executions(self):
        filters = {'status': ExecutionState.QUEUED_STATE}

        queued_executions = self.list_executions(
            is_include_system_workflows=True,
            filters=filters,
            all_tenants=True,
            sort={'created_at': 'asc'}).items

        return queued_executions

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
            execution = self._execute_system_workflow(
                wf_id='create_snapshot',
                task_mapping='cloudify_system_workflows.snapshot.create',
                execution_parameters={
                    'snapshot_id': snapshot_id,
                    'include_credentials': include_credentials,
                    'include_logs': include_logs,
                    'include_events': include_events,
                    'config': self._get_conf_for_snapshots_wf()
                },
                bypass_maintenance=bypass_maintenance,
                queue=queue
            )
        except manager_exceptions.ExistingRunningExecutionError:
            snapshot = self.sm.get(models.Snapshot, snapshot_id)
            self.sm.delete(snapshot)
            raise

        return execution

    def restore_snapshot(self,
                         snapshot_id,
                         recreate_deployments_envs,
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

        execution = self._execute_system_workflow(
            wf_id='restore_snapshot',
            task_mapping='cloudify_system_workflows.snapshot.restore',
            execution_parameters={
                'snapshot_id': snapshot_id,
                'recreate_deployments_envs': recreate_deployments_envs,
                'config': self._get_conf_for_snapshots_wf(),
                'force': force,
                'timeout': timeout,
                'restore_certificates': restore_certificates,
                'no_reboot': no_reboot,
                'premium_enabled': premium_enabled,
                'user_is_bootstrap_admin': current_user.is_bootstrap_admin
            },
            bypass_maintenance=bypass_maintenance
        )
        return execution

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
        return self._execute_system_workflow(
            wf_id='update_plugin',
            task_mapping=PLUGIN_UPDATE_WORKFLOW,
            deployment=None,
            execution_parameters={
                'update_id': plugins_update.id,
                'deployments_to_update': plugins_update.deployments_to_update,
                'temp_blueprint_id': plugins_update.temp_blueprint_id,
                'force': plugins_update.forced,
                'auto_correct_types': auto_correct_types,
                'reevaluate_active_statuses': reevaluate_active_statuses,
            },
            verify_no_executions=False,
            fake_execution=no_changes_required)

    def remove_plugin(self, plugin_id, force):
        # Verify plugin exists and can be removed
        plugin = self.sm.get(models.Plugin, plugin_id)
        validate_global_modification(plugin)

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
                         file_server_root, validate_only=False):
        return self._execute_system_workflow(
            wf_id='upload_blueprint',
            task_mapping='cloudify_system_workflows.blueprint.upload',
            verify_no_executions=False,
            execution_parameters={
                'blueprint_id': blueprint_id,
                'app_file_name': app_file_name,
                'url': blueprint_url,
                'file_server_root': file_server_root,
                'validate_only': validate_only,
            },
        )

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
        self.parse_plan(
            application_dir, application_file_name, resources_base)

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
        shutil.rmtree(blueprint_folder)

    def delete_blueprint(self, blueprint_id, force, remove_files=True):
        blueprint = self.sm.get(models.Blueprint, blueprint_id)
        validate_global_modification(blueprint)

        if blueprint.state in BlueprintUploadState.FAILED_STATES:
            return self.sm.delete(blueprint)
        if (blueprint.state and
                blueprint.state != BlueprintUploadState.UPLOADED):
            # don't allow deleting blueprints while still uploading,
            # so we don't leave a dirty file system
            raise manager_exceptions.InvalidBlueprintError(
                'Blueprint `{}` is still {}.'.format(blueprint.id,
                                                     blueprint.state))

        if not force:
            imported_blueprints_list = []
            for b in self.sm.list(models.Blueprint,
                                  include=['id', 'plan', 'state'],
                                  get_all_results=True):
                # we can't know whether the blueprint's plan will use the
                # blueprint we try to delete, before we actually have a plan
                if b.state not in BlueprintUploadState.FAILED_STATES:
                    if b.plan:
                        imported_blueprints_list.append(
                            b.plan.get(constants.IMPORTED_BLUEPRINTS, []))
                    else:
                        raise manager_exceptions.BlueprintInUseError(
                            'Some blueprints have not yet finished parsing. '
                            'Please wait for them to finish and then try'
                            ' again.')

            for imported in imported_blueprints_list:
                if blueprint_id in imported:
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

    def delete_deployment_environment(self, deployment_id,
                                      bypass_maintenance=False, force=False,
                                      delete_logs=False):
        """Schedule deployment for deletion - delete environment.

        Do validations and send the delete-dep-env workflow. The deployment
        will be really actually deleted once that finishes.
        """
        # Verify deployment exists.
        deployment = self.sm.get(models.Deployment, deployment_id)

        # Validate there are no running executions for this deployment
        deployment_id_filter = self.create_filters_dict(
            deployment_id=deployment_id,
            status=ExecutionState.ACTIVE_STATES + ExecutionState.QUEUED_STATE
        )
        executions = self.sm.list(
            models.Execution,
            filters=deployment_id_filter
        )

        # Verify deleting the deployment won't affect dependent deployments
        dep_graph = RecursiveDeploymentDependencies(self.sm)
        excluded_ids = self._excluded_component_creator_ids(deployment)
        deployment_dependencies = \
            dep_graph.retrieve_and_display_dependencies(
                deployment.id,
                excluded_component_creator_ids=excluded_ids)
        if deployment_dependencies:
            if force:
                current_app.logger.warning(
                    "Force-deleting deployment {0} despite having the "
                    "following existing dependent installations\n{1}".format(
                        deployment.id, deployment_dependencies
                    ))
            else:
                raise manager_exceptions.DependentExistsError(
                    "Can't delete deployment {0} - the following existing "
                    "installations depend on it:\n{1}".format(
                        deployment_id, deployment_dependencies
                    )
                )

        if self._any_running_executions(executions):
            raise manager_exceptions.DependentExistsError(
                "Can't delete deployment {0} - There are running or queued "
                "executions for this deployment. Running executions ids: {1}"
                .format(
                    deployment_id,
                    ','.join([execution.id for execution in
                              executions if execution.status not
                              in ExecutionState.END_STATES])))
        if not force:
            deployment_id_filter = self.create_filters_dict(
                deployment_id=deployment_id)
            node_instances = self.sm.list(
                models.NodeInstance,
                filters=deployment_id_filter,
                get_all_results=True
            )
            # validate either all nodes for this deployment are still
            # uninitialized or have been deleted
            if any(node.state not in ('uninitialized', 'deleted') for node in
                   node_instances):
                raise manager_exceptions.DependentExistsError(
                    "Can't delete deployment {0} - There are live nodes for "
                    "this deployment. Live nodes ids: {1}"
                    .format(deployment_id,
                            ','.join([node.id for node in node_instances
                                     if node.state not in
                                     ('uninitialized', 'deleted')])))

        dep = self.sm.get(models.Deployment, deployment_id)

        deployment_env_deletion_task_name = \
            'cloudify_system_workflows.deployment_environment.delete'
        self._execute_system_workflow(
            wf_id='delete_deployment_environment',
            task_mapping=deployment_env_deletion_task_name,
            deployment=deployment,
            bypass_maintenance=bypass_maintenance,
            verify_no_executions=False,
            execution_parameters={
                'delete_logs': delete_logs
            })
        workflow_executor.delete_source_plugins(deployment.id)

        return dep

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

    def _reset_operations(self, execution, execution_token, from_states=None):
        """Force-resume the execution: restart failed operations.

        All operations that were failed are going to be retried,
        the execution itself is going to be set to pending again.
        Operations that were retried by another operation, will
        not be reset.

        :return: Whether to continue with running the execution
        """
        if from_states is None:
            from_states = {cloudify_tasks.TASK_RESCHEDULED,
                           cloudify_tasks.TASK_FAILED}
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
        execution_token = generate_execution_token(execution_id)
        if execution.status in {ExecutionState.CANCELLED,
                                ExecutionState.FAILED}:
            self._reset_operations(execution, execution_token)
            if force:
                # with force, we resend all tasks which haven't finished yet
                self._reset_operations(execution,
                                       execution_token,
                                       from_states={
                                           cloudify_tasks.TASK_STARTED,
                                           cloudify_tasks.TASK_SENT,
                                           cloudify_tasks.TASK_SENDING,
                                       })
        elif force:
            raise manager_exceptions.ConflictError(
                'Cannot force-resume execution: `{0}` in state: `{1}`'
                .format(execution.id, execution.status))
        elif execution.status != ExecutionState.STARTED:
            # not force and not cancelled/failed/started - invalid:
            raise manager_exceptions.ConflictError(
                'Cannot resume execution: `{0}` in state: `{1}`'
                .format(execution.id, execution.status))

        execution.status = ExecutionState.STARTED
        execution.ended_at = None
        self.sm.update(execution, modified_attrs=('status', 'ended_at'))

        workflow_id = execution.workflow_id
        deployment = execution.deployment
        blueprint = deployment.blueprint
        workflow_plugins = blueprint.plan[
            constants.WORKFLOW_PLUGINS_TO_INSTALL]
        workflow = deployment.workflows[workflow_id]

        workflow_executor.execute_workflow(
            workflow_id,
            workflow,
            workflow_plugins=workflow_plugins,
            blueprint_id=deployment.blueprint_id,
            deployment=deployment,
            execution_id=execution_id,
            execution_parameters=execution.parameters,
            bypass_maintenance=False,
            dry_run=False,
            resume=True,
            execution_creator=execution.creator,
            execution_token=execution_token
        )

        # Dealing with the inner Components' deployments
        components_executions = self._find_all_components_executions(
            execution.deployment_id)
        for exec_id in components_executions:
            execution = self.sm.get(models.Execution, exec_id)
            if execution.status in [ExecutionState.CANCELLED,
                                    ExecutionState.FAILED]:
                self.resume_execution(exec_id, force)

        return execution

    def requeue_execution(self, execution_id, force=False):
        execution = self.sm.get(models.Execution, execution_id)
        if execution.status != ExecutionState.SCHEDULED:
            raise manager_exceptions.ConflictError(
                'Cannot requeue execution: `{0}` in state: `{1}`'
                .format(execution.id, execution.status))

        workflow_id = execution.workflow_id
        deployment = execution.deployment
        blueprint = deployment.blueprint
        workflow_plugins = blueprint.plan[
            constants.WORKFLOW_PLUGINS_TO_INSTALL]
        workflow = deployment.workflows[workflow_id]
        execution_token = generate_execution_token(execution_id)

        workflow_executor.execute_workflow(
            workflow_id,
            workflow,
            workflow_plugins=workflow_plugins,
            blueprint_id=deployment.blueprint_id,
            deployment=deployment,
            execution_id=execution_id,
            execution_parameters=execution.parameters,
            bypass_maintenance=False,
            dry_run=False,
            resume=False,
            scheduled_time=parse_datetime_string(execution.scheduled_for),
            execution_creator=execution.creator,
            execution_token=execution_token
        )

        return execution

    @staticmethod
    def _set_execution_tenant(tenant_name):
        tenant = get_storage_manager().get(
            models.Tenant,
            tenant_name,
            filters={'name': tenant_name}
        )
        utils.set_current_tenant(tenant)

    def execute_workflow(self,
                         deployment_id,
                         workflow_id,
                         blueprint_id=None,
                         parameters=None,
                         allow_custom_parameters=False,
                         force=False,
                         bypass_maintenance=None,
                         dry_run=False,
                         queue=False,
                         execution=None,
                         wait_after_fail=600,
                         execution_creator=None,
                         scheduled_time=None,
                         allow_overlapping_running_wf=False):
        execution_creator = execution_creator or current_user
        deployment = self.sm.get(models.Deployment, deployment_id)
        self._validate_permitted_to_execute_global_workflow(deployment)
        blueprint_id = blueprint_id or deployment.blueprint_id
        blueprint = self.sm.get(models.Blueprint, blueprint_id)
        self._verify_workflow_in_deployment(workflow_id, deployment,
                                            deployment_id)
        self._verify_dependencies_not_affected(workflow_id, deployment, force)
        workflow = deployment.workflows[workflow_id]

        if execution:
            new_execution = execution
            execution_parameters = parameters
            execution_id = execution.id

        else:
            self._verify_deployment_environment_created_successfully(
                deployment_id)
            execution_parameters = \
                ResourceManager._merge_and_validate_execution_parameters(
                    workflow, workflow_id, parameters, allow_custom_parameters)

            execution_parameters = self._get_only_user_execution_parameters(
                execution_parameters)

            execution_id = str(uuid.uuid4())

        should_queue = queue
        if not allow_overlapping_running_wf:
            should_queue = self.check_for_executions(deployment_id,
                                                     force,
                                                     queue,
                                                     execution,
                                                     scheduled_time)
        if not execution:
            new_execution = models.Execution(
                id=execution_id,
                status=self._get_proper_status(should_queue, scheduled_time),
                created_at=utils.get_formatted_timestamp(),
                creator=execution_creator,
                workflow_id=workflow_id,
                error='',
                parameters=execution_parameters,
                is_system_workflow=False,
                is_dry_run=dry_run,
                scheduled_for=scheduled_time
            )

            new_execution.set_deployment(deployment, blueprint_id)
        if should_queue and not scheduled_time:
            # Scheduled executions are passed to rabbit, no need to break here
            self.sm.put(new_execution)
            self._workflow_queued(new_execution)
            return new_execution

        if scheduled_time:
            self.sm.put(new_execution)
        else:
            # This execution will start now (it's not scheduled for later)
            new_execution.status = ExecutionState.PENDING
            new_execution.started_at = utils.get_formatted_timestamp()
            self.sm.put(new_execution)

        # executing the user workflow
        workflow_plugins = blueprint.plan[
            constants.WORKFLOW_PLUGINS_TO_INSTALL]

        workflow_executor.execute_workflow(
            workflow_id,
            workflow,
            execution_creator=execution_creator,
            workflow_plugins=workflow_plugins,
            blueprint_id=deployment.blueprint_id,
            deployment=deployment,
            execution_id=execution_id,
            execution_parameters=execution_parameters,
            bypass_maintenance=bypass_maintenance,
            dry_run=dry_run,
            wait_after_fail=wait_after_fail,
            scheduled_time=scheduled_time)

        is_cascading_workflow = workflow.get('is_cascading', False)
        if is_cascading_workflow:
            components_dep_ids = self._find_all_components_deployment_id(
                deployment_id)

            for component_dep_id in components_dep_ids:
                self.execute_workflow(component_dep_id,
                                      workflow_id,
                                      None,
                                      parameters,
                                      allow_custom_parameters,
                                      force,
                                      bypass_maintenance,
                                      dry_run,
                                      queue,
                                      execution,
                                      wait_after_fail,
                                      execution_creator,
                                      scheduled_time)
        return new_execution

    @staticmethod
    def _should_use_system_workflow_executor(execution):
        """
        Both system and `regular` workflows are being de-queued, and each kind
        should be executed using a different executor function
        (`execute_system_workflow`/`execute_workflow`).
        * Deployment environment creation and deletion are considered
        system workflows

        """
        workflow_id = execution.workflow_id
        dep_env_workflows = ('create_deployment_environment',
                             'delete_deployment_environment')
        if workflow_id in dep_env_workflows or execution.is_system_workflow:
            return True
        return False

    def execute_queued_workflow(self, execution):
        """
        Whenever an execution is about to change to END status this function
        is called. Since the execution exists in the DB (it was created and
        then queued), we extract the needed information, set the correct user
        and re-run it with the correct workflow executor.
        :param execution: an execution DB object
        """
        current_tenant = utils.current_tenant._get_current_object()
        deployment = execution.deployment
        deployment_id = None
        if deployment:
            deployment_id = deployment.id
        workflow_id = execution.workflow_id
        execution_parameters = execution.parameters
        task_mapping = self.task_mapping.get(workflow_id)

        # Since this method is triggered by another execution we need to
        # make sure we use the correct user to execute the queued execution.
        # That is, the user that created the execution (instead of
        # `current_user` which we usually use)
        execution_creator = execution.creator
        self._set_execution_tenant(execution.tenant_name)
        if self._should_use_system_workflow_executor(execution):
            # Use `execute_system_workflow`
            self._execute_system_workflow(
                workflow_id, task_mapping, deployment=deployment,
                execution_parameters=execution_parameters, timeout=0,
                created_at=None, verify_no_executions=True,
                bypass_maintenance=None, update_execution_status=True,
                queue=True, execution=execution,
                execution_creator=execution_creator
            )

        else:  # Use `execute_workflow`
            self.execute_workflow(
                deployment_id, workflow_id, parameters=execution_parameters,
                allow_custom_parameters=False, force=False,
                bypass_maintenance=None, dry_run=False, queue=True,
                execution=execution, execution_creator=execution_creator
            )
        utils.set_current_tenant(current_tenant)

    @staticmethod
    def _get_proper_status(should_queue, scheduled=None):
        if scheduled:
            return ExecutionState.SCHEDULED

        elif should_queue:
            return ExecutionState.QUEUED

        return ExecutionState.PENDING

    @staticmethod
    def _verify_workflow_in_deployment(wf_id, deployment, dep_id):
        if wf_id not in deployment.workflows:
            raise manager_exceptions.NonexistentWorkflowError(
                'Workflow {0} does not exist in deployment {1}'.format(
                    wf_id, dep_id))

    def check_for_executions(self, deployment_id, force,
                             queue, execution, schedule=None):
        """
        :param deployment_id: The id of the deployment the workflow belongs to.
        :param force: If set, 2 executions under the same deployment can run
                together.
        :param queue: If set, in case an execution can't currently run it will
                be queued (instead of raising an exception).
        :param execution: An execution DB object, if exists it means this
                execution was de-queued.
        :param schedule: Whether or not this execution is scheduled to run in
                        the future
        If the `queue` flag is False and there are running executions an
        Exception will be raised
        """
        system_exec_running = self._check_for_active_system_wide_execution(
            queue, execution, schedule)
        execution_running = self._check_for_active_executions(
            deployment_id, force, queue, schedule)
        return system_exec_running or execution_running

    def _check_for_any_active_executions(self, queue):
        filters = {
            'status': ExecutionState.ACTIVE_STATES
        }
        executions = [
            e.id
            for e in self.list_executions(is_include_system_workflows=True,
                                          filters=filters,
                                          all_tenants=True,
                                          get_all_results=True).items
        ]
        should_queue = False
        # Execution can't currently run because other executions are running,
        # since `queue` flag is on - we will queue the execution and it will
        # run when possible
        if executions and queue:
            should_queue = True

        elif executions:
            raise manager_exceptions.ExistingRunningExecutionError(
                'You cannot start a system-wide execution if there are '
                'other executions running. '
                'Currently running executions: {0}'
                .format(executions))
        return should_queue

    def _check_for_active_system_wide_execution(self, queue,
                                                execution, scheduled):
        """
        If execution is passed (execution is de-queued) we only check for
        ACTIVE system executions.
        If execution is None (it's the first time this execution is trying to
        run) we check for ACTIVE and QUEUED executions.
        We do this to avoid starving executions.
        """

        status = ExecutionState.ACTIVE_STATES if execution else \
            ExecutionState.ACTIVE_STATES + ExecutionState.QUEUED_STATE
        filters = {
            'status': status
        }
        should_queue = False
        for e in self.list_executions(is_include_system_workflows=True,
                                      filters=filters,
                                      all_tenants=True,
                                      get_all_results=True).items:
            # When `queue` or `schedule` options are used no need to
            # raise an exception (the execution will run later)
            if e.deployment_id is None and (queue or scheduled):
                should_queue = True
                break
            elif e.deployment_id is None:
                raise manager_exceptions.ExistingRunningExecutionError(
                    'You cannot start an execution if there is a running '
                    'system-wide execution (id: {0})'
                    .format(e.id))

        return should_queue

    @staticmethod
    def _system_workflow_modifies_db(wf_id):
        """ Returns `True` if the workflow modifies the DB and
            needs to be blocked while a `create_snapshot` workflow
            is running or queued.
        """
        return wf_id in ('create_deployment_environment',
                         'delete_deployment_environment',
                         'uninstall_plugin')

    def _execute_system_workflow(self,
                                 wf_id,
                                 task_mapping,
                                 deployment=None,
                                 execution_parameters=None,
                                 created_at=None,
                                 verify_no_executions=True,
                                 bypass_maintenance=None,
                                 update_execution_status=True,
                                 queue=False,
                                 execution=None,
                                 execution_creator=None,
                                 fake_execution=False,
                                 **_):
        """
        :param deployment: deployment for workflow execution
        :param wf_id: workflow id
        :param task_mapping: mapping to the system workflow
        :param execution_parameters: parameters for the system workflow
        :param created_at: creation time for the workflow execution object.
         if omitted, a value will be generated by this method.
        :param bypass_maintenance: allows running the workflow despite having
        the manager maintenance mode activated.
        :param queue: If set, in case the execution is blocked it will be
        queued and automatically run when the blocking workflows are finished
        :param execution: an execution DB object. If it was passed it means
        this execution was queued and now trying to run again. If the execution
        can currently run it will, if not it will be queued again.
        :param fake_execution: True if a fake execution should be created,
        meaning an execution that never does anything and is initialized with
        the TERMINATED state.
        :return: (async task object, execution object)
        """
        execution_creator = execution_creator or current_user
        if execution:
            execution_id = execution.id
            is_system_workflow = execution.is_system_workflow

        else:
            # First time we try to execute this workflows,
            # we need all the details to create a DB object
            execution_id = str(uuid.uuid4())  # will also serve as the task id
            execution_parameters = execution_parameters or {}
            execution_parameters = self._get_only_user_execution_parameters(
                execution_parameters)
            # currently, deployment env creation/deletion are not set as
            # system workflows
            is_system_workflow = wf_id not in ('create_deployment_environment',
                                               'delete_deployment_environment',
                                               'upload_blueprint')

        should_queue = False
        if self._system_workflow_modifies_db(wf_id):
            self.assert_no_snapshot_creation_running_or_queued()

        if deployment is None and verify_no_executions:
            should_queue = self._check_for_any_active_executions(queue)

        if not execution:
            execution = models.Execution(
                id=execution_id,
                status=self._get_proper_status(should_queue),
                created_at=created_at or utils.get_formatted_timestamp(),
                creator=execution_creator,
                workflow_id=wf_id,
                error='',
                parameters=execution_parameters,
                is_system_workflow=is_system_workflow)

            if deployment:
                execution.set_deployment(deployment)

        if fake_execution:
            execution.status = ExecutionState.TERMINATED
            return self.sm.put(execution)

        # Execution can't currently run, it's queued and will run later
        if should_queue:
            self.sm.put(execution)
            self._workflow_queued(execution)
            return execution

        execution.status = ExecutionState.PENDING
        execution.started_at = utils.get_formatted_timestamp()
        self.sm.put(execution)
        workflow_executor.execute_system_workflow(
            wf_id=wf_id,
            task_id=execution_id,
            task_mapping=task_mapping,
            deployment=deployment,
            execution_parameters=execution_parameters,
            bypass_maintenance=bypass_maintenance,
            update_execution_status=update_execution_status,
            is_system_workflow=is_system_workflow,
            execution_creator=execution_creator
        )

        return execution

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

    def cancel_execution(self, execution_id, force=False, kill=False):
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
        if kill:
            force = True
        execution = self.sm.get(models.Execution, execution_id)
        # When a user cancels queued execution automatically use the kill flag
        if execution.status in (ExecutionState.QUEUED,
                                ExecutionState.SCHEDULED):
            kill = True
            force = True
        if execution.status not in (ExecutionState.PENDING,
                                    ExecutionState.STARTED,
                                    ExecutionState.SCHEDULED) and \
                (not force or execution.status != ExecutionState.CANCELLING)\
                and not kill:
            raise manager_exceptions.IllegalActionError(
                "Can't {0} cancel execution {1} because it's in status {2}"
                .format(
                    'kill-' if kill else 'force-' if force else '',
                    execution_id,
                    execution.status))

        if kill:
            new_status = ExecutionState.KILL_CANCELLING
        elif force:
            new_status = ExecutionState.FORCE_CANCELLING
        else:
            new_status = ExecutionState.CANCELLING
        execution.status = new_status
        execution.error = ''
        if kill:
            workflow_executor.cancel_execution(execution_id)

        # Dealing with the inner Components' deployments
        components_executions = self._find_all_components_executions(
            execution.deployment_id)
        for exec_id in components_executions:
            execution = self.sm.get(models.Execution, exec_id)
            if execution.status not in ExecutionState.END_STATES:
                self.cancel_execution(exec_id, force, kill)

        return self.sm.update(execution)

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

    def assert_no_snapshot_creation_running_or_queued(self):
        """
        Make sure no 'create_snapshot' workflow is currently running or queued.
        We do this to avoid DB modifications during snapshot creation.
        """
        status = ExecutionState.ACTIVE_STATES + ExecutionState.QUEUED_STATE
        filters = {'status': status}
        for e in self.list_executions(is_include_system_workflows=True,
                                      filters=filters,
                                      get_all_results=True).items:
            if e.workflow_id == 'create_snapshot':
                raise manager_exceptions.ExistingRunningExecutionError(
                    'You cannot start an execution that modifies DB state'
                    ' while a `create_snapshot` workflow is running or queued'
                    ' (snapshot id: {0})'.format(e.id))

    def create_deployment(self,
                          blueprint_id,
                          deployment_id,
                          private_resource,
                          visibility,
                          inputs=None,
                          bypass_maintenance=None,
                          skip_plugins_validation=False,
                          site_name=None,
                          runtime_only_evaluation=False,
                          labels=None):
        blueprint = self.sm.get(models.Blueprint, blueprint_id)
        verify_blueprint_uploaded_state(blueprint)
        plan = blueprint.plan
        site = self.sm.get(models.Site, site_name) if site_name else None

        try:
            deployment_plan = tasks.prepare_deployment_plan(
                plan, get_secret_method, inputs,
                runtime_only_evaluation=runtime_only_evaluation)
        except parser_exceptions.MissingRequiredInputError as e:
            raise manager_exceptions.MissingRequiredDeploymentInputError(
                str(e))
        except parser_exceptions.UnknownInputError as e:
            raise manager_exceptions.UnknownDeploymentInputError(str(e))
        except parser_exceptions.InputEvaluationError as e:
            raise manager_exceptions.DeploymentInputEvaluationError(str(e))
        except parser_exceptions.ConstraintException as e:
            raise manager_exceptions.ConstraintError(str(e))
        except parser_exceptions.UnknownSecretError as e:
            raise manager_exceptions.UnknownDeploymentSecretError(str(e))
        except parser_exceptions.UnsupportedGetSecretError as e:
            raise manager_exceptions.UnsupportedDeploymentGetSecretError(
                str(e))
        except parser_exceptions.DSLParsingException as e:
            raise manager_exceptions.DSLParsingException(str(e))

        #  validate plugins exists on manager when
        #  skip_plugins_validation is False
        if not skip_plugins_validation:
            plugins_list = deployment_plan.get(
                constants.DEPLOYMENT_PLUGINS_TO_INSTALL, [])
            # validate that all central-deployment plugins are installed
            for plugin in plugins_list:
                self.validate_plugin_is_installed(plugin)

            # validate that all host_agent plugins are installed
            host_agent_plugins = extract_host_agent_plugins_from_plan(
                deployment_plan)
            for plugin in host_agent_plugins:
                self.validate_plugin_is_installed(plugin)
        visibility = self.get_resource_visibility(models.Deployment,
                                                  deployment_id,
                                                  visibility,
                                                  private_resource)
        if (visibility == VisibilityState.GLOBAL and
                blueprint.visibility != VisibilityState.GLOBAL):
            raise manager_exceptions.ForbiddenError(
                "Can't create global deployment {0} because blueprint {1} "
                "is not global".format(deployment_id, blueprint_id)
            )
        new_deployment = self.prepare_deployment_for_storage(
            deployment_id,
            deployment_plan
        )
        new_deployment.runtime_only_evaluation = runtime_only_evaluation
        new_deployment.blueprint = blueprint
        new_deployment.visibility = visibility

        if site:
            validate_deployment_and_site_visibility(new_deployment, site)
            new_deployment.site = site

        self.sm.put(new_deployment)

        self._create_deployment_nodes(deployment_id, deployment_plan)

        self._create_deployment_node_instances(
            deployment_id,
            dsl_node_instances=deployment_plan['node_instances'])

        self._create_deployment_initial_dependencies(
            deployment_plan, new_deployment)

        self.create_deployment_labels(new_deployment, labels)

        try:
            self._create_deployment_environment(new_deployment,
                                                deployment_plan,
                                                bypass_maintenance)
        except manager_exceptions.ExistingRunningExecutionError as e:
            self.delete_deployment(new_deployment)
            raise e

        return new_deployment

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
        return operation

    def create_tasks_graph(self, name, execution_id, operations=None):
        execution = self.sm.list(models.Execution,
                                 filters={'id': execution_id},
                                 get_all_results=True,
                                 all_tenants=True)[0]
        graph = models.TasksGraph(
            id=uuid.uuid4().hex,
            name=name,
            _execution_fk=execution._storage_id,
            created_at=utils.get_formatted_timestamp(),
            _tenant_id=execution._tenant_id,
            _creator_id=execution._creator_id
        )
        self.sm.put(graph)
        if operations:
            created_at = utils.get_formatted_timestamp()
            for operation in operations:
                operation.setdefault('state', 'pending')
                op = models.Operation(
                    tenant=utils.current_tenant,
                    creator=current_user,
                    _tasks_graph_fk=graph._storage_id,
                    created_at=created_at,
                    **operation)
                db.session.add(op)
            self.sm._safe_commit()
        return graph

    @staticmethod
    def _try_convert_from_str(string, target_type):
        if target_type == text_type:
            return string
        if target_type == bool:
            if string.lower() == 'true':
                return True
            if string.lower() == 'false':
                return False
            return string
        try:
            return target_type(string)
        except ValueError:
            return string

    @classmethod
    def _merge_and_validate_execution_parameters(
            cls, workflow, workflow_name, execution_parameters=None,
            allow_custom_parameters=False):
        """
        merge parameters - parameters passed directly to execution request
        override workflow parameters from the original plan. any
        parameters without a default value in the blueprint must
        appear in the execution request parameters.
        Custom parameters will be passed to the workflow as well if allowed;
        Otherwise, an exception will be raised if such parameters are passed.
        """

        merged_execution_parameters = dict()
        workflow_parameters = workflow.get('parameters', dict())
        execution_parameters = execution_parameters or dict()

        missing_mandatory_parameters = set()

        allowed_types = {
            'integer': int,
            'float': float,
            'string': text_type,
            'boolean': bool
        }
        wrong_types = {}

        for param_name, param in workflow_parameters.items():

            if 'type' in param and param_name in execution_parameters:

                # check if need to convert from string
                if isinstance(execution_parameters[param_name], text_type) \
                        and param['type'] in allowed_types:
                    execution_parameters[param_name] = \
                        cls._try_convert_from_str(
                            execution_parameters[param_name],
                            allowed_types[param['type']])

                # validate type
                if not isinstance(execution_parameters[param_name],
                                  allowed_types.get(param['type'], object)):
                    wrong_types[param_name] = param['type']

            if 'default' not in param:
                # parameter without a default value - ensure one was
                # provided via execution parameters
                if param_name not in execution_parameters:
                    missing_mandatory_parameters.add(param_name)
                    continue

                merged_execution_parameters[param_name] = \
                    execution_parameters[param_name]
            else:
                merged_execution_parameters[param_name] = \
                    execution_parameters[param_name] if \
                    param_name in execution_parameters else param['default']

        if missing_mandatory_parameters:
            raise \
                manager_exceptions.IllegalExecutionParametersError(
                    'Workflow "{0}" must be provided with the following '
                    'parameters to execute: {1}'.format(
                        workflow_name, ','.join(missing_mandatory_parameters)))

        if wrong_types:
            error_message = StringIO()
            for param_name, param_type in wrong_types.items():
                error_message.write('Parameter "{0}" must be of type {1}\n'.
                                    format(param_name, param_type))
            raise manager_exceptions.IllegalExecutionParametersError(
                error_message.getvalue())

        custom_parameters = {k: v for k, v in execution_parameters.items()
                             if k not in workflow_parameters}

        if not allow_custom_parameters and custom_parameters:
            raise \
                manager_exceptions.IllegalExecutionParametersError(
                    'Workflow "{0}" does not have the following parameters '
                    'declared: {1}. Remove these parameters or use '
                    'the flag for allowing custom parameters'
                    .format(workflow_name, ','.join(custom_parameters.keys())))

        merged_execution_parameters.update(custom_parameters)
        return merged_execution_parameters

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

    def _verify_deployment_environment_created_successfully(self,
                                                            deployment_id):
        deployment_id_filter = self.create_filters_dict(
            deployment_id=deployment_id,
            workflow_id='create_deployment_environment')
        env_creation = next(
            (execution for execution in
             self.sm.list(models.Execution, filters=deployment_id_filter)
             if execution.workflow_id == 'create_deployment_environment'),
            None)

        if not env_creation:
            raise RuntimeError('Failed to find "create_deployment_environment"'
                               ' execution for deployment {0}'.format(
                                   deployment_id))
        status = env_creation.status
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
            raise RuntimeError(
                "Can't launch executions since environment creation for "
                "deployment {0} has failed: {1}".format(
                    deployment_id, env_creation.error))
        elif status in (
            ExecutionState.CANCELLED, ExecutionState.CANCELLING,
                ExecutionState.FORCE_CANCELLING):
            raise RuntimeError(
                "Can't launch executions since the environment creation for "
                "deployment {0} has been cancelled [status={1}]".format(
                    deployment_id, status))
        else:
            raise RuntimeError(
                'Unexpected deployment status for deployment {0} '
                '[status={1}]'.format(deployment_id, status))

    @staticmethod
    def create_filters_dict(**kwargs):
        filters = {}
        for key, val in kwargs.items():
            if val:
                filters[key] = val
        return filters or None

    def _create_deployment_environment(self,
                                       deployment,
                                       deployment_plan,
                                       bypass_maintenance):
        wf_id = 'create_deployment_environment'
        deployment_env_creation_task_name = \
            'cloudify_system_workflows.deployment_environment.create'
        self._execute_system_workflow(
            wf_id=wf_id,
            task_mapping=deployment_env_creation_task_name,
            deployment=deployment,
            bypass_maintenance=bypass_maintenance,
            execution_parameters={
                'deployment_plugins_to_install': deployment_plan[
                    constants.DEPLOYMENT_PLUGINS_TO_INSTALL],
                'workflow_plugins_to_install': deployment_plan[
                    constants.WORKFLOW_PLUGINS_TO_INSTALL],
                'policy_configuration': {
                    'policy_types': deployment_plan[constants.POLICY_TYPES],
                    'policy_triggers':
                        deployment_plan[constants.POLICY_TRIGGERS],
                    'groups': deployment_plan[constants.GROUPS],
                    'api_token': current_user.api_token
                }
            }
        )

    def _check_for_active_executions(self, deployment_id, force,
                                     queue, schedule):

        def _get_running_executions(deployment_id=None, include_system=True):
            deployment_id_filter = self.create_filters_dict(
                deployment_id=deployment_id,
                status=ExecutionState.ACTIVE_STATES)
            executions = self.list_executions(
                filters=deployment_id_filter,
                is_include_system_workflows=include_system).items
            return [e.id for e in executions if
                    self.sm.get(models.Execution, e.id).status
                    not in ExecutionState.END_STATES]

        should_queue = False

        # validate no execution is currently in progress
        if not force:
            running = _get_running_executions(deployment_id)

            # Execution can't currently run since other executions are running.
            # `queue` flag is on - we will queue the execution and it will
            # run when possible
            if len(running) > 0 and (queue or schedule):
                should_queue = True
                return should_queue
            if len(running) > 0:
                raise manager_exceptions.ExistingRunningExecutionError(
                    'The following executions are currently running for this '
                    'deployment: {0}. To execute this workflow anyway, pass '
                    '"force=true" as a query parameter to this request'.format(
                        running))

        return should_queue

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

    def _validate_permitted_to_execute_global_workflow(self, deployment):
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
        dep_graph = RecursiveDeploymentDependencies(self.sm)

        # if we're in the middle of an execution initiated by the component
        # creator, we'd like to drop the component dependency from the list
        excluded_ids = self._excluded_component_creator_ids(deployment)
        deployment_dependencies = \
            dep_graph.retrieve_and_display_dependencies(
                deployment.id,
                excluded_component_creator_ids=excluded_ids)
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

    @staticmethod
    def _any_running_executions(executions):
        return any(execution.status not in
                   ExecutionState.END_STATES for execution in executions)

    def _workflow_queued(self, execution):
        message_context = {
            'message_type': 'hook',
            'is_system_workflow': execution.is_system_workflow,
            'blueprint_id': execution.blueprint_id,
            'deployment_id': execution.deployment_id,
            'execution_id': execution.id,
            'workflow_id': execution.workflow_id,
            'tenant_name': execution.tenant_name
        }

        if not execution.is_system_workflow:
            message_context['execution_parameters'] = execution.parameters

        event = {
            'type': 'cloudify_event',
            'event_type': 'workflow_queued',
            'context': message_context,
            'message': {
                'text': "'{0}' workflow execution was queued".format(
                    execution.workflow_id
                ),
                'arguments': None
            }
        }

        send_event(event, 'hook')

    def _create_deployment_initial_dependencies(self,
                                                deployment_plan,
                                                source_deployment):
        new_dependencies = deployment_plan.setdefault(
            INTER_DEPLOYMENT_FUNCTIONS, {})

        # handle external client for component and shared resource
        client_config = None
        target_deployment_config = None
        for node in deployment_plan['nodes']:
            if node['type'] in ['cloudify.nodes.Component',
                                'cloudify.nodes.SharedResource']:
                client_config = node['properties'].get('client')
                target_deployment_config = node['properties'].get(
                    'resource_config').get('deployment')
                break
        external_client = None
        if client_config:
            manager_ips = [manager.private_ip for manager in
                           self.sm.list(models.Manager)]
            internal_hosts = ({'127.0.0.1', 'localhost'} | set(manager_ips))
            host = client_config['host']
            host = {host} if type(host) == str else set(host)
            if not (host & internal_hosts):
                external_client = CloudifyClient(**client_config)

        dep_graph = RecursiveDeploymentDependencies(self.sm)
        dep_graph.create_dependencies_graph()

        for func_id, target_deployment_attr in new_dependencies.items():
            target_deployment = target_deployment_attr[0]
            target_deployment_func = target_deployment_attr[1]
            target_deployment_instance = \
                self.sm.get(models.Deployment,
                            target_deployment,
                            fail_silently=True,
                            all_tenants=True) if target_deployment else None

            now = utils.get_formatted_timestamp()
            if external_client:
                external_target = {
                    'deployment': (target_deployment_config.get('id') if
                                   target_deployment_config else None),
                    'client_config': client_config
                }

            self.sm.put(models.InterDeploymentDependencies(
                id=str(uuid.uuid4()),
                dependency_creator=func_id,
                source_deployment=source_deployment,
                target_deployment=(None if external_client else
                                   target_deployment_instance),
                target_deployment_func=target_deployment_func,
                external_target=(external_target if external_client else None),
                created_at=now))
            if external_client:
                dependency_params = {
                    'dependency_creator': func_id,
                    'source_deployment': source_deployment.id,
                    'target_deployment': (target_deployment if
                                          target_deployment else ' '),
                    'external_source': {
                        'deployment': source_deployment.id,
                        'tenant': source_deployment.tenant_name,
                        'host': manager_ips
                    }
                }
                external_client.inter_deployment_dependencies.create(
                    **dependency_params)

            if source_deployment and target_deployment_instance:
                source_id = str(source_deployment.id)
                target_id = str(target_deployment_instance.id)
                dep_graph.assert_no_cyclic_dependencies(source_id, target_id)
                dep_graph.add_dependency_to_graph(source_id, target_id)

    def create_deployment_labels(self, deployment, labels_list):
        """
        Populate the deployments_labels table.

        :param deployment: A deployment object
        :param labels_list: A list of labels of the form:
                            [(key1, value1), (key2, value2)]
        """
        if not labels_list:
            return

        current_time = utils.get_formatted_timestamp()
        for key, value in labels_list:
            self.sm.put(
                models.DeploymentLabel(
                    key=key,
                    value=value,
                    created_at=current_time,
                    deployment=deployment,
                    creator=current_user
                )
            )


# What we need to access this manager in Flask
def get_resource_manager(sm=None):
    """
    Get the current app's resource manager, create if necessary
    """
    if sm:
        return ResourceManager(sm)
    return current_app.config.setdefault('resource_manager',
                                         ResourceManager())


def _create_task_mapping():
    mapping = {
        'create_snapshot': 'cloudify_system_workflows.snapshot.create',
        'restore_snapshot': 'cloudify_system_workflows.snapshot.restore',
        'uninstall_plugin': 'cloudify_system_workflows.plugins.uninstall',
        'create_deployment_environment':
            'cloudify_system_workflows.deployment_environment.create',
        'delete_deployment_environment':
            'cloudify_system_workflows.deployment_environment.delete'
    }
    return mapping


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
