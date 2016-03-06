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

import uuid
import traceback
import os
from datetime import datetime
from StringIO import StringIO

from flask import current_app

from dsl_parser import constants, functions, tasks
from dsl_parser import exceptions as parser_exceptions
from dsl_parser import utils as dsl_parser_utils
from manager_rest import models
from manager_rest import config
from manager_rest import manager_exceptions
from manager_rest import storage_manager
from manager_rest import workflow_client as wf_client


class DslParseException(Exception):
    pass


class BlueprintAlreadyExistsException(Exception):
    def __init__(self, blueprint_id, *args):
        Exception.__init__(self, args)
        self.blueprint_id = blueprint_id


class BlueprintsManager(object):

    def __init__(self):
        self.sm = storage_manager.get_storage_manager()
        self.workflow_client = wf_client.get_workflow_client()

    def blueprints_list(self, include=None, filters=None,
                        pagination=None, sort=None):
        return self.sm.blueprints_list(include=include, filters=filters,
                                       pagination=pagination, sort=sort)

    def deployments_list(self, include=None, filters=None, pagination=None,
                         sort=None):
        return self.sm.deployments_list(include=include, filters=filters,
                                        pagination=pagination, sort=sort)

    def snapshots_list(self, include=None, filters=None, pagination=None,
                       sort=None):
        return self.sm.snapshots_list(include=include, filters=filters,
                                      pagination=pagination, sort=sort)

    def executions_list(self, include=None, is_include_system_workflows=False,
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
        return self.sm.executions_list(include=include, filters=filters,
                                       pagination=pagination, sort=sort)

    def get_blueprint(self, blueprint_id, include=None):
        return self.sm.get_blueprint(blueprint_id, include=include)

    def get_snapshot(self, snapshot_id, include=None):
        return self.sm.get_snapshot(snapshot_id, include=include)

    def get_deployment(self, deployment_id, include=None):
        return self.sm.get_deployment(deployment_id=deployment_id,
                                      include=include)

    def get_execution(self, execution_id, include=None):
        return self.sm.get_execution(execution_id, include=include)

    def get_plugin(self, plugin_id, include=None):
        return self.sm.get_plugin(plugin_id, include=include)

    def update_execution_status(self, execution_id, status, error):
        execution = self.get_execution(execution_id)
        if not self._validate_execution_update(execution.status, status):
            raise manager_exceptions.InvalidExecutionUpdateStatus(
                "Invalid relationship - can't change status from {0} to {1}"
                .format(execution.status, status))

        return self.sm.update_execution_status(
            execution_id, status, error)

    def _validate_execution_update(self, current_status, future_status):
        if current_status in models.Execution.END_STATES:
            return False

        invalid_cancel_statuses = models.Execution.ACTIVE_STATES + [
            models.Execution.TERMINATED]
        if all((current_status == models.Execution.CANCELLING,
                future_status in invalid_cancel_statuses)):
            return False

        invalid_force_cancel_statuses = invalid_cancel_statuses + [
            models.Execution.CANCELLING]
        if all((current_status == models.Execution.FORCE_CANCELLING,
                future_status in invalid_force_cancel_statuses)):
            return False

        return True

    def _get_conf_for_snapshots_wf(self):
        return {
            'file_server_root': config.instance().file_server_root,
            'file_server_snapshots_folder':
                config.instance().file_server_snapshots_folder,
            'file_server_blueprints_folder':
                config.instance().file_server_blueprints_folder,
            'file_server_deployments_folder':
                config.instance().file_server_deployments_folder,
            'file_server_uploaded_blueprints_folder':
                config.instance().file_server_uploaded_blueprints_folder,
            'db_address': config.instance().db_address,
            'db_port': config.instance().db_port,
            'created_status': models.Snapshot.CREATED,
            'failed_status': models.Snapshot.FAILED,
            'file_server_uploaded_plugins_folder':
                config.instance().file_server_uploaded_plugins_folder
        }

    def create_snapshot_model(self, snapshot_id,
                              status=models.Snapshot.CREATING):
        now = str(datetime.now())
        new_snapshot = models.Snapshot(id=snapshot_id,
                                       created_at=now,
                                       status=status,
                                       error='')
        self.sm.put_snapshot(snapshot_id, new_snapshot)
        return new_snapshot

    def update_snapshot_status(self, snapshot_id, status, error):
        return self.sm.update_snapshot_status(snapshot_id, status, error)

    def create_snapshot(self, snapshot_id,
                        include_metrics, include_credentials):
        self.create_snapshot_model(snapshot_id)
        try:
            _, execution = self._execute_system_workflow(
                wf_id='create_snapshot',
                task_mapping='cloudify_system_workflows.snapshot.create',
                execution_parameters={
                    'snapshot_id': snapshot_id,
                    'include_metrics': include_metrics,
                    'include_credentials': include_credentials,
                    'config': self._get_conf_for_snapshots_wf()
                }
            )
        except manager_exceptions.ExistingRunningExecutionError:
            self.delete_snapshot(snapshot_id)
            raise

        return execution

    def restore_snapshot(self, snapshot_id, recreate_deployments_envs, force):
        # Throws error if no snapshot found
        snap = self.get_snapshot(snapshot_id)
        if snap.status == models.Snapshot.FAILED:
            raise manager_exceptions.SnapshotActionError(
                'Failed snapshot cannot be restored'
            )
        _, execution = self._execute_system_workflow(
            wf_id='restore_snapshot',
            task_mapping='cloudify_system_workflows.snapshot.restore',
            execution_parameters={
                'snapshot_id': snapshot_id,
                'recreate_deployments_envs': recreate_deployments_envs,
                'config': self._get_conf_for_snapshots_wf(),
                'force': force
            }
        )
        return execution

    def publish_blueprint(self,
                          application_dir,
                          application_file_name,
                          resources_base,
                          blueprint_id):
        application_file = os.path.join(application_dir, application_file_name)
        dsl_location = '{0}{1}'.format(resources_base, application_file)
        try:
            plan = tasks.parse_dsl(
                dsl_location, resources_base,
                **self._get_parser_context())
        except Exception, ex:
            raise DslParseException(str(ex))

        now = str(datetime.now())

        new_blueprint = models.BlueprintState(
            plan=plan,
            id=blueprint_id,
            description=plan.get('description'),
            created_at=now,
            updated_at=now,
            main_file_name=application_file_name)
        self.sm.put_blueprint(new_blueprint.id, new_blueprint)
        return new_blueprint

    def delete_blueprint(self, blueprint_id):
        blueprint_deployments = self.sm.get_blueprint_deployments(
            blueprint_id).items

        if len(blueprint_deployments) > 0:
            raise manager_exceptions.DependentExistsError(
                "Can't delete blueprint {0} - There exist "
                "deployments for this blueprint; Deployments ids: {1}"
                .format(blueprint_id,
                        ','.join([dep.id for dep
                                  in blueprint_deployments])))

        return self.sm.delete_blueprint(blueprint_id)

    def delete_snapshot(self, snapshot_id):
        return self.sm.delete_snapshot(snapshot_id)

    def delete_deployment(self, deployment_id, ignore_live_nodes=False):
        # Verify deployment exists.
        self.sm.get_deployment(deployment_id)

        # validate there are no running executions for this deployment
        deplyment_id_filter = self.create_filters_dict(
            deployment_id=deployment_id)
        executions = self.sm.executions_list(
            filters=deplyment_id_filter).items
        if any(execution.status not in models.Execution.END_STATES for
           execution in executions):
            raise manager_exceptions.DependentExistsError(
                "Can't delete deployment {0} - There are running "
                "executions for this deployment. Running executions ids: {1}"
                .format(
                    deployment_id,
                    ','.join([execution.id for execution in
                              executions if execution.status not
                              in models.Execution.END_STATES])))

        if not ignore_live_nodes:
            deplyment_id_filter = self.create_filters_dict(
                deployment_id=deployment_id)
            node_instances = self.sm.get_node_instances(
                filters=deplyment_id_filter).items
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

        self._delete_deployment_environment(deployment_id)
        self._delete_deployment_logs(deployment_id)
        return self.sm.delete_deployment(deployment_id)

    def execute_workflow(self, deployment_id, workflow_id,
                         parameters=None,
                         allow_custom_parameters=False, force=False):
        deployment = self.get_deployment(deployment_id)
        blueprint = self.get_blueprint(deployment.blueprint_id)

        if workflow_id not in deployment.workflows:
            raise manager_exceptions.NonexistentWorkflowError(
                'Workflow {0} does not exist in deployment {1}'.format(
                    workflow_id, deployment_id))
        workflow = deployment.workflows[workflow_id]

        self._verify_deployment_environment_created_successfully(deployment_id)

        self._check_for_active_system_wide_execution()
        self._check_for_active_executions(deployment_id, force)

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
            parameters=self._get_only_user_execution_parameters(
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

    def _check_for_any_active_executions(self):
        filters = {
            'status': models.Execution.ACTIVE_STATES
        }
        executions = [
            e.id
            for e in self.executions_list(is_include_system_workflows=True,
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
            'status': models.Execution.ACTIVE_STATES
        }
        for e in self.executions_list(is_include_system_workflows=True,
                                      filters=filters).items:
            if e.deployment_id is None:
                raise manager_exceptions.ExistingRunningExecutionError(
                    'You cannot start an execution if there is a running '
                    'system-wide execution (id: {0})'
                    .format(e.id))

    def _execute_system_workflow(self, wf_id, task_mapping, deployment=None,
                                 execution_parameters=None, timeout=0,
                                 created_at=None,
                                 verify_no_executions=True):
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
        :return: (async task object, execution object)
        """
        execution_id = str(uuid.uuid4())  # will also serve as the task id
        execution_parameters = execution_parameters or {}

        # currently, deployment env creation/deletion are not set as
        # system workflows
        is_system_workflow = wf_id not in (
            'create_deployment_environment', 'delete_deployment_environment')

        # It means that a system-wide workflow is about to be launched
        if deployment is None and verify_no_executions:
            self._check_for_any_active_executions()

        execution = models.Execution(
            id=execution_id,
            status=models.Execution.PENDING,
            created_at=created_at or str(datetime.now()),
            blueprint_id=deployment.blueprint_id if deployment else None,
            workflow_id=wf_id,
            deployment_id=deployment.id if deployment else None,
            error='',
            parameters=self._get_only_user_execution_parameters(
                execution_parameters),
            is_system_workflow=is_system_workflow)

        self.sm.put_execution(execution.id, execution)

        async_task = self.workflow_client.execute_system_workflow(
            wf_id=wf_id,
            task_id=execution_id,
            task_mapping=task_mapping,
            deployment=deployment,
            execution_parameters=execution_parameters)

        if timeout > 0:
            try:
                # wait for the workflow execution to complete
                async_task.get(timeout=timeout, propagate=True)
            except Exception as e:
                # error message for the user
                if deployment:
                    add_info = ' for deployment {0}'.format(deployment.id)
                else:
                    add_info = ''
                error_msg = 'Error occurred while executing the {0} ' \
                            'system workflow{1}: {2} - {3}'.format(
                                wf_id, add_info, type(e).__name__, e)
                # adding traceback to the log error message
                tb = StringIO()
                traceback.print_exc(file=tb)
                log_error_msg = '{0}; traceback: {1}'.format(
                    error_msg, tb.getvalue())
                current_app.logger.error(log_error_msg)
                raise RuntimeError(error_msg)

            # verify the execution completed successfully
            execution = self.sm.get_execution(async_task.id)
            if execution.status != models.Execution.TERMINATED:
                raise RuntimeError(
                    'Failed executing the {0} system workflow: '
                    'Execution did not complete successfully before '
                    'timeout ({1} seconds)'.format(wf_id, timeout))

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

        execution = self.get_execution(execution_id)
        if execution.status not in (models.Execution.PENDING,
                                    models.Execution.STARTED) and \
                (not force or execution.status != models.Execution
                    .CANCELLING):
            raise manager_exceptions.IllegalActionError(
                "Can't {0}cancel execution {1} because it's in status {2}"
                .format(
                    'force-' if force else '',
                    execution_id,
                    execution.status))

        new_status = models.Execution.CANCELLING if not force \
            else models.Execution.FORCE_CANCELLING
        self.sm.update_execution_status(
            execution_id, new_status, '')
        return self.get_execution(execution_id)

    def create_deployment(self, blueprint_id, deployment_id, inputs=None):
        blueprint = self.get_blueprint(blueprint_id)
        plan = blueprint.plan
        try:
            deployment_plan = tasks.prepare_deployment_plan(plan, inputs)
        except parser_exceptions.MissingRequiredInputError, e:
            raise manager_exceptions.MissingRequiredDeploymentInputError(
                str(e))
        except parser_exceptions.UnknownInputError, e:
            raise manager_exceptions.UnknownDeploymentInputError(str(e))

        now = str(datetime.now())
        new_deployment = models.Deployment(
            id=deployment_id,
            blueprint_id=blueprint_id, created_at=now, updated_at=now,
            workflows=deployment_plan['workflows'],
            inputs=deployment_plan['inputs'],
            policy_types=deployment_plan['policy_types'],
            policy_triggers=deployment_plan['policy_triggers'],
            groups=deployment_plan['groups'],
            outputs=deployment_plan['outputs'])

        self.sm.put_deployment(deployment_id, new_deployment)
        self._create_deployment_nodes(blueprint_id,
                                      deployment_id,
                                      deployment_plan)

        node_instances = deployment_plan['node_instances']
        self._create_deployment_node_instances(deployment_id,
                                               node_instances)
        self._create_deployment_environment(new_deployment, deployment_plan)
        return new_deployment

    def start_deployment_modification(self,
                                      deployment_id,
                                      modified_nodes,
                                      context):
        # verify deployment exists
        self.sm.get_deployment(deployment_id, include=['id'])

        deployment_id_filter = self.create_filters_dict(
            deployment_id=deployment_id)
        existing_modifications = self.sm.deployment_modifications_list(
            include=['id', 'status']).items
        active_modifications = [
            m.id for m in existing_modifications
            if m.status == models.DeploymentModification.STARTED]
        if active_modifications:
            raise \
                manager_exceptions.ExistingStartedDeploymentModificationError(
                    'Cannot start deployment modification while there are '
                    'existing started deployment modifications. Currently '
                    'started deployment modifications: {0}'
                    .format(active_modifications))

        nodes = [node.to_dict() for node in self.sm.get_nodes(
            filters=deployment_id_filter).items]
        node_instances = [instance.to_dict() for instance
                          in self.sm.get_node_instances(
                          filters=deployment_id_filter).items]
        node_instances_modification = tasks.modify_deployment(
            nodes=nodes,
            previous_node_instances=node_instances,
            modified_nodes=modified_nodes)

        node_instances_modification['before_modification'] = [
            instance.to_dict() for instance in
            self.sm.get_node_instances(filters=deployment_id_filter).items]

        now = str(datetime.now())
        modification_id = str(uuid.uuid4())
        modification = models.DeploymentModification(
            id=modification_id,
            created_at=now,
            ended_at=None,
            status=models.DeploymentModification.STARTED,
            deployment_id=deployment_id,
            modified_nodes=modified_nodes,
            node_instances=node_instances_modification,
            context=context)
        self.sm.put_deployment_modification(modification_id, modification)

        for node_id, modified_node in modified_nodes.items():
            self.sm.update_node(
                modification.deployment_id, node_id,
                planned_number_of_instances=modified_node['instances'])
        added_and_related = node_instances_modification['added_and_related']
        added_node_instances = []
        for node_instance in added_and_related:
            if node_instance.get('modification') == 'added':
                added_node_instances.append(node_instance)
            else:
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
        self._create_deployment_node_instances(deployment_id,
                                               added_node_instances)
        return modification

    def finish_deployment_modification(self, modification_id):
        modification = self.sm.get_deployment_modification(modification_id)

        if modification.status in models.DeploymentModification.END_STATES:
            raise manager_exceptions.DeploymentModificationAlreadyEndedError(
                'Cannot finish deployment modification: {0}. It is already in'
                ' {1} status.'.format(modification_id,
                                      modification.status))

        modified_nodes = modification.modified_nodes
        for node_id, modified_node in modified_nodes.items():
            self.sm.update_node(modification.deployment_id, node_id,
                                number_of_instances=modified_node['instances'])
        node_instances = modification.node_instances
        for node_instance in node_instances['removed_and_related']:
            if node_instance.get('modification') == 'removed':
                self.sm.delete_node_instance(node_instance['id'])
            else:
                removed_relationship_target_ids = set(
                    [rel['target_id']
                     for rel in node_instance['relationships']])
                current = self.sm.get_node_instance(node_instance['id'])
                new_relationships = [rel for rel in current.relationships
                                     if rel['target_id']
                                     not in removed_relationship_target_ids]
                self.sm.update_node_instance(models.DeploymentNodeInstance(
                    id=node_instance['id'],
                    relationships=new_relationships,
                    version=current.version,
                    node_id=None,
                    host_id=None,
                    deployment_id=None,
                    state=None,
                    runtime_properties=None))

        now = str(datetime.now())
        self.sm.update_deployment_modification(
            models.DeploymentModification(
                id=modification_id,
                status=models.DeploymentModification.FINISHED,
                ended_at=now,
                created_at=None,
                deployment_id=None,
                modified_nodes=None,
                node_instances=None,
                context=None))

        return models.DeploymentModification(
            id=modification_id,
            status=models.DeploymentModification.FINISHED,
            ended_at=None,
            created_at=None,
            deployment_id=None,
            modified_nodes=None,
            node_instances=None,
            context=None)

    def rollback_deployment_modification(self, modification_id):
        modification = self.sm.get_deployment_modification(modification_id)

        if modification.status in models.DeploymentModification.END_STATES:
            raise manager_exceptions.DeploymentModificationAlreadyEndedError(
                'Cannot rollback deployment modification: {0}. It is already '
                'in {1} status.'.format(modification_id,
                                        modification.status))
        deplyment_id_filter = self.create_filters_dict(
            deployment_id=modification.deployment_id)
        node_instances = self.sm.get_node_instances(
            filters=deplyment_id_filter).items
        modification.node_instances['before_rollback'] = [
            instance.to_dict() for instance in node_instances]
        for instance in node_instances:
            self.sm.delete_node_instance(instance.id)
        for instance in modification.node_instances['before_modification']:
            self.sm.put_node_instance(
                models.DeploymentNodeInstance(**instance))
        nodes_num_instances = {node.id: node for node in self.sm.get_nodes(
            filters=deplyment_id_filter,
            include=['id', 'number_of_instances']).items}
        for node_id, modified_node in modification.modified_nodes.items():
            self.sm.update_node(
                modification.deployment_id, node_id,
                planned_number_of_instances=nodes_num_instances[
                    node_id].number_of_instances)

        now = str(datetime.now())
        self.sm.update_deployment_modification(
            models.DeploymentModification(
                id=modification_id,
                status=models.DeploymentModification.ROLLEDBACK,
                ended_at=now,
                created_at=None,
                deployment_id=None,
                modified_nodes=None,
                node_instances=modification.node_instances,
                context=None))

        return models.DeploymentModification(
            id=modification_id,
            status=models.DeploymentModification.ROLLEDBACK,
            ended_at=None,
            created_at=None,
            deployment_id=None,
            modified_nodes=None,
            node_instances=None,
            context=None)

    def _get_node_instance_ids(self, deployment_id):
        deplyment_id_filter = self.create_filters_dict(
            deployment_id=deployment_id)
        return self.sm.get_node_instances(filters=deplyment_id_filter,
                                          include=['id'])

    def _create_deployment_node_instances(self,
                                          deployment_id,
                                          dsl_node_instances):
        for node_instance in dsl_node_instances:
            instance_id = node_instance['id']
            node_id = node_instance['node_id']
            relationships = node_instance.get('relationships', [])
            host_id = node_instance.get('host_id')
            instance = models.DeploymentNodeInstance(
                id=instance_id,
                node_id=node_id,
                host_id=host_id,
                relationships=relationships,
                deployment_id=deployment_id,
                state='uninitialized',
                runtime_properties={},
                version=None)
            self.sm.put_node_instance(instance)

    def evaluate_deployment_outputs(self, deployment_id):
        deployment = self.get_deployment(
            deployment_id, include=['outputs'])

        def get_node_instances(node_id=None):
            filters = self.create_filters_dict(deployment_id=deployment_id,
                                               node_id=node_id)
            return self.sm.get_node_instances(filters=filters).items

        def get_node_instance(node_instance_id):
            return self.sm.get_node_instance(node_instance_id)

        def get_node(node_id):
            return self.sm.get_node(deployment_id, node_id)

        try:
            return functions.evaluate_outputs(
                outputs_def=deployment.outputs,
                get_node_instances_method=get_node_instances,
                get_node_instance_method=get_node_instance,
                get_node_method=get_node)
        except parser_exceptions.FunctionEvaluationError, e:
            raise manager_exceptions.DeploymentOutputsEvaluationError(str(e))

    def evaluate_functions(self, deployment_id, context, payload):
        self.get_deployment(deployment_id, include=['id'])

        def get_node_instances(node_id=None):
            filters = self.create_filters_dict(deployment_id=deployment_id,
                                               node_id=node_id)
            return self.sm.get_node_instances(filters=filters).items

        def get_node_instance(node_instance_id):
            return self.sm.get_node_instance(node_instance_id)

        def get_node(node_id):
            return self.sm.get_node(deployment_id, node_id)

        try:
            return functions.evaluate_functions(
                payload=payload,
                context=context,
                get_node_instances_method=get_node_instances,
                get_node_instance_method=get_node_instance,
                get_node_method=get_node)
        except parser_exceptions.FunctionEvaluationError, e:
            raise manager_exceptions.FunctionsEvaluationError(str(e))

    def _create_deployment_nodes(self, blueprint_id, deployment_id, plan,
                                 node_ids=None):
        """
        create deployment nodes in storage based on a provided blueprint
        :param blueprint_id: blueprint id
        :param deployment_id: deployment id
        :param plan: blueprint plan
        :param node_ids: optionally create only nodes with these ids
        """
        node_ids = node_ids or []
        if not isinstance(node_ids, list):
            node_ids = [node_ids]

        raw_nodes = plan['nodes']
        if node_ids:
            raw_nodes = \
                [node for node in raw_nodes if node['id'] in node_ids]
        for raw_node in raw_nodes:
            num_instances = raw_node['instances']['deploy']
            self.sm.put_node(models.DeploymentNode(
                id=raw_node['name'],
                deployment_id=deployment_id,
                blueprint_id=blueprint_id,
                type=raw_node['type'],
                type_hierarchy=raw_node['type_hierarchy'],
                number_of_instances=num_instances,
                planned_number_of_instances=num_instances,
                deploy_number_of_instances=num_instances,
                host_id=raw_node['host_id'] if 'host_id' in raw_node else None,
                properties=raw_node['properties'],
                operations=raw_node['operations'],
                plugins=raw_node['plugins'],
                plugins_to_install=raw_node.get('plugins_to_install'),
                relationships=self._prepare_node_relationships(raw_node)
            ))

    @staticmethod
    def _merge_and_validate_execution_parameters(
            workflow, workflow_name, execution_parameters=None,
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

        for param_name, param in workflow_parameters.iteritems():
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
            deployment_id=deployment_id)
        env_creation = next(
            (execution for execution in
             self.sm.executions_list(filters=deployment_id_filter).items
             if execution.workflow_id == 'create_deployment_environment'),
            None)

        if not env_creation:
            raise RuntimeError('Failed to find "create_deployment_environment"'
                               ' execution for deployment {0}'.format(
                                   deployment_id))
        status = env_creation.status
        if status == models.Execution.TERMINATED:
            return
        elif status == models.Execution.PENDING:
            raise manager_exceptions \
                .DeploymentEnvironmentCreationPendingError(
                    'Deployment environment creation is still pending, '
                    'try again in a minute')
        elif status == models.Execution.STARTED:
            raise manager_exceptions\
                .DeploymentEnvironmentCreationInProgressError(
                    'Deployment environment creation is still in progress, '
                    'try again in a minute')
        elif status == models.Execution.FAILED:
            raise RuntimeError(
                "Can't launch executions since environment creation for "
                "deployment {0} has failed: {1}".format(
                    deployment_id, env_creation.error))
        elif status in (
            models.Execution.CANCELLED, models.Execution.CANCELLING,
                models.Execution.FORCE_CANCELLING):
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

    def _create_deployment_environment(self, deployment, deployment_plan):
        wf_id = 'create_deployment_environment'
        deployment_env_creation_task_name = \
            'cloudify_system_workflows.deployment_environment.create'

        self._execute_system_workflow(
            wf_id=wf_id,
            task_mapping=deployment_env_creation_task_name,
            deployment=deployment,
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
                }
            }
        )

    def _delete_deployment_environment(self, deployment_id):
        deployment = self.sm.get_deployment(deployment_id)
        blueprint = self.sm.get_blueprint(deployment.blueprint_id)
        wf_id = 'delete_deployment_environment'
        deployment_env_deletion_task_name = \
            'cloudify_system_workflows.deployment_environment.delete'

        self._execute_system_workflow(
            wf_id=wf_id,
            task_mapping=deployment_env_deletion_task_name,
            deployment=deployment,
            timeout=300,
            execution_parameters={
                'deployment_plugins_to_uninstall': blueprint.plan[
                    constants.DEPLOYMENT_PLUGINS_TO_INSTALL],
                'workflow_plugins_to_uninstall': blueprint.plan[
                    constants.WORKFLOW_PLUGINS_TO_INSTALL],
            })

    def _delete_deployment_logs(self, deployment_id):
        self._execute_system_workflow(
            wf_id='delete_deployment_logs',
            task_mapping='cloudify_system_workflows.deployment_environment'
                         '.delete_logs',
            execution_parameters={
                'deployment_id': deployment_id
            },
            verify_no_executions=False,
            timeout=300,
        )

    def _check_for_active_executions(self, deployment_id, force):

        def _get_running_executions(deployment_id=None, include_system=True):
            deployment_id_filter = self.create_filters_dict(
                deployment_id=deployment_id)
            executions = self.executions_list(
                filters=deployment_id_filter,
                is_include_system_workflows=include_system).items
            running = [
                e.id for e in executions if
                self.sm.get_execution(e.id).status
                not in models.Execution.END_STATES]
            return running

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

    @staticmethod
    def _extract_parser_context(context):
        context = context or {}
        cloudify_section = context.get(constants.CLOUDIFY, {})
        return {
            'resolver_section': cloudify_section.get(
                constants.IMPORT_RESOLVER_KEY),
            'validate_definitions_version': cloudify_section.get(
                constants.VALIDATE_DEFINITIONS_VERSION, True)
        }

    def _get_parser_context(self):
        if not hasattr(current_app, 'parser_context'):
            self._update_parser_context_in_app(
                self.sm.get_provider_context().context)
        return current_app.parser_context

    def _update_parser_context_in_app(self, context):
        raw_parser_context = self._extract_parser_context(context)
        resolver = dsl_parser_utils.create_import_resolver(
            raw_parser_context['resolver_section'])
        validate_definitions_version = raw_parser_context[
            'validate_definitions_version']
        current_app.parser_context = {
            'resolver': resolver,
            'validate_version': validate_definitions_version
        }

    def update_provider_context(self, update, provider_context):
        if update:
            self.sm.update_provider_context(provider_context)
        else:
            self.sm.put_provider_context(provider_context)
        self._update_parser_context_in_app(provider_context.context)


# What we need to access this manager in Flask
def get_blueprints_manager():
    """
    Get the current app's blueprints manager, create if necessary
    """
    manager = current_app.config.get('blueprints_manager')
    if not manager:
        current_app.config['blueprints_manager'] = BlueprintsManager()
        manager = current_app.config.get('blueprints_manager')
    return manager
