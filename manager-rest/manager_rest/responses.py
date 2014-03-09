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

from flask.ext.restful import fields
from flask_restful_swagger import swagger


@swagger.model
class BlueprintState(object):

    resource_fields = {
        'id': fields.String,
        'plan': fields.Raw,
        'createdAt': fields.String(attribute='created_at'),
        'updatedAt': fields.String(attribute='updated_at'),
    }

    def __init__(self, *args, **kwargs):
        self.plan = kwargs['plan']
        self.id = kwargs['id']
        self.created_at = kwargs['created_at']
        self.updated_at = kwargs['updated_at']


@swagger.model
class BlueprintValidationStatus(object):

    resource_fields = {
        'blueprintId': fields.String(attribute='blueprint_id'),
        'status': fields.String
    }

    def __init__(self, *args, **kwargs):
        self.blueprint_id = kwargs['blueprint_id']
        self.status = kwargs['status']


@swagger.model
class Deployment(object):

    resource_fields = {
        'id': fields.String,
        # 'permalink': fields.Url('blueprint_ep')
        'createdAt': fields.String(attribute='created_at'),
        'updatedAt': fields.String(attribute='updated_at'),
        'blueprintId': fields.String(attribute='blueprint_id'),
        'plan': fields.Raw,
    }

    def __init__(self, *args, **kwargs):
        self.id = kwargs['id']
        self.permalink = kwargs['permalink']
        self.created_at = kwargs['created_at']
        self.updated_at = kwargs['updated_at']
        self.blueprint_id = kwargs['blueprint_id']
        self.plan = kwargs['plan']


@swagger.model
class Workflow(object):

    resource_fields = {
        'name': fields.String,
        'createdAt': fields.String(attribute='created_at')
    }

    def __init__(self, *args, **kwargs):
        self.name = kwargs['name']
        self.created_at = kwargs.get('created_at', None)


@swagger.model
@swagger.nested(workflows=Workflow.__name__)
class Workflows(object):

    resource_fields = {
        'workflows': fields.List(fields.Nested(Workflow.resource_fields)),
        'blueprintId': fields.String(attribute='blueprint_id'),
        'deploymentId': fields.String(attribute='deployment_id')
    }

    def __init__(self, *args, **kwargs):
        self.workflows = kwargs['workflows']
        self.blueprint_id = kwargs['blueprint_id']
        self.deployment_id = kwargs['deployment_id']


@swagger.model
class Execution(object):

    resource_fields = {
        'id': fields.String,
        'workflowId': fields.String(attribute='workflow_id'),
        'blueprintId': fields.String(attribute='blueprint_id'),
        'deploymentId': fields.String(attribute='deployment_id'),
        'status': fields.String,
        'error': fields.String,
        'createdAt': fields.String(attribute='created_at')
    }

    def __init__(self, *args, **kwargs):
        self.id = kwargs['id']
        self.status = kwargs['status']
        self.deployment_id = kwargs['deployment_id']
        self.internal_workflow_id = kwargs['internal_workflow_id']
        self.workflow_id = kwargs['workflow_id']
        self.blueprint_id = kwargs['blueprint_id']
        self.created_at = kwargs['created_at']
        self.error = kwargs['error']


@swagger.model
class DeploymentNode(object):

    resource_fields = {
        'id': fields.String,
        'runtimeInfo': fields.Raw(attribute='runtime_info'),
        'stateVersion': fields.Raw(attribute='state_version'),
        'reachable': fields.Boolean,
        'state': fields.String
    }

    def __init__(self, *args, **kwargs):
        self.id = kwargs['id']
        self.runtime_info = \
            kwargs['runtime_info'] if 'runtime_info' in kwargs else None
        self.reachable = kwargs['reachable'] if 'reachable' in kwargs else None
        self.state_version = kwargs['state_version']
        self.state = kwargs['state'] if 'state' in kwargs else None


@swagger.model
@swagger.nested(nodes=DeploymentNode.__name__)
class DeploymentNodes(object):

    resource_fields = {
        'deploymentId': fields.String(attribute='deployment_id'),
        'nodes': fields.List(
            fields.Nested(DeploymentNode.resource_fields))
    }

    def __init__(self, *args, **kwargs):
        self.deployment_id = kwargs['deployment_id']
        self.nodes = kwargs['nodes']
