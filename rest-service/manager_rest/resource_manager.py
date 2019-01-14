#########
# Copyright (c) 2018 Cloudify Platform Ltd. All rights reserved
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
import shutil
import itertools
from copy import deepcopy
from StringIO import StringIO

from flask import current_app
from flask_security import current_user

from cloudify import constants as cloudify_constants, utils as cloudify_utils
from cloudify.workflows import tasks as cloudify_tasks
from cloudify.models_states import (SnapshotState,
                                    ExecutionState,
                                    VisibilityState,
                                    DeploymentModificationState)

from dsl_parser import constants, tasks
from dsl_parser import exceptions as parser_exceptions

from manager_rest import premium_enabled
from manager_rest.constants import (DEFAULT_TENANT_NAME,
                                    FILE_SERVER_BLUEPRINTS_FOLDER,
                                    FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER)
from manager_rest.dsl_functions import get_secret_method
from manager_rest.utils import is_create_global_permitted, send_event
from manager_rest.storage import (db,
                                  get_storage_manager,
                                  models,
                                  get_node,
                                  ListResult)

from . import utils
from . import config
from . import app_context
from . import workflow_executor
from . import manager_exceptions


class ResourceManager(object):

    def __init__(self):
        self.sm = get_storage_manager()
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
                "Invalid relationship - can't change status from {0} to {1}"
                .format(execution.status, status))
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
            self.start_queued_executions()
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
            'db_address': config_instance.db_address,
            'db_port': config_instance.db_port,
            'created_status': SnapshotState.CREATED,
            'failed_status': SnapshotState.FAILED,
            'postgresql_bin_path': config_instance.postgresql_bin_path,
            'postgresql_username': config_instance.postgresql_username,
            'postgresql_password': config_instance.postgresql_password,
            'postgresql_db_name': config_instance.postgresql_db_name,
            'postgresql_host': config_instance.postgresql_host,
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
                        include_metrics,
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
                    'include_metrics': include_metrics,
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
                         no_reboot,
                         ignore_plugin_failure):
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
                'ignore_plugin_failure':
                    ignore_plugin_failure,
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

    def install_plugin(self, plugin):
        """Install the plugin if required.

        The plugin will be installed if the declared platform/distro
        is the same as the manager's.
        """
        if plugin.yaml_file_path():
            self._validate_plugin_yaml(plugin)

        if not utils.plugin_installable_on_current_platform(plugin):
            return

        self._execute_system_workflow(
            wf_id='install_plugin',
            task_mapping='cloudify_system_workflows.plugins.install',
            execution_parameters={
                'plugin': {
                    'name': plugin.package_name,
                    'package_name': plugin.package_name,
                    'package_version': plugin.package_version
                }
            },
            verify_no_executions=False,
            timeout=300)

    def remove_plugin(self, plugin_id, force):
        # Verify plugin exists and can be removed
        plugin = self.sm.get(models.Plugin, plugin_id)
        self.validate_modification_permitted(plugin)

        # Uninstall (if applicable)
        if utils.plugin_installable_on_current_platform(plugin):
            if not force:
                used_blueprints = list(set(
                    d.blueprint_id for d in
                    self.sm.list(models.Deployment, include=['blueprint_id'])))
                plugins = [b.plan[constants.WORKFLOW_PLUGINS_TO_INSTALL] +
                           b.plan[constants.DEPLOYMENT_PLUGINS_TO_INSTALL]
                           for b in
                           self.sm.list(models.Blueprint,
                                        include=['plan'],
                                        filters={'id': used_blueprints},
                                        get_all_results=True)]
                plugins = set((p.get('package_name'), p.get('package_version'))
                              for sublist in plugins for p in sublist)
                if (plugin.package_name, plugin.package_version) in plugins:
                    raise manager_exceptions.PluginInUseError(
                        'Plugin {} is currently in use. You can "force" '
                        'plugin removal.'.format(plugin.id))
            self._execute_system_workflow(
                wf_id='uninstall_plugin',
                task_mapping='cloudify_system_workflows.plugins.uninstall',
                execution_parameters={
                    'plugin': {
                        'name': plugin.package_name,
                        'package_name': plugin.package_name,
                        'package_version': plugin.package_version,
                        'wagon': True
                    }
                },
                verify_no_executions=False,
                timeout=300)

        # Remove from storage
        self.sm.delete(plugin)

        # Remove from file system
        archive_path = utils.get_plugin_archive_path(plugin_id,
                                                     plugin.archive_name)
        shutil.rmtree(os.path.dirname(archive_path), ignore_errors=True)

        return plugin

    def publish_blueprint(self,
                          application_dir,
                          application_file_name,
                          resources_base,
                          blueprint_id,
                          private_resource,
                          visibility):
        dsl_location = os.path.join(
            resources_base,
            application_dir,
            application_file_name
        )
        try:
            plan = tasks.parse_dsl(dsl_location,
                                   resources_base,
                                   **app_context.get_parser_context())
        except Exception, ex:
            raise manager_exceptions.DslParseException(str(ex))

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
            visibility=visibility
        )
        return self.sm.put(new_blueprint)

    def _remove_folder(self, folder_name, blueprints_location):
        blueprint_folder = os.path.join(
            config.instance.file_server_root,
            blueprints_location,
            utils.current_tenant.name,
            folder_name.id)
        shutil.rmtree(blueprint_folder)

    def delete_blueprint(self, blueprint_id, force):
        blueprint = self.sm.get(models.Blueprint, blueprint_id)
        self.validate_modification_permitted(blueprint)

        if not force:
            imported_blueprints_list = [b.plan[constants.IMPORTED_BLUEPRINTS]
                                        for b in self.sm.list(
                                        models.Blueprint,
                                        include=['id', 'plan'],
                                        get_all_results=True)]
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
                        ','.join([dep.id for dep
                                  in blueprint.deployments])))
        # Delete blueprint resources from file server
        self._remove_folder(folder_name=blueprint,
                            blueprints_location=FILE_SERVER_BLUEPRINTS_FOLDER)
        self._remove_folder(
            folder_name=blueprint,
            blueprints_location=FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER)

        return self.sm.delete(blueprint)

    def delete_deployment(self,
                          deployment_id,
                          bypass_maintenance=None,
                          ignore_live_nodes=False,
                          delete_db_mode=False):
        # Verify deployment exists.
        deployment = self.sm.get(models.Deployment, deployment_id)

        # Validate there are no running executions for this deployment
        deplyment_id_filter = self.create_filters_dict(
            deployment_id=deployment_id,
            status=ExecutionState.ACTIVE_STATES + ExecutionState.QUEUED_STATE
        )
        executions = self.sm.list(
            models.Execution,
            filters=deplyment_id_filter
        )

        if not delete_db_mode and self._any_running_executions(executions):
            raise manager_exceptions.DependentExistsError(
                "Can't delete deployment {0} - There are running or queued "
                "executions for this deployment. Running executions ids: {1}"
                .format(
                    deployment_id,
                    ','.join([execution.id for execution in
                              executions if execution.status not
                              in ExecutionState.END_STATES])))
        if not ignore_live_nodes:
            deplyment_id_filter = self.create_filters_dict(
                deployment_id=deployment_id)
            node_instances = self.sm.list(
                models.NodeInstance,
                filters=deplyment_id_filter,
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

        # Start delete_deployment_env workflow
        if not delete_db_mode:
            self._delete_deployment_environment(deployment,
                                                bypass_maintenance)
            return self.sm.get(models.Deployment, deployment_id)

        # Delete deployment data  DB (should only happen AFTER the workflow
        # finished successfully, hence the delete_db_mode flag)
        else:
            return self.sm.delete(deployment)

    def _reset_failed_operations(self, execution):
        """Force-resume the execution: restart failed operations.

        All operations that were failed are going to be retried,
        the execution itself is going to be set to pending again.

        :return: Whether to continue with running the execution
        """
        execution.status = ExecutionState.STARTED
        self.sm.update(execution, modified_attrs=('status',))

        tasks_graphs = self.sm.list(models.TasksGraph,
                                    filters={'execution': execution},
                                    get_all_results=True)
        for graph in tasks_graphs:
            operations = self.sm.list(models.Operation,
                                      filters={'tasks_graph': graph},
                                      get_all_results=True)
            for operation in operations:
                if operation.state in (cloudify_tasks.TASK_RESCHEDULED,
                                       cloudify_tasks.TASK_FAILED):
                    operation.state = cloudify_tasks.TASK_PENDING
                    operation.parameters['current_retries'] = 0
                    self.sm.update(operation,
                                   modified_attrs=('parameters', 'state'))

    def resume_execution(self, execution_id, force=False):
        execution = self.sm.get(models.Execution, execution_id)
        if force:
            if execution.status not in (ExecutionState.CANCELLED,
                                        ExecutionState.FAILED):
                raise manager_exceptions.ConflictError(
                    'Cannot force-resume execution: `{0}` in state: `{1}`'
                    .format(execution.id, execution.status))
            self._reset_failed_operations(execution)

        if execution.status != ExecutionState.STARTED:
            raise manager_exceptions.ConflictError(
                'Cannot resume execution: `{0}` in state: `{1}`'
                .format(execution.id, execution.status))
        self.sm.update(execution)

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
            deployment_id=deployment.id,
            execution_id=execution_id,
            execution_parameters=execution.parameters,
            bypass_maintenance=False,
            dry_run=False,
            resume=True,
            execution_creator=execution.creator)
        return execution

    def execute_workflow(self,
                         deployment_id,
                         workflow_id,
                         parameters=None,
                         allow_custom_parameters=False,
                         force=False,
                         bypass_maintenance=None,
                         dry_run=False,
                         queue=False,
                         execution=None,
                         wait_after_fail=600,
                         execution_creator=None,
                         scheduled_time=None):

        execution_creator = execution_creator or current_user
        deployment = self.sm.get(models.Deployment, deployment_id)
        self._validate_permitted_to_execute_global_workflow(deployment)
        blueprint = self.sm.get(models.Blueprint, deployment.blueprint_id)
        self._verify_workflow_in_deployment(workflow_id, deployment,
                                            deployment_id)
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

        should_queue = self._check_for_executions(deployment_id, force,
                                                  queue, execution)
        if not execution:
            new_execution = models.Execution(
                id=execution_id,
                status=self._get_proper_status(should_queue, scheduled_time),
                created_at=utils.get_formatted_timestamp(),
                workflow_id=workflow_id,
                error='',
                parameters=execution_parameters,
                is_system_workflow=False,
                is_dry_run=dry_run,
                scheduled_for=scheduled_time
            )

            if deployment:
                new_execution.set_deployment(deployment)
        if should_queue:
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
            deployment_id=deployment_id,
            execution_id=execution_id,
            execution_parameters=execution_parameters,
            bypass_maintenance=bypass_maintenance,
            dry_run=dry_run,
            wait_after_fail=wait_after_fail,
            scheduled_time=scheduled_time)

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

    @staticmethod
    def _get_proper_status(should_queue, scheduled=None):
        if should_queue:
            return ExecutionState.QUEUED

        elif scheduled:
            return ExecutionState.SCHEDULED

        return ExecutionState.PENDING

    @staticmethod
    def _verify_workflow_in_deployment(wf_id, deployment, dep_id):
        if wf_id not in deployment.workflows:
            raise manager_exceptions.NonexistentWorkflowError(
                'Workflow {0} does not exist in deployment {1}'.format(
                    wf_id, dep_id))

    def _check_for_executions(self, deployment_id, force, queue, execution):
        """
        :param deployment_id: The id of the deployment the workflow belongs to.
        :param force: If set, 2 executions under the same deployment can run
                together.
        :param queue: If set, in case an execution can't currently run it will
                be queued (instead of raising an exception).
        :param execution: An execution DB object, if exists it means this
                execution was de-queued.

        If the `queue` flag is False and there are running executions an
        Exception will be raised
        """
        system_exec_running = self._check_for_active_system_wide_execution(
            queue, execution)
        execution_running = self._check_for_active_executions(
            deployment_id, force, queue)
        return system_exec_running or execution_running

    def _check_for_any_active_executions(self, queue):
        filters = {
            'status': ExecutionState.ACTIVE_STATES
        }
        executions = [
            e.id
            for e in self.list_executions(is_include_system_workflows=True,
                                          filters=filters,
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

    def _check_for_active_system_wide_execution(self, queue, execution):
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
                                      get_all_results=True).items:
            # Execution can't currently run because system execution is
            # running. since `queue` flag is on - we will queue the execution
            #  and it will run when possible
            if e.deployment_id is None and queue:
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

    def _execute_system_workflow(self, wf_id, task_mapping, deployment=None,
                                 execution_parameters=None, timeout=0,
                                 created_at=None, verify_no_executions=True,
                                 bypass_maintenance=None,
                                 update_execution_status=True,
                                 queue=False, execution=None,
                                 execution_creator=None):
        """
        :param deployment: deployment for workflow execution
        :param wf_id: workflow id
        :param task_mapping: mapping to the system workflow
        :param execution_parameters: parameters for the system workflow
        :param timeout: 0 will return immediately; any positive value will
         cause this method to wait for the given timeout for the task to
         complete, and verify it finished successfully before returning
        :param created_at: creation time for the workflow execution object.
         if omitted, a value will be generated by this method.
        :param bypass_maintenance: allows running the workflow despite having
        the manager maintenance mode activated.
        :param queue: If set, in case the execution is blocked it will be
        queued and automatically run when the blocking workflows are finished
        :param execution: an execution DB object. If it was passed it means
        this execution was queued and now trying to run again. If the execution
        can currently run it will, if not it will be queued again.
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
                                               'delete_deployment_environment')

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
                workflow_id=wf_id,
                error='',
                parameters=execution_parameters,
                is_system_workflow=is_system_workflow)

            if deployment:
                execution.set_deployment(deployment)

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

        Note that in either case, the execution is not yet cancelled upon
        returning from the method. Instead, it'll be in a 'cancelling' or
        'force_cancelling' status (as can be seen in models.Execution). Once
        the execution is truly stopped, it'll be in 'cancelled' status (unless
        force was not used and the executed workflow doesn't support
        graceful termination, in which case it might simply continue
        regardless and end up with a 'terminated' status)

        :param execution_id: The execution id
        :param force: A boolean describing whether to force cancellation
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
                "Can't {0}cancel execution {1} because it's in status {2}"
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
            capabilities=deployment_plan['capabilities']
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
        node_instances = []
        for node_instance in dsl_node_instances:
            node = get_node(deployment_id, node_instance['node_id'])
            instance_id = node_instance['id']
            scaling_groups = node_instance.get('scaling_groups', [])
            relationships = node_instance.get('relationships', [])
            host_id = node_instance.get('host_id')
            instance = models.NodeInstance(
                id=instance_id,
                host_id=host_id,
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
                          skip_plugins_validation=False):
        blueprint = self.sm.get(models.Blueprint, blueprint_id)
        plan = blueprint.plan
        try:
            deployment_plan = tasks.prepare_deployment_plan(
                plan, get_secret_method(), inputs)
        except parser_exceptions.MissingRequiredInputError as e:
            raise manager_exceptions.MissingRequiredDeploymentInputError(
                str(e))
        except parser_exceptions.UnknownInputError as e:
            raise manager_exceptions.UnknownDeploymentInputError(str(e))
        except parser_exceptions.InputEvaluationError as e:
            raise manager_exceptions.DeploymentInputEvaluationError(str(e))
        except parser_exceptions.UnknownSecretError as e:
            raise manager_exceptions.UnknownDeploymentSecretError(str(e))
        except parser_exceptions.UnsupportedGetSecretError as e:
            raise manager_exceptions.UnsupportedDeploymentGetSecretError(
                str(e))

        #  validate plugins exists on manager when
        #  skip_plugins_validation is False
        if not skip_plugins_validation:
            plugins_list = deployment_plan.get('deployment_plugins_to_install',
                                               [])
            # validate that all central-deployment plugins are installed
            for plugin in plugins_list:
                self.validate_plugin_is_installed(plugin)
            # validate that all host_agent plugins are installed
            for node in deployment_plan.get('nodes', []):
                for plugin in node.get('plugins_to_install', []):
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
        new_deployment.blueprint = blueprint
        new_deployment.visibility = visibility
        self.sm.put(new_deployment)

        self._create_deployment_nodes(deployment_id, deployment_plan)

        self._create_deployment_node_instances(
            deployment_id,
            dsl_node_instances=deployment_plan['node_instances'])

        try:
            self._create_deployment_environment(new_deployment,
                                                deployment_plan,
                                                bypass_maintenance)
        except manager_exceptions.ExistingRunningExecutionError as e:
            self.delete_deployment(deployment_id=deployment_id,
                                   ignore_live_nodes=True,
                                   delete_db_mode=True)
            raise e

        return new_deployment

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

        node_instances_modification['before_modification'] = [
            instance.to_dict() for instance in
            self.sm.list(models.NodeInstance,
                         filters=deployment_id_filter,
                         get_all_results=True)]

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

    def list_agents(self, deployment_id=None, node_ids=None,
                    node_instance_ids=None, install_method=None):
        filters = {}
        if deployment_id is not None:
            filters['deployment_id'] = deployment_id
        if node_ids is not None:
            filters['id'] = node_ids
        nodes = {n._storage_id: n
                 for n in self.sm.list(models.Node, filters=filters,
                                       get_all_results=True)
                 if self._is_agent_node(n)}

        if not nodes:
            pagination = {'total': 0, 'size': 0, 'offset': 0}
            return ListResult([], metadata={'pagination': pagination})

        instance_filters = {'_node_fk': list(nodes)}
        if node_instance_ids:
            instance_filters['id'] = node_instance_ids
        node_instances = self.sm.list(models.NodeInstance,
                                      filters=instance_filters,
                                      get_all_results=True)
        agents = []
        for inst in node_instances:
            agent = self._agent_from_instance(inst)
            if agent is None:
                continue
            if install_method is not None and \
                    agent['install_method'] not in install_method:
                continue
            agents.append(agent)

        # there's no real way to implement pagination in a meaningful manner,
        # since we need to query node-instances anyway; still, include the
        # sizes to keep response object shape consistent with all other
        # endpoints
        pagination = {'total': len(agents), 'size': len(agents), 'offset': 0}
        return ListResult(agents, metadata={'pagination': pagination})

    def _agent_from_instance(self, instance):
        if instance.state != 'started':
            return
        agent = instance.runtime_properties.get('cloudify_agent')
        if not agent:
            return
        if agent.get('windows'):
            system = 'windows'
        else:
            system = agent.get('distro')
            if agent.get('distro_codename'):
                system = '{0} {1}'.format(system, agent.get('distro_codename'))
        return dict(
            id=instance.id,
            host_id=instance.host_id,
            ip=agent.get('ip'),
            install_method=agent.get('install_method'),
            system=system,
            version=agent.get('version'),
            node=instance.node_id,
            deployment=instance.deployment_id
        )

    def _is_agent_node(self, node):
        if cloudify_constants.COMPUTE_NODE_TYPE not in node.type_hierarchy:
            return False
        if cloudify_utils.internal.get_install_method(node.properties) == \
                cloudify_constants.AGENT_INSTALL_METHOD_NONE:
            return False
        return True

    @staticmethod
    def _try_convert_from_str(string, target_type):
        if target_type == basestring:
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
            'string': basestring,
            'boolean': bool
        }
        wrong_types = {}

        for param_name, param in workflow_parameters.iteritems():

            if 'type' in param and param_name in execution_parameters:

                # check if need to convert from string
                if isinstance(execution_parameters[param_name], basestring) \
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
            for param_name, param_type in wrong_types.iteritems():
                error_message.write('Parameter "{0}" must be of type {1}\n'.
                                    format(param_name, param_type))
            raise manager_exceptions.IllegalExecutionParametersError(
                error_message.getvalue())

        custom_parameters = {k: v for k, v in execution_parameters.iteritems()
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
        for key, val in kwargs.iteritems():
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

    def _delete_deployment_environment(self,
                                       deployment,
                                       bypass_maintenance):
        blueprint = self.sm.get(models.Blueprint, deployment.blueprint_id)
        wf_id = 'delete_deployment_environment'
        deployment_env_deletion_task_name = \
            'cloudify_system_workflows.deployment_environment.delete'

        self._execute_system_workflow(
            wf_id=wf_id,
            task_mapping=deployment_env_deletion_task_name,
            deployment=deployment,
            bypass_maintenance=bypass_maintenance,
            update_execution_status=False,
            verify_no_executions=False,
            execution_parameters={
                'deployment_plugins_to_uninstall': blueprint.plan[
                    constants.DEPLOYMENT_PLUGINS_TO_INSTALL],
                'workflow_plugins_to_uninstall': blueprint.plan[
                    constants.WORKFLOW_PLUGINS_TO_INSTALL],
            })

    def _check_for_active_executions(self, deployment_id, force, queue):

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
            if len(running) > 0 and queue:
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
        return {k: v for k, v in execution_parameters.iteritems()
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
            return VisibilityState.PRIVATE if private_resource else \
                VisibilityState.TENANT

        # Validate that global visibility is permitted
        if visibility == VisibilityState.GLOBAL:
            self._validate_global_permitted(model_class,
                                            resource_id,
                                            create_resource=True,
                                            plugin_info=plugin_info)

        return visibility or VisibilityState.TENANT

    @staticmethod
    def _is_visibility_wider(first, second):
        states = VisibilityState.STATES
        return states.index(first) > states.index(second)

    def set_deployment_visibility(self, deployment_id, visibility):
        deployment = self.sm.get(models.Deployment, deployment_id)
        blueprint = deployment.blueprint
        if self._is_visibility_wider(visibility, blueprint.visibility):
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
        if self._is_visibility_wider(current_visibility, new_visibility):
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
            self._validate_global_permitted(model_class,
                                            resource.id,
                                            plugin_info=plugin_info)

    def _validate_global_permitted(self,
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
            unique_filter = {
                model_class.package_name: plugin_info['package_name'],
                model_class.archive_name: plugin_info['archive_name']
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

    def validate_modification_permitted(self, resource):
        # A global resource can't be modify from outside its tenant
        if resource.visibility == VisibilityState.GLOBAL and \
           resource.tenant_name != self.sm.current_tenant.name:
            raise manager_exceptions.IllegalActionError(
                "Can't modify the global resource `{0}` from outside its "
                "tenant `{1}`".format(resource.id, resource.tenant_name))

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


# What we need to access this manager in Flask
def get_resource_manager():
    """
    Get the current app's resource manager, create if necessary
    """
    return current_app.config.setdefault('resource_manager', ResourceManager())


def _create_task_mapping():
    mapping = {
        'create_snapshot': 'cloudify_system_workflows.snapshot.create',
        'restore_snapshot': 'cloudify_system_workflows.snapshot.restore',
        'install_plugin': 'cloudify_system_workflows.plugins.install',
        'uninstall_plugin': 'cloudify_system_workflows.plugins.uninstall',
        'create_deployment_environment':
            'cloudify_system_workflows.deployment_environment.create',
        'delete_deployment_environment':
            'cloudify_system_workflows.deployment_environment.delete'
    }
    return mapping
