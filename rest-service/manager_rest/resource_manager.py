#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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
import shutil
import traceback
import itertools
from copy import deepcopy
from StringIO import StringIO

import celery.exceptions
from flask import current_app
from flask_security import current_user

from dsl_parser import constants, tasks
from dsl_parser import exceptions as parser_exceptions

from manager_rest.constants import DEFAULT_TENANT_NAME
from manager_rest.storage import get_storage_manager, models, get_node
from manager_rest.storage.models_states import (SnapshotState,
                                                ExecutionState,
                                                DeploymentModificationState)

from . import utils
from . import config
from . import app_context
from . import workflow_executor
from . import manager_exceptions


class ResourceManager(object):

    def __init__(self):
        self.sm = get_storage_manager()

    def list_executions(self, include=None, is_include_system_workflows=False,
                        filters=None, pagination=None, sort=None):
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
            sort=sort
        )

    def update_execution_status(self, execution_id, status, error):
        execution = self.sm.get(models.Execution, execution_id)
        if not self._validate_execution_update(execution.status, status):
            raise manager_exceptions.InvalidExecutionUpdateStatus(
                "Invalid relationship - can't change status from {0} to {1}"
                .format(execution.status, status))
        execution.status = status
        execution.error = error
        return self.sm.update(execution)

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
            'default_tenant_name': DEFAULT_TENANT_NAME
        }

    def create_snapshot_model(self,
                              snapshot_id,
                              status=SnapshotState.CREATING,
                              private_resource=False):
        now = utils.get_formatted_timestamp()
        new_snapshot = models.Snapshot(id=snapshot_id,
                                       created_at=now,
                                       status=status,
                                       private_resource=private_resource,
                                       error='')
        return self.sm.put(new_snapshot)

    def create_snapshot(self,
                        snapshot_id,
                        include_metrics,
                        include_credentials,
                        bypass_maintenance,
                        private_resource=False):
        if not current_user.is_admin:
            raise manager_exceptions.UnauthorizedError(
                '{0} is not admin. Only admins are allowed to create '
                'snapshots'.format(current_user)
            )
        self.create_snapshot_model(snapshot_id,
                                   private_resource=private_resource)
        try:
            _, execution = self._execute_system_workflow(
                wf_id='create_snapshot',
                task_mapping='cloudify_system_workflows.snapshot.create',
                execution_parameters={
                    'snapshot_id': snapshot_id,
                    'include_metrics': include_metrics,
                    'include_credentials': include_credentials,
                    'config': self._get_conf_for_snapshots_wf()
                },
                bypass_maintenance=bypass_maintenance
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
                         tenant_name):
        # Throws error if no snapshot found
        snapshot = self.sm.get(models.Snapshot, snapshot_id)
        if snapshot.status == SnapshotState.FAILED:
            raise manager_exceptions.SnapshotActionError(
                'Failed snapshot cannot be restored'
            )
        if not current_user.is_admin:
            raise manager_exceptions.UnauthorizedError(
                '{0} is not admin. Only admins are allowed to restore '
                'snapshots'.format(current_user)
            )
        _, execution = self._execute_system_workflow(
            wf_id='restore_snapshot',
            task_mapping='cloudify_system_workflows.snapshot.restore',
            execution_parameters={
                'snapshot_id': snapshot_id,
                'recreate_deployments_envs': recreate_deployments_envs,
                'config': self._get_conf_for_snapshots_wf(),
                'force': force,
                'timeout': timeout,
                'tenant_name': tenant_name,
                'premium_enabled': current_app.premium_enabled,
                'user_is_bootstrap_admin': current_user.is_bootstrap_admin
            },
            bypass_maintenance=bypass_maintenance
        )
        return execution

    def install_plugin(self, plugin):
        if utils.plugin_installable_on_current_platform(plugin):
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
        # Verify plugin exists.
        plugin = self.sm.get(models.Plugin, plugin_id)

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
                                        filters={'id': used_blueprints})]
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
                          private_resource=False):
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

        new_blueprint = models.Blueprint(
            plan=plan,
            id=blueprint_id,
            description=plan.get('description'),
            created_at=now,
            updated_at=now,
            main_file_name=application_file_name,
            private_resource=private_resource
        )
        return self.sm.put(new_blueprint)

    def delete_blueprint(self, blueprint_id):
        blueprint = self.sm.get(models.Blueprint, blueprint_id)

        if len(blueprint.deployments) > 0:
            raise manager_exceptions.DependentExistsError(
                "Can't delete blueprint {0} - There exist "
                "deployments for this blueprint; Deployments ids: {1}"
                .format(blueprint_id,
                        ','.join([dep.id for dep
                                  in blueprint.deployments])))

        return self.sm.delete(blueprint)

    def delete_deployment(self,
                          deployment_id,
                          bypass_maintenance=None,
                          ignore_live_nodes=False):
        # Verify deployment exists.
        deployment = self.sm.get(models.Deployment, deployment_id)

        # validate there are no running executions for this deployment
        deplyment_id_filter = self.create_filters_dict(
            deployment_id=deployment_id,
            status=ExecutionState.ACTIVE_STATES
        )
        executions = self.sm.list(
            models.Execution,
            filters=deplyment_id_filter
        )
        if any(execution.status not in ExecutionState.END_STATES for
           execution in executions):
            raise manager_exceptions.DependentExistsError(
                "Can't delete deployment {0} - There are running "
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
                filters=deplyment_id_filter
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
        self._delete_deployment_environment(deployment,
                                            bypass_maintenance)
        return self.sm.delete(deployment)

    def execute_workflow(self, deployment_id, workflow_id,
                         parameters=None,
                         allow_custom_parameters=False,
                         force=False, bypass_maintenance=None):
        deployment = self.sm.get(models.Deployment, deployment_id)
        blueprint = self.sm.get(models.Blueprint, deployment.blueprint_id)

        if workflow_id not in deployment.workflows:
            raise manager_exceptions.NonexistentWorkflowError(
                'Workflow {0} does not exist in deployment {1}'.format(
                    workflow_id, deployment_id))
        workflow = deployment.workflows[workflow_id]

        self._verify_deployment_environment_created_successfully(deployment_id)

        self._check_for_active_system_wide_execution()
        self._check_for_active_executions(deployment_id, force)

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
            parameters=self._get_only_user_execution_parameters(
                execution_parameters),
            is_system_workflow=False)

        if deployment:
            new_execution.set_deployment(deployment)
        self.sm.put(new_execution)

        # executing the user workflow
        workflow_plugins = blueprint.plan[
            constants.WORKFLOW_PLUGINS_TO_INSTALL]
        workflow_executor.execute_workflow(
            workflow_id,
            workflow,
            workflow_plugins=workflow_plugins,
            blueprint_id=deployment.blueprint_id,
            deployment_id=deployment_id,
            execution_id=execution_id,
            execution_parameters=execution_parameters,
            bypass_maintenance=bypass_maintenance)

        return new_execution

    def _check_for_any_active_executions(self):
        filters = {
            'status': ExecutionState.ACTIVE_STATES
        }
        executions = [
            e.id
            for e in self.list_executions(is_include_system_workflows=True,
                                          filters=filters).items
        ]

        if executions:
            raise manager_exceptions.ExistingRunningExecutionError(
                'You cannot start a system-wide execution if there are '
                'other executions running. '
                'Currently running executions: {0}'
                .format(executions))

    def _check_for_active_system_wide_execution(self):
        filters = {
            'status': ExecutionState.ACTIVE_STATES
        }
        for e in self.list_executions(is_include_system_workflows=True,
                                      filters=filters).items:
            if e.deployment_id is None:
                raise manager_exceptions.ExistingRunningExecutionError(
                    'You cannot start an execution if there is a running '
                    'system-wide execution (id: {0})'
                    .format(e.id))

    def _execute_system_workflow(self, wf_id, task_mapping, deployment=None,
                                 execution_parameters=None, timeout=0,
                                 created_at=None, verify_no_executions=True,
                                 bypass_maintenance=None,
                                 update_execution_status=True):
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
        :return: (async task object, execution object)
        """
        execution_id = str(uuid.uuid4())  # will also serve as the task id
        execution_parameters = execution_parameters or {}

        # currently, deployment env creation/deletion are not set as
        # system workflows
        is_system_workflow = wf_id not in ('create_deployment_environment',
                                           'delete_deployment_environment')

        # It means that a system-wide workflow is about to be launched
        if deployment is None and verify_no_executions:
            self._check_for_any_active_executions()

        execution = models.Execution(
            id=execution_id,
            status=ExecutionState.PENDING,
            created_at=created_at or utils.get_formatted_timestamp(),
            workflow_id=wf_id,
            error='',
            parameters=self._get_only_user_execution_parameters(
                execution_parameters),
            is_system_workflow=is_system_workflow)

        if deployment:
            execution.set_deployment(deployment)
        self.sm.put(execution)

        async_task = workflow_executor.execute_system_workflow(
            wf_id=wf_id,
            task_id=execution_id,
            task_mapping=task_mapping,
            deployment=deployment,
            execution_parameters=execution_parameters,
            bypass_maintenance=bypass_maintenance,
            update_execution_status=update_execution_status)

        if timeout > 0:
            try:
                # wait for the workflow execution to complete
                async_task.get(timeout=timeout, propagate=True)
            except celery.exceptions.TimeoutError:
                raise manager_exceptions.ExecutionTimeout(
                    'Execution of system workflow {0} timed out ({1} seconds)'
                    .format(wf_id, timeout))
            except Exception as e:
                # error message for the user
                if deployment:
                    add_info = ' for deployment {0}'.format(deployment.id)
                else:
                    add_info = ''
                error_msg = 'Error occurred while executing the {0} ' \
                            'system workflow {1}: {2} - {3}'.format(
                                wf_id, add_info, type(e).__name__, e)
                # adding traceback to the log error message
                tb = StringIO()
                traceback.print_exc(file=tb)
                log_error_msg = '{0}; traceback: {1}'.format(
                    error_msg, tb.getvalue())
                current_app.logger.error(log_error_msg)
                raise manager_exceptions.ExecutionFailure(error_msg)
            self.sm.refresh(execution)  # Reload the status form the DB
            if execution.status != ExecutionState.TERMINATED:
                raise manager_exceptions.ExecutionFailure(
                    'Failed executing the {0} system workflow: '
                    'Execution did not complete successfully.'.format(wf_id))

        return async_task, execution

    def cancel_execution(self, execution_id, force=False):
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

        execution = self.sm.get(models.Execution, execution_id)
        if execution.status not in (ExecutionState.PENDING,
                                    ExecutionState.STARTED) and \
                (not force or execution.status != ExecutionState.CANCELLING):
            raise manager_exceptions.IllegalActionError(
                "Can't {0}cancel execution {1} because it's in status {2}"
                .format(
                    'force-' if force else '',
                    execution_id,
                    execution.status))

        new_status = ExecutionState.CANCELLING if not force \
            else ExecutionState.FORCE_CANCELLING
        execution.status = new_status
        execution.error = ''
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

    def create_deployment(self,
                          blueprint_id,
                          deployment_id,
                          inputs=None,
                          bypass_maintenance=None,
                          private_resource=False,
                          skip_plugins_validation=False):

        blueprint = self.sm.get(models.Blueprint, blueprint_id)
        plan = blueprint.plan
        try:
            deployment_plan = tasks.prepare_deployment_plan(plan, inputs)
        except parser_exceptions.MissingRequiredInputError, e:
            raise manager_exceptions.MissingRequiredDeploymentInputError(
                str(e))
        except parser_exceptions.UnknownInputError, e:
            raise manager_exceptions.UnknownDeploymentInputError(str(e))

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
        new_deployment = self.prepare_deployment_for_storage(
            deployment_id,
            deployment_plan
        )
        new_deployment.set_blueprint(blueprint)
        # The deployment is private if either the blueprint was
        # private, or the user passed the `private_resource` flag
        private_resource = private_resource or blueprint.private_resource
        new_deployment.private_resource = private_resource
        self.sm.put(new_deployment)

        self._create_deployment_nodes(deployment_id, deployment_plan)

        self._create_deployment_node_instances(
            deployment_id,
            dsl_node_instances=deployment_plan['node_instances'])

        self._create_deployment_environment(new_deployment,
                                            deployment_plan,
                                            bypass_maintenance)
        return new_deployment

    def validate_plugin_is_installed(self, plugin):
        """
        This method checks if a plugin is already installed on the manager,
        if not - raises an appropriate exception.
        :param plugin: A plugin from the blueprint
        """

        # if plugin['install']==False we don't need to install this plugin
        if not plugin['install']:
            return
        query_parameters = {
            'package_name': plugin['package_name'],
            'package_version': plugin['package_version']
        }
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
        if plugin['source']:
            query_parameters['package_source'] = plugin['source']

        result = self.sm.list(models.Plugin, filters=query_parameters)
        if result.metadata['pagination']['total'] == 0:
            raise manager_exceptions.\
                DeploymentPluginNotFound(
                    'Required plugin {}, version {} is not installed '
                    'on the manager'.format(plugin['name'],
                                            plugin['package_version']))

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
                 in self.sm.list(models.Node, filters=deployment_id_filter)]
        node_instances = [instance.to_dict() for instance
                          in self.sm.list(models.NodeInstance,
                          filters=deployment_id_filter)]
        node_instances_modification = tasks.modify_deployment(
            nodes=nodes,
            previous_nodes=nodes,
            previous_node_instances=node_instances,
            modified_nodes=modified_nodes,
            scaling_groups=deployment.scaling_groups)

        node_instances_modification['before_modification'] = [
            instance.to_dict() for instance in
            self.sm.list(models.NodeInstance, filters=deployment_id_filter)]

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
            filters=deployment_id_filter
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
                include=['id', 'number_of_instances'])
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

        # Link the node instance object to to the node, and add it to the DB
        new_node_instance = models.NodeInstance(**instance_dict)
        node = get_node(deployment_id, node_id)
        new_node_instance.set_node(node)
        self.sm.put(new_node_instance)

        # Return the IDs to the dict for later use
        instance_dict['deployment_id'] = deployment_id
        instance_dict['node_id'] = node_id
        instance_dict['tenant_name'] = tenant_name
        instance_dict['created_by'] = created_by

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

    def _check_for_active_executions(self, deployment_id, force):

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

        # validate no execution is currently in progress
        if not force:
            running = _get_running_executions(deployment_id)
            if len(running) > 0:
                raise manager_exceptions.ExistingRunningExecutionError(
                    'The following executions are currently running for this '
                    'deployment: {0}. To execute this workflow anyway, pass '
                    '"force=true" as a query parameter to this request'.format(
                        running))

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


# What we need to access this manager in Flask
def get_resource_manager():
    """
    Get the current app's resource manager, create if necessary
    """
    return current_app.config.setdefault('resource_manager', ResourceManager())
