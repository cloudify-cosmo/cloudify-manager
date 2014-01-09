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

from dsl_parser import tasks
import json
import uuid
from responses import BlueprintState, Execution, BlueprintValidationStatus, \
    Deployment
from workflow_client import workflow_client


class DslParseException(Exception):
    pass


class BlueprintsManager(object):

    def __init__(self):
        self.blueprints = {}
        self.executions = {}
        self.deployments = {}

    def blueprints_list(self):
        return self.blueprints.values()

    def deployments_list(self):
        return self.deployments.values()

    def get_blueprint(self, blueprint_id):
        return self.blueprints.get(blueprint_id, None)

    def get_deployment(self, deployment_id):
        return self.deployments.get(deployment_id, None)

    def get_execution(self, execution_id):
        return self.executions.get(execution_id, None)

    # TODO: call celery tasks instead of doing this directly here
    # TODO: prepare multi instance plan should be called on workflow execution
    def publish_blueprint(self, blueprint_id, dsl_location, alias_mapping_url,
                          resources_base_url):
        # TODO: error code if parsing fails (in one of the 2 tasks)
        try:
            plan = tasks.parse_dsl(dsl_location, alias_mapping_url,
                                   resources_base_url)
        except Exception, ex:
            raise DslParseException(*ex.args)
        new_blueprint = BlueprintState(id=blueprint_id, json_plan=plan,
                                       plan=json.loads(plan))
        self.blueprints[str(new_blueprint.id)] = new_blueprint
        return new_blueprint

    # currently validation is split to 2 phases: the first
    # part is during submission (dsl parsing)
    # second part is during call to validate which simply delegates
    # the plan to the workflow service
    # so we can parse all the workflows and see things are ok
    def validate_blueprint(self, blueprint_id):
        blueprint = self.get_blueprint(blueprint_id)
        plan = blueprint.typed_plan
        response = workflow_client().validate_workflows(plan)
        # TODO raise error if error
        return BlueprintValidationStatus(blueprint_id=blueprint_id,
                                         status=response['status'])

    def execute_workflow(self, deployment_id, workflow_id):
        #TODO: in the future, take the workflow from the
        # deployment rather than from the blueprint
        deployment = self.get_deployment(deployment_id)
        blueprint = self.get_blueprint(deployment.blueprint_id)
        workflow = blueprint.typed_plan['workflows'][workflow_id]
        plan = blueprint.typed_plan

        response = workflow_client().execute_workflow(
            workflow, plan, deployment_id=deployment_id)
        # TODO raise error if there is error in response
        new_execution = Execution(state=response['state'],
                                  internal_workflow_id=response['id'],
                                  created_at=response['created'],
                                  blueprint_id=blueprint.id,
                                  workflow_id=workflow_id,
                                  deployment_id=deployment_id)

        deployment.add_execution(new_execution)
        self.executions[str(new_execution.id)] = new_execution

        return new_execution

    def get_workflow_state(self, execution_id):
        execution = self.get_execution(execution_id)
        response = workflow_client().get_workflow_status(
            execution.internal_workflow_id)
        execution.status = response['state']
        if execution.status == 'failed':
            execution.error = response['error']
        return execution

    def create_deployment(self, blueprint_id):
        blueprint = self.get_blueprint(blueprint_id)
        plan = blueprint.typed_plan
        deployment_json_plan = tasks.prepare_deployment_plan(plan)
        deployment_id = uuid.uuid4()

        new_deployment = Deployment(deployment_id=deployment_id,
                                    plan=deployment_json_plan,
                                    typed_plan=blueprint.typed_plan,
                                    blueprint_id=blueprint_id)

        self.deployments[str(deployment_id)] = new_deployment

        return new_deployment


_instance = BlueprintsManager()


def reset():
    global _instance
    _instance = BlueprintsManager()


def instance():
    return _instance
