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
from datetime import datetime

from flask import g, current_app

from dsl_parser import exceptions as parser_exceptions
from dsl_parser import functions
from dsl_parser import tasks
from dsl_parser.constants import DEPLOYMENT_PLUGINS_TO_INSTALL
from manager_rest import models
from manager_rest import manager_exceptions
from manager_rest.workflow_client import workflow_client
from manager_rest.storage_manager import get_storage_manager
from manager_rest.utils import maybe_register_teardown
from manager_rest.celery_client import celery_client


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

    def executions_list(self, deployment_id=None, include=None):
        return self.sm.executions_list(deployment_id=deployment_id,
                                       include=include)

    def get_blueprint(self, blueprint_id, include=None):
        return self.sm.get_blueprint(blueprint_id, include=include)

    def get_deployment(self, deployment_id, include=None):
        return self.sm.get_deployment(deployment_id=deployment_id,
                                      include=include)

    def get_execution(self, execution_id, include=None):
        return self.sm.get_execution(execution_id, include=include)

    def publish_blueprint(self, dsl_location,
                          resources_base_url, blueprint_id):
        try:
            plan = tasks.parse_dsl(dsl_location, resources_base_url)
        except Exception, ex:
            raise DslParseException(str(ex))

        now = str(datetime.now())

        new_blueprint = models.BlueprintState(plan=plan,
                                              id=blueprint_id,
                                              created_at=now,
                                              updated_at=now)
        self.sm.put_blueprint(new_blueprint.id, new_blueprint)
        return new_blueprint

    def delete_blueprint(self, blueprint_id):
        blueprint_deployments = self.sm.get_blueprint_deployments(blueprint_id)

        if len(blueprint_deployments) > 0:
            raise manager_exceptions.DependentExistsError(
                "Can't delete blueprint {0} - There exist "
                "deployments for this blueprint; Deployments ids: {1}"
                .format(blueprint_id,
                        ','.join([dep.id for dep
                                  in blueprint_deployments])))

        return self.sm.delete_blueprint(blueprint_id)

    def delete_deployment(self, deployment_id, ignore_live_nodes=False):
        # Verify deployment exists.
        self.sm.get_deployment(deployment_id)

        # validate there are no running executions for this deployment
        executions = self.sm.executions_list(deployment_id=deployment_id)
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
            node_instances = self.sm.get_node_instances(
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

        self._delete_deployment_environment(deployment_id)
        return self.sm.delete_deployment(deployment_id)

    def _initiate_deployment_environment(self, deployment, parameters=None):
        """
            Sends task to celery workers to
            start workflow and deployment workers
            :param deployment: Deployment object
            :return:
        """
        deployment_env_init_task_name = (
            'cloudify_system_workflows.deployment_environment.initiate'
        )
        deployment_env_init_task_id = str(uuid.uuid4())
        wf_id = "initiate_deployment_environment"
        context = self._build_context_from_deployment(
            deployment,
            deployment_env_init_task_id,
            wf_id,
            deployment_env_init_task_name
        )

        _parameters = {} if not parameters else parameters
        _parameters.update({'__cloudify_context': context})

        new_execution = models.Execution(
            id=deployment_env_init_task_id,
            status=models.Execution.PENDING,
            created_at=str(datetime.now()),
            blueprint_id=deployment.blueprint_id,
            workflow_id=wf_id,
            deployment_id=deployment.id,
            error='',
            parameters=self._get_only_user_execution_parameters(_parameters))

        self.sm.put_execution(new_execution.id, new_execution)

        celery_class = celery_client()
        with celery_class() as cl:
            initiate_task = cl.execute_task(
                deployment_env_init_task_name,
                context['task_target'],
                deployment_env_init_task_id,
                kwargs=_parameters)

            # usually it takes from 5 up to 10 seconds
            initiate_task.get(timeout=300,
                              propagate=True)

    def execute_workflow(self, deployment_id, workflow_id,
                         parameters=None,
                         allow_custom_parameters=False, force=False):
        deployment = self.get_deployment(deployment_id)

        if workflow_id not in deployment.workflows:
            raise manager_exceptions.NonexistentWorkflowError(
                'Workflow {0} does not exist in deployment {1}'.format(
                    workflow_id, deployment_id))
        workflow = deployment.workflows[workflow_id]

        self._verify_deployment_environment_created_successfully(deployment_id)

        # validate no execution is currently in progress
        if not force:
            executions = self.sm.executions_list(
                deployment_id=deployment_id)
            running = [
                e.id for e in executions if
                self.sm.get_execution(e.id).status
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

        self._initiate_deployment_environment(deployment,
                                              parameters=execution_parameters)

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

        self.sm.put_execution(new_execution.id, new_execution)

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
        self._create_deployment_environment(new_deployment, deployment_plan,
                                            now)
        return new_deployment

    def start_deployment_modification(self,
                                      deployment_id,
                                      modified_nodes,
                                      context):
        # verify deployment exists
        self.sm.get_deployment(deployment_id, include=['id'])

        existing_modifications = self.sm.deployment_modifications_list(
            deployment_id=deployment_id, include=['id', 'status'])
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

        nodes = [node.to_dict() for node in self.sm.get_nodes(deployment_id)]
        node_instances = [instance.to_dict() for instance
                          in self.sm.get_node_instances(deployment_id)]
        node_instances_modification = tasks.modify_deployment(
            nodes=nodes,
            previous_node_instances=node_instances,
            modified_nodes=modified_nodes)

        node_instances_modification['before_modification'] = [
            instance.to_dict() for instance in
            self.sm.get_node_instances(deployment_id)]

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

        node_instances = self.sm.get_node_instances(modification.deployment_id)
        modification.node_instances['before_rollback'] = [
            instance.to_dict() for instance in node_instances]
        for instance in node_instances:
            self.sm.delete_node_instance(instance.id)
        for instance in modification.node_instances['before_modification']:
            self.sm.put_node_instance(
                models.DeploymentNodeInstance(**instance))
        nodes_num_instances = {node.id: node for node in self.sm.get_nodes(
            deployment_id=modification.deployment_id,
            include=['id', 'number_of_instances'])}
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
        return self.sm.get_node_instances(deployment_id, include=['id'])

    def _create_deployment_node_instances(self,
                                          deployment_id,
                                          dsl_node_instances):
        for node_instance in dsl_node_instances:
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
                runtime_properties={},
                version=None)
            self.sm.put_node_instance(instance)

    def evaluate_deployment_outputs(self, deployment_id):
        deployment = self.get_deployment(
            deployment_id, include=['outputs'])

        def get_node_instances(node_id=None):
            return self.sm.get_node_instances(deployment_id, node_id)

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
            return self.sm.get_node_instances(deployment_id, node_id)

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

    def _create_deployment_nodes(self, blueprint_id, deployment_id, plan):
        for raw_node in plan['nodes']:
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
        env_creation = next(
            (execution for execution in
             self.sm.executions_list(deployment_id=deployment_id)
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

    def _create_deployment_environment(self, deployment, deployment_plan, now):
        deployment_env_creation_task_id = str(uuid.uuid4())
        wf_id = 'create_deployment_environment'
        deployment_env_creation_task_name = \
            'cloudify_system_workflows.deployment_environment.create'

        context = self._build_context_from_deployment(
            deployment, deployment_env_creation_task_id, wf_id,
            deployment_env_creation_task_name)
        kwargs = {
            DEPLOYMENT_PLUGINS_TO_INSTALL: deployment_plan[
                DEPLOYMENT_PLUGINS_TO_INSTALL],
            'workflow_plugins_to_install': deployment_plan[
                'workflow_plugins_to_install'],
            'policy_configuration': {
                'policy_types': deployment_plan['policy_types'],
                'policy_triggers': deployment_plan['policy_triggers'],
                'groups': deployment_plan['groups'],
            },
            '__cloudify_context': context
        }

        new_execution = models.Execution(
            id=deployment_env_creation_task_id,
            status=models.Execution.PENDING,
            created_at=now,
            blueprint_id=deployment.blueprint_id,
            workflow_id=wf_id,
            deployment_id=deployment.id,
            error='',
            parameters=self._get_only_user_execution_parameters(kwargs))
        self.sm.put_execution(new_execution.id, new_execution)

        celery_class = celery_client()
        with celery_class() as cl:
            cl.execute_task(
                deployment_env_creation_task_name,
                'cloudify.management',
                deployment_env_creation_task_id,
                kwargs=kwargs)

    @staticmethod
    def _build_context_from_deployment(deployment, task_id, wf_id,
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

    def _delete_deployment_environment(self, deployment_id):
        deployment = self.sm.get_deployment(deployment_id)

        deployment_env_deletion_task_id = str(uuid.uuid4())
        wf_id = 'delete_deployment_environment'
        deployment_env_deletion_task_name = \
            'cloudify_system_workflows.deployment_environment.delete'

        context = self._build_context_from_deployment(
            deployment,
            deployment_env_deletion_task_id,
            wf_id,
            deployment_env_deletion_task_name)
        kwargs = {'__cloudify_context': context}

        new_execution = models.Execution(
            id=deployment_env_deletion_task_id,
            status=models.Execution.PENDING,
            created_at=str(datetime.now()),
            blueprint_id=deployment.blueprint_id,
            workflow_id=wf_id,
            deployment_id=deployment_id,
            error='',
            parameters=self._get_only_user_execution_parameters(kwargs))
        self.sm.put_execution(new_execution.id, new_execution)

        celery_class = celery_client()
        with celery_class() as cl:
            deployment_env_deletion_task_async_result = (
                cl.execute_task(
                    deployment_env_deletion_task_name,
                    'cloudify.management',
                    deployment_env_deletion_task_id,
                    kwargs=kwargs))

            # wait for deployment environment deletion to complete
            deployment_env_deletion_task_async_result.get(timeout=300,
                                                          propagate=True)
            # verify deployment environment deletion completed successfully
            execution = self.sm.get_execution(
                deployment_env_deletion_task_id)
            if execution.status != models.Execution.TERMINATED:
                raise RuntimeError(
                    'Failed to delete environment for deployment '
                    '{0}. Execution status: {1}'.format(
                        deployment_id, execution.status))

    @staticmethod
    def _get_only_user_execution_parameters(execution_parameters):
        return {k: v for k, v in execution_parameters.iteritems()
                if not k.startswith('__')}


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
