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
from manager_rest.util import maybe_register_teardown

__author__ = 'dan'


from datetime import datetime
import json
import uuid
import contextlib

from dsl_parser import tasks
from urllib2 import urlopen
from flask import g, current_app

from manager_rest import models
from manager_rest import responses
from manager_rest import manager_exceptions
from manager_rest.workflow_client import workflow_client
from manager_rest.storage_manager import get_storage_manager


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

    def blueprints_list(self):
        return self.sm.blueprints_list()

    def deployments_list(self):
        return self.sm.deployments_list()

    def executions_list(self):
        return self.sm.executions_list()

    def get_blueprint(self, blueprint_id, fields=None):
        return self.sm.get_blueprint(blueprint_id, fields)

    def get_deployment(self, deployment_id):
        return self.sm.get_deployment(deployment_id)

    def get_execution(self, execution_id):
        return self.sm.get_execution(execution_id)

    # TODO: call celery tasks instead of doing this directly here
    # TODO: prepare multi instance plan should be called on workflow execution
    def publish_blueprint(self, dsl_location, alias_mapping_url,
                          resources_base_url, blueprint_id=None):
        # TODO: error code if parsing fails (in one of the 2 tasks)
        try:
            plan = tasks.parse_dsl(dsl_location, alias_mapping_url,
                                   resources_base_url)

            with contextlib.closing(urlopen(dsl_location)) as f:
                source = f.read()
        except Exception, ex:
            raise DslParseException(*ex.args)

        now = str(datetime.now())
        parsed_plan = json.loads(plan)
        if not blueprint_id:
            blueprint_id = parsed_plan['name']

        new_blueprint = models.BlueprintState(plan=parsed_plan,
                                              id=blueprint_id,
                                              created_at=now, updated_at=now,
                                              source=source)
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
        deployment = get_storage_manager().get_deployment(deployment_id)

        deployment_executions =\
            get_storage_manager().get_deployment_executions(deployment_id)

        deployment_executions = [self.get_workflow_state(execution.id) for
                                 execution in deployment_executions]

        # validate there are no running executions for this deployment
        if any(execution.status not in ('terminated', 'failed') for
           execution in deployment_executions):
            raise manager_exceptions.DependentExistsError(
                "Can't delete deployment {0} - There are running "
                "executions for this deployment. Running executions ids: {1}"
                .format(
                    deployment_id,
                    ','.join([execution.id for execution in
                              deployment_executions if execution.status not
                              in ('terminated', 'failed')])))

        deployment_nodes_ids = [node['id'] for node in
                                deployment.plan['nodes']]
        if not ignore_live_nodes:
            deployment_nodes = [get_storage_manager().get_node(node_id) for
                                node_id in deployment_nodes_ids]
            # validate either all nodes for this deployment are still
            # uninitialized or have been deleted
            if any(node.state not in ('uninitialized', 'deleted') for node in
                   deployment_nodes):
                raise manager_exceptions.DependentExistsError(
                    "Can't delete deployment {0} - There are live nodes for "
                    "this deployment. Live nodes ids: {1}"
                    .format(deployment_id,
                            ','.join([node.id for node in deployment_nodes
                                     if node.state not in
                                     ('uninitialized', 'deleted')])))

        # delete deployment resources
        for execution in deployment_executions:
            get_storage_manager().delete_execution(execution.id)

        for node_id in deployment_nodes_ids:
            get_storage_manager().delete_node(node_id)

        return get_storage_manager().delete_deployment(deployment_id)

    # currently validation is split to 2 phases: the first
    # part is during submission (dsl parsing)
    # second part is during call to validate which simply delegates
    # the plan to the workflow service
    # so we can parse all the workflows and see things are ok
    def validate_blueprint(self, blueprint_id):
        blueprint = self.get_blueprint(blueprint_id)
        plan = blueprint.plan
        response = workflow_client().validate_workflows(plan)
        # TODO raise error if error
        return responses.BlueprintValidationStatus(
            blueprint_id=blueprint_id, status=response['status'])

    def execute_workflow(self, deployment_id, workflow_id):
        deployment = self.get_deployment(deployment_id)

        if workflow_id not in deployment.plan['workflows']:
            raise manager_exceptions.NonexistentWorkflowError(
                'Workflow {0} does not exist in deployment {1}'.format(
                    workflow_id, deployment_id))
        workflow = deployment.plan['workflows'][workflow_id]
        plan = deployment.plan

        execution_id = str(uuid.uuid4())
        response = workflow_client().execute_workflow(
            workflow_id,
            workflow, plan,
            blueprint_id=deployment.blueprint_id,
            deployment_id=deployment_id,
            execution_id=execution_id)
        # TODO raise error if there is error in response

        new_execution = models.Execution(
            id=execution_id,
            status=response['state'],
            internal_workflow_id=response['id'],
            created_at=str(response['created']),
            blueprint_id=deployment.blueprint_id,
            workflow_id=workflow_id,
            deployment_id=deployment_id,
            error='None')

        get_storage_manager().put_execution(new_execution.id, new_execution)

        return new_execution

    def get_workflow_state(self, execution_id):
        execution = self.get_execution(execution_id)

        response = self.get_workflows_states_by_internal_workflows_ids(
            [execution.internal_workflow_id])

        if len(response) > 0:
            execution.status = response[0]['state']
            if execution.status == 'failed':
                execution.error = response[0]['error']
        else:
            # workflow not found in workflow-service, return unknown values
            execution.status, execution.error = None, None
        return execution

    def get_workflows_states_by_internal_workflows_ids(self,
                                                       internal_wfs_ids):
        return workflow_client().get_workflows_statuses(internal_wfs_ids)

    def cancel_workflow(self, execution_id):
        execution = self.get_execution(execution_id)
        workflow_client().cancel_workflow(
            execution.internal_workflow_id
        )
        return execution

    def create_deployment(self, blueprint_id, deployment_id):
        blueprint = self.get_blueprint(blueprint_id)
        plan = blueprint.plan
        deployment_json_plan = tasks.prepare_deployment_plan(plan)

        now = str(datetime.now())
        new_deployment = models.Deployment(
            id=deployment_id, plan=json.loads(deployment_json_plan),
            blueprint_id=blueprint_id, created_at=now, updated_at=now)

        self.sm.put_deployment(deployment_id, new_deployment)

        for plan_node in new_deployment.plan['nodes']:
            node_id = plan_node['id']
            node = models.DeploymentNode(id=node_id,
                                         state='uninitialized',
                                         runtime_info=None,
                                         state_version=None)
            self.sm.put_node(node_id, node)

        return new_deployment


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
