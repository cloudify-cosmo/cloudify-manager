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

__author__ = 'dan'


import json
import time
import uuid
from datetime import datetime
from flask import g, current_app

from dsl_parser import tasks
from manager_rest import models
from manager_rest import manager_exceptions
from manager_rest.workflow_client import workflow_client
from manager_rest.storage_manager import get_storage_manager
from manager_rest.util import maybe_register_teardown
from manager_rest.celery_client import celery_client
from manager_rest.celery_client import TASK_STATE_FAILURE as \
    CELERY_TASK_STATE_FAILURE


class DslParseException(Exception):
    pass


class BlueprintAlreadyExistsException(Exception):
    def __init__(self, blueprint_id, *args):
        Exception.__init__(self, args)
        self.blueprint_id = blueprint_id


class BlueprintsManager(object):

    @property
    def sm(self):
        return get_storage_manager()

    def blueprints_list(self, include=None):
        return self.sm.blueprints_list(include=include)

    def deployments_list(self, include=None):
        return self.sm.deployments_list(include=include)

    def executions_list(self, include=None):
        return self.sm.executions_list(include=include)

    def get_blueprint(self, blueprint_id, include=None):
        return self.sm.get_blueprint(blueprint_id, include=include)

    def get_deployment(self, deployment_id, include=None):
        return self.sm.get_deployment(deployment_id, include=include)

    def get_execution(self, execution_id, include=None):
        return self.sm.get_execution(execution_id, include=include)

    def get_deployment_executions(self, deployment_id, include=None):
        return self.sm.get_deployment_executions(deployment_id,
                                                 include=include)

    # TODO: call celery tasks instead of doing this directly here
    # TODO: prepare multi instance plan should be called on workflow execution
    def publish_blueprint(self, dsl_location, alias_mapping_url,
                          resources_base_url, blueprint_id):
        # TODO: error code if parsing fails (in one of the 2 tasks)
        try:
            plan = tasks.parse_dsl(dsl_location, alias_mapping_url,
                                   resources_base_url)
        except Exception, ex:
            raise DslParseException(*ex.args)

        now = str(datetime.now())
        parsed_plan = json.loads(plan)

        new_blueprint = models.BlueprintState(plan=parsed_plan,
                                              id=blueprint_id,
                                              created_at=now, updated_at=now)
        self.sm.put_blueprint(new_blueprint.id, new_blueprint)
        return new_blueprint

    def delete_blueprint(self, blueprint_id):
        blueprint_deployments = get_storage_manager()\
            .get_blueprint_deployments(blueprint_id)

        if len(blueprint_deployments) > 0:
            raise manager_exceptions.DependentExistsError(
                "Can't delete blueprint {0} - There exist "
                "deployments for this blueprint; Deployments ids: {1}"
                .format(blueprint_id,
                        ','.join([dep.id for dep
                                  in blueprint_deployments])))

        return get_storage_manager().delete_blueprint(blueprint_id)

    def delete_deployment(self, deployment_id, ignore_live_nodes=False):
        storage = get_storage_manager()

        # Verify deployment exists.
        storage.get_deployment(deployment_id)

        # validate there are no running executions for this deployment
        executions = storage.get_deployment_executions(deployment_id)
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
            node_instances = storage.get_node_instances(
                deployment_id=deployment_id)
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

        self._uninstall_deployment_workers(deployment_id)
        return storage.delete_deployment(deployment_id)

    def execute_workflow(self, deployment_id, workflow_id,
                         parameters=None,
                         allow_custom_parameters=False, force=False):
        deployment = self.get_deployment(deployment_id)

        if workflow_id not in deployment.workflows:
            raise manager_exceptions.NonexistentWorkflowError(
                'Workflow {0} does not exist in deployment {1}'.format(
                    workflow_id, deployment_id))
        workflow = deployment.workflows[workflow_id]

        self._verify_deployment_workers_installed_successfully(deployment_id)

        # validate no execution is currently in progress
        if not force:
            executions = self.get_deployment_executions(deployment_id)
            running = [
                e.id for e in executions if
                get_storage_manager().get_execution(e.id).status
                not in models.Execution.END_STATES]
            if len(running) > 0:
                raise manager_exceptions.ExistingRunningExecutionError(
                    'The following executions are currently running for this '
                    'deployment: {0}. To execute this workflow anyway, pass '
                    '"force=true" as a query parameter to this request'.format(
                        running))

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
                execution_parameters))

        get_storage_manager().put_execution(new_execution.id, new_execution)

        workflow_client().execute_workflow(
            workflow_id,
            workflow,
            blueprint_id=deployment.blueprint_id,
            deployment_id=deployment_id,
            execution_id=execution_id,
            execution_parameters=execution_parameters)

        return new_execution

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
        get_storage_manager().update_execution_status(
            execution_id, new_status, '')
        return self.get_execution(execution_id)

    def create_deployment(self, blueprint_id, deployment_id):
        blueprint = self.get_blueprint(blueprint_id)
        plan = blueprint.plan
        deployment_json_plan = tasks.prepare_deployment_plan(plan)
        deployment_plan = json.loads(deployment_json_plan)

        now = str(datetime.now())
        new_deployment = models.Deployment(
            id=deployment_id,
            blueprint_id=blueprint_id, created_at=now, updated_at=now,
            workflows=deployment_plan['workflows'])

        self.sm.put_deployment(deployment_id, new_deployment)
        self._create_deployment_nodes(blueprint_id, deployment_id, plan)

        self._install_deployment_workers(new_deployment, deployment_plan, now)

        node_instances = deployment_plan['node_instances']
        for node_instance in node_instances:
            instance_id = node_instance['id']
            node_id = node_instance['name']
            relationships = node_instance.get('relationships', [])
            host_id = node_instance.get('host_id')

            instance = models.DeploymentNodeInstance(
                id=instance_id,
                node_id=node_id,
                host_id=host_id,
                relationships=relationships,
                deployment_id=deployment_id,
                state='uninitialized',
                runtime_properties=None,
                version=None)
            self.sm.put_node_instance(instance)

        self._wait_for_count(expected_count=len(node_instances),
                             query_method=self.sm.get_node_instances,
                             deployment_id=deployment_id)

        return new_deployment

    def _create_deployment_nodes(self, blueprint_id, deployment_id, plan):
        for raw_node in plan['nodes']:
            self.sm.put_node(models.DeploymentNode(
                id=raw_node['name'],
                deployment_id=deployment_id,
                blueprint_id=blueprint_id,
                type=raw_node['type'],
                type_hierarchy=raw_node['type_hierarchy'],
                number_of_instances=raw_node['instances']['deploy'],
                host_id=raw_node['host_id'] if 'host_id' in raw_node else None,
                properties=raw_node['properties'],
                operations=raw_node['operations'],
                plugins=raw_node['plugins'],
                plugins_to_install=raw_node.get('plugins_to_install'),
                relationships=self._prepare_node_relationships(raw_node)
            ))

        self._wait_for_count(expected_count=len(plan['nodes']),
                             query_method=self.sm.get_nodes,
                             deployment_id=deployment_id)

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

    def _verify_deployment_workers_installed_successfully(self,
                                                          deployment_id,
                                                          is_retry=False):
        workers_installation_execution = next(
            (execution for execution in
             get_storage_manager().get_deployment_executions(
                 deployment_id) if execution.workflow_id ==
                'workers_installation'),
            None)

        if not workers_installation_execution:
            raise RuntimeError('Failed to find "workers_installation" '
                               'execution for deployment {0}'.format(
                                   deployment_id))

        # Because of ES eventual consistency, we need to get the execution by
        # its id in order to make sure the read status is correct.
        workers_installation_execution = get_storage_manager().get_execution(
            workers_installation_execution.id)

        if workers_installation_execution.status == \
                models.Execution.TERMINATED:
            # workers installation is complete
            return
        elif workers_installation_execution.status == models.Execution.STARTED:
            # workers installation is still in process
            raise manager_exceptions\
                .DeploymentWorkersNotYetInstalledError(
                    'Deployment workers are still being installed, '
                    'try again in a minute')
        elif workers_installation_execution.status == models.Execution.FAILED:
            # workers installation workflow failed
            raise RuntimeError(
                "Can't launch executions since workers for deployment {0} "
                'failed to be installed: {1}'.format(
                    deployment_id, workers_installation_execution.error))
        elif workers_installation_execution.status in (
            models.Execution.CANCELLED, models.Execution.CANCELLING,
                models.Execution.FORCE_CANCELLING):
            # workers installation workflow is got cancelled
            raise RuntimeError(
                "Can't launch executions since workers for deployment {0} "
                'installation has been cancelled [status={1}]'.format(
                    deployment_id, workers_installation_execution.status))

        # status is 'pending'. Waiting for a few seconds and retrying to
        # verify (to avoid eventual consistency issues). If this is already a
        # failed retry, it might mean there was a problem with the Celery task
        if not is_retry:
            time.sleep(5)
            self._verify_deployment_workers_installed_successfully(
                deployment_id, True)
        else:
            # workers installation failed but not on the workflow level -
            # retrieving the celery task's status for the error message,
            # and the error object from celery if one is available
            celery_task_status = celery_client().get_task_status(
                workers_installation_execution.id)
            error_message = \
                "Can't launch executions since workers for deployment {0}" \
                " haven't been installed (Execution status is still " \
                "'{1}'). Celery task status is ".format(
                    deployment_id, workers_installation_execution.status)
            if celery_task_status != CELERY_TASK_STATE_FAILURE:
                raise RuntimeError(
                    "{0} {1}".format(error_message, celery_task_status))
            else:
                celery_error = celery_client().get_failed_task_error(
                    workers_installation_execution.id)
                raise RuntimeError(
                    "{0} {1}; Error is of type {2}; Error message: {3}"
                    .format(error_message, celery_task_status,
                            celery_error.__class__.__name__, celery_error))

    def _install_deployment_workers(self,
                                    deployment,
                                    deployment_plan,
                                    now):
        workers_installation_task_id = str(uuid.uuid4())
        wf_id = 'workers_installation'
        workers_install_task_name = \
            'system_workflows.workers_installation.install'

        context = self._build_context_from_deployment(
            deployment, workers_installation_task_id, wf_id,
            workers_install_task_name)
        kwargs = {
            'management_plugins_to_install': deployment_plan[
                'management_plugins_to_install'],
            'workflow_plugins_to_install': deployment_plan[
                'workflow_plugins_to_install'],
            'policy_configuration': {
                'policy_types': deployment_plan['policy_types'],
                'groups': deployment_plan['groups']
            },
            '__cloudify_context': context
        }

        new_execution = models.Execution(
            id=workers_installation_task_id,
            status=models.Execution.PENDING,
            created_at=now,
            blueprint_id=deployment.blueprint_id,
            workflow_id=wf_id,
            deployment_id=deployment.id,
            error='',
            parameters=self._get_only_user_execution_parameters(kwargs))
        get_storage_manager().put_execution(new_execution.id, new_execution)

        celery_client().execute_task(
            workers_install_task_name,
            'cloudify.management',
            workers_installation_task_id,
            kwargs=kwargs)

    def _build_context_from_deployment(self, deployment, task_id, wf_id,
                                       task_name):
        return {
            'task_id': task_id,
            'task_name': task_name,
            'task_target': 'cloudify.management',
            'blueprint_id': deployment.blueprint_id,
            'deployment_id': deployment.id,
            'execution_id': task_id,
            'workflow_id': wf_id,
        }

    def _uninstall_deployment_workers(self, deployment_id):
        deployment = get_storage_manager().get_deployment(deployment_id)

        workers_uninstallation_task_id = str(uuid.uuid4())
        wf_id = 'workers_uninstallation'
        workers_uninstall_task_name = \
            'system_workflows.workers_installation.uninstall'

        context = self._build_context_from_deployment(
            deployment,
            workers_uninstallation_task_id,
            wf_id,
            workers_uninstall_task_name)
        kwargs = {'__cloudify_context': context}

        new_execution = models.Execution(
            id=workers_uninstallation_task_id,
            status=models.Execution.PENDING,
            created_at=str(datetime.now()),
            blueprint_id=deployment.blueprint_id,
            workflow_id=wf_id,
            deployment_id=deployment_id,
            error='',
            parameters=self._get_only_user_execution_parameters(kwargs))
        get_storage_manager().put_execution(new_execution.id, new_execution)

        uninstall_workers_task_async_result = celery_client().execute_task(
            workers_uninstall_task_name,
            'cloudify.management',
            workers_uninstallation_task_id,
            kwargs=kwargs)

        # wait for workers uninstall to complete
        uninstall_workers_task_async_result.get(timeout=300,
                                                propagate=True)
        # verify uninstall completed successfully
        execution = get_storage_manager().get_execution(
            workers_uninstallation_task_id)
        if execution.status != models.Execution.TERMINATED:
            raise RuntimeError('Failed to uninstall deployment workers for '
                               'deployment {0}'.format(deployment_id))

    def _get_only_user_execution_parameters(self, execution_parameters):
        return {k: v for k, v in execution_parameters.iteritems()
                if not k.startswith('__')}

    @staticmethod
    def _wait_for_count(expected_count, query_method, deployment_id):
        import time
        timeout = time.time() + 30
        # workaround ES eventual consistency
        # TODO check if there is a count query and do that
        actual_count = len(query_method(deployment_id))
        while actual_count < expected_count and time.time() < timeout:
            time.sleep(1)
            actual_count = len(query_method(deployment_id))
        if actual_count < expected_count:
            raise RuntimeError('Timed out while waiting for nodes count')


def teardown_blueprints_manager(exception):
    # print "tearing down blueprints manager!"
    pass


# What we need to access this manager in Flask
def get_blueprints_manager():
    """
    Get the current blueprints manager
    or create one if none exists for the current app context
    """
    if 'blueprints_manager' not in g:
        g.blueprints_manager = BlueprintsManager()
        maybe_register_teardown(current_app, teardown_blueprints_manager)
    return g.blueprints_manager
