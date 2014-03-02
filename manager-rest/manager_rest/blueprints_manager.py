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

from dsl_parser import tasks
from flask import g, current_app

from manager_rest import models
from manager_rest import responses
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

    def get_blueprint(self, blueprint_id):
        return self.sm.get_blueprint(blueprint_id)

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
        except Exception, ex:
            raise DslParseException(*ex.args)

        now = str(datetime.now())
        parsed_plan = json.loads(plan)
        if not blueprint_id:
            blueprint_id = parsed_plan['name']
        new_blueprint = models.BlueprintState(plan=parsed_plan,
                                              id=blueprint_id,
                                              created_at=now, updated_at=now)
        if self.get_blueprint(new_blueprint.id) is not None:
            raise BlueprintAlreadyExistsException(new_blueprint.id)
        self.sm.put_blueprint(new_blueprint.id, new_blueprint)
        return new_blueprint

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

        self.sm.put_execution(new_execution.id, new_execution)

        return new_execution

    def get_workflow_state(self, execution_id):
        execution = self.get_execution(execution_id)
        response = workflow_client().get_workflow_status(
            execution.internal_workflow_id)
        execution.status = response['state']
        if execution.status == 'failed':
            execution.error = response['error']
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

        return new_deployment


def teardown_blueprints_manager(exception):
    #print "tearing down blueprints manager!"
    pass


# What we need to access this manager in Flask
def get_blueprints_manager():
    """
    Get the current blueprints manager
    or create one if none exists for the current app context
    """
    if not 'blueprints_manager' in g:
        g.blueprints_manager = BlueprintsManager()
        maybe_register_teardown(current_app, teardown_blueprints_manager)
    return g.blueprints_manager
