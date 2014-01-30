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

from datetime import datetime
import uuid
from flask.ext.restful import fields

from flask_restful_swagger import swagger


@swagger.model
class BlueprintState(object):

    resource_fields = {
        'name': fields.String,
        'id': fields.String,
        'plan': fields.String,
        'createdAt': fields.DateTime(attribute='created_at'),
        'updatedAt': fields.DateTime(attribute='updated_at'),
        # 'permalink': fields.Url('blueprint_ep')
    }

    def __init__(self, *args, **kwargs):
        self.typed_plan = kwargs['plan']
        self.plan = kwargs['json_plan']
        self.name = self.typed_plan['name']
        self.id = kwargs['id']
        now = datetime.now()
        self.created_at = now
        self.updated_at = now
        self.yml = None  # TODO kwargs['yml']
        self.topology = None  # TODO kwargs['topology']
        self.deployments = None  # TODO kwargs['deployments']


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
class Topology(object):

    def __init__(self, *args, **kwargs):
        self.id = None  # TODO generate
        self.permalink = None  # TODO implement
        self.nodes = kwargs['nodes']


@swagger.model
class Deployment(object):

    resource_fields = {
        'id': fields.String,
        # 'permalink': fields.Url('blueprint_ep')
        'createdAt': fields.DateTime(attribute='created_at'),
        'updatedAt': fields.DateTime(attribute='updated_at'),
        'blueprintId': fields.String(attribute='blueprint_id'),
        'plan': fields.String,
    }

    def __init__(self, *args, **kwargs):
        self.id = kwargs['deployment_id']
        self.permalink = None  # TODO implement
        now = datetime.now()
        self.created_at = now
        self.updated_at = now
        self.blueprint_id = kwargs['blueprint_id']
        self.plan = kwargs['plan']
        self.typed_plan = kwargs['typed_plan']
        self.workflows = {key: Workflow(workflow_id=key, created_at=now)
                          for key in self.typed_plan['workflows']}
        self.executions = {}

    def add_execution(self, execution):
        self.executions[str(execution.id)] = execution

    def executions_list(self):
        return self.executions.values()

    def workflows_list(self):
        return self.workflows.values()


@swagger.model
class Workflow(object):

    resource_fields = {
        'name': fields.String,
        'createdAt': fields.String(attribute='created_at')
    }

    def __init__(self, *args, **kwargs):
        self.name = kwargs['workflow_id']
        self.created_at = kwargs['created_at']


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
        self.status = kwargs['state']
        self.deployment_id = kwargs['deployment_id']
        self.internal_workflow_id = kwargs['internal_workflow_id']
        self.workflow_id = kwargs['workflow_id']
        self.blueprint_id = kwargs['blueprint_id']
        self.created_at = kwargs['created_at']
        self.error = 'None'


@swagger.model
class DeploymentNodesNode(object):

    resource_fields = {
        'id': fields.String,
        'reachable': fields.Boolean
    }

    def __init__(self, *args, **kwargs):
        self.id = kwargs['id']
        self.reachable = kwargs['reachable'] if 'reachable' in kwargs else None


@swagger.model
@swagger.nested(nodes=DeploymentNodesNode.__name__)
class DeploymentNodes(object):

    resource_fields = {
        'deploymentId': fields.String(attribute='deployment_id'),
        'nodes': fields.List(
            fields.Nested(DeploymentNodesNode.resource_fields))
    }

    def __init__(self, *args, **kwargs):
        self.deployment_id = kwargs['deployment_id']
        self.nodes = kwargs['nodes']


@swagger.model
class Nodes(object):

    resource_fields = {
        'nodes': fields.List(fields.Raw)
    }

    def __init__(self, *args, **kwargs):
        self.nodes = kwargs['nodes']


@swagger.model
class Node(object):

    resource_fields = {
        'id': fields.String,
        'runtimeInfo': fields.Raw(attribute='runtime_info'),
        'reachable': fields.Boolean
    }

    def __init__(self, *args, **kwargs):
        self.id = kwargs['id']
        self.runtime_info = \
            kwargs['runtime_info'] if 'runtime_info' in kwargs else None
        self.reachable = kwargs['reachable'] if 'reachable' in kwargs else None

