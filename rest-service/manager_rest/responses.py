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

from flask.ext.restful import fields
from flask_restful_swagger import swagger


@swagger.model
class BlueprintState(object):

    resource_fields = {
        'id': fields.String,
        'plan': fields.Raw,
        'created_at': fields.String,
        'updated_at': fields.String
    }

    def __init__(self, **kwargs):
        self.plan = kwargs.get('plan')
        self.id = kwargs.get('id')
        self.created_at = kwargs.get('created_at')
        self.updated_at = kwargs.get('updated_at')


@swagger.model
class BlueprintValidationStatus(object):

    resource_fields = {
        'blueprintId': fields.String(attribute='blueprint_id'),
        'status': fields.String
    }

    def __init__(self, **kwargs):
        self.blueprint_id = kwargs.get('blueprint_id')
        self.status = kwargs.get('status')


@swagger.model
class Workflow(object):

    resource_fields = {
        'name': fields.String,
        'created_at': fields.String,
        'parameters': fields.Raw
    }

    def __init__(self, **kwargs):
        self.name = kwargs.get('name')
        self.created_at = kwargs.get('created_at')
        self.parameters = kwargs.get('parameters')


class Deployment(object):

    resource_fields = {
        'id': fields.String,
        'description': fields.String,
        'created_at': fields.String,
        'updated_at': fields.String,
        'blueprint_id': fields.String,
        'workflows': fields.List(fields.Nested(Workflow.resource_fields)),
        'inputs': fields.Raw,
        'policy_types': fields.Raw,
        'policy_triggers': fields.Raw,
        'groups': fields.Raw,
        'outputs': fields.Raw
    }

    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.permalink = kwargs.get('permalink')
        self.created_at = kwargs.get('created_at')
        self.updated_at = kwargs.get('updated_at')
        self.blueprint_id = kwargs.get('blueprint_id')
        self.workflows = self._responsify_workflows_field(
            kwargs.get('workflows')
        )
        self.inputs = kwargs.get('inputs')
        self.policy_types = kwargs.get('policy_types')
        self.policy_triggers = kwargs.get('policy_triggers')
        self.groups = kwargs.get('groups')
        self.outputs = kwargs.get('outputs')
        self.description = kwargs.get('description')

    @staticmethod
    def _responsify_workflows_field(deployment_workflows):
        if deployment_workflows is None:
            return None

        return [Workflow(name=wf_name,
                         created_at=None,
                         parameters=wf.get('parameters', dict()))
                for wf_name, wf in deployment_workflows.iteritems()]


@swagger.model
class DeploymentOutputs(object):

    resource_fields = {
        'deployment_id': fields.String,
        'outputs': fields.Raw
    }

    def __init__(self, **kwargs):
        self.deployment_id = kwargs.get('deployment_id')
        self.outputs = kwargs.get('outputs')


@swagger.model
class DeploymentModification(object):

    resource_fields = {
        'id': fields.String,
        'status': fields.String,
        'deployment_id': fields.String,
        'node_instances': fields.Raw,
        'created_at': fields.String,
        'ended_at': fields.String,
        'modified_nodes': fields.Raw,
        'context': fields.Raw
    }

    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.status = kwargs.get('status')
        self.deployment_id = kwargs.get('deployment_id')
        self.node_instances = kwargs.get('node_instances')
        self.created_at = kwargs.get('created_at')
        self.ended_at = kwargs.get('ended_at')
        self.modified_nodes = kwargs.get('modified_nodes')
        self.context = kwargs.get('context')


@swagger.model
class Execution(object):

    resource_fields = {
        'id': fields.String,
        'workflow_id': fields.String,
        'blueprint_id': fields.String,
        'deployment_id': fields.String,
        'status': fields.String,
        'error': fields.String,
        'created_at': fields.String,
        'parameters': fields.Raw,
        'is_system_workflow': fields.Boolean
    }

    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.status = kwargs.get('status')
        self.deployment_id = kwargs.get('deployment_id')
        self.workflow_id = kwargs.get('workflow_id')
        self.blueprint_id = kwargs.get('blueprint_id')
        self.created_at = kwargs.get('created_at')
        self.error = kwargs.get('error')
        self.parameters = kwargs.get('parameters')
        self.is_system_workflow = kwargs.get('is_system_workflow')


@swagger.model
class Node(object):

    resource_fields = {
        'id': fields.String,
        'deployment_id': fields.String,
        'blueprint_id': fields.String,
        'type': fields.String,
        'type_hierarchy': fields.Raw,
        'number_of_instances': fields.String,
        'planned_number_of_instances': fields.String,
        'deploy_number_of_instances': fields.String,
        'host_id': fields.String,
        'properties': fields.Raw,
        'operations': fields.Raw,
        'plugins': fields.Raw,
        'plugins_to_install': fields.Raw,
        'relationships': fields.Raw
    }

    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.deployment_id = kwargs.get('deployment_id')
        self.blueprint_id = kwargs.get('blueprint_id')
        self.type = kwargs.get('type')
        self.type_hierarchy = kwargs.get('type_hierarchy')
        self.number_of_instances = kwargs.get('number_of_instances')
        self.planned_number_of_instances = kwargs.get(
            'planned_number_of_instances'
        )
        self.deploy_number_of_instances = kwargs.get(
            'deploy_number_of_instances'
        )
        self.host_id = kwargs.get('host_id')
        self.properties = kwargs.get('properties')
        self.operations = kwargs.get('operations')
        self.plugins = kwargs.get('plugins')
        self.plugins_to_install = kwargs.get('plugins_to_install')
        self.relationships = kwargs.get('relationships')


@swagger.model
class NodeInstance(object):

    resource_fields = {
        'id': fields.String,
        'node_id': fields.String,
        'host_id': fields.String,
        'relationships': fields.Raw,
        'deployment_id': fields.String,
        'runtime_properties': fields.Raw,
        'version': fields.Raw,
        'state': fields.String
    }

    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.deployment_id = kwargs.get('deployment_id')
        self.runtime_properties = kwargs.get('runtime_properties')
        self.version = kwargs.get('version')
        self.state = kwargs.get('state')
        self.node_id = kwargs.get('node_id')
        self.relationships = kwargs.get('relationships')
        self.host_id = kwargs.get('host_id')


@swagger.model
class Status(object):

    resource_fields = {
        'status': fields.String,
        'services': fields.Raw
    }

    def __init__(self, **kwargs):
        self.status = kwargs.get('status')
        self.services = kwargs.get('services')


@swagger.model
class ProviderContextPostStatus(object):

    resource_fields = {
        'status': fields.String
    }

    def __init__(self, **kwargs):
        self.status = kwargs.get('status')


@swagger.model
class ProviderContext(object):

    resource_fields = {
        'name': fields.String,
        'context': fields.Raw
    }

    def __init__(self, **kwargs):
        self.context = kwargs.get('context')
        self.name = kwargs.get('name')


@swagger.model
class Version(object):

    resource_fields = {
        'version': fields.String,
        'build': fields.String,
        'date': fields.String,
        'commit': fields.String,
    }

    def __init__(self, **kwargs):
        self.version = kwargs.get('version')
        self.build = kwargs.get('build')
        self.date = kwargs.get('date')
        self.commit = kwargs.get('commit')


@swagger.model
class EvaluatedFunctions(object):

    resource_fields = {
        'deployment_id': fields.String,
        'payload': fields.Raw
    }

    def __init__(self, **kwargs):
        self.deployment_id = kwargs.get('deployment_id')
        self.payload = kwargs.get('payload')


@swagger.model
class Tokens(object):

    resource_fields = {
        'value': fields.String
    }

    def __init__(self, **kwargs):
        self.value = kwargs.get('value')
