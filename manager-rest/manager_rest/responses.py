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
from serialization import SerializableObjectBase
from flask.ext.restful import fields

from flask_restful_swagger import swagger


@swagger.model
class BlueprintState(SerializableObjectBase):

    resource_fields = {
        'id': fields.String,
        'plan': fields.Raw,
        'createdAt': fields.String(attribute='created_at'),
        'updatedAt': fields.String(attribute='updated_at'),
        # 'permalink': fields.Url('blueprint_ep')
    }

    def __init__(self):
        self.plan = None
        self.id = None
        self.created_at = None
        self.updated_at = None
        self.yml = None
        self.topology = None
        self.deployments = None

    def init(self, *args, **kwargs):
        self.plan = kwargs['plan']
        self.id = self.plan['name']
        now = str(datetime.now())
        self.created_at = now
        self.updated_at = now
        self.yml = None  # TODO kwargs['yml']
        self.topology = None  # TODO kwargs['topology']
        self.deployments = None  # TODO kwargs['deployments']
        return self


@swagger.model
class BlueprintValidationStatus(SerializableObjectBase):

    resource_fields = {
        'blueprintId': fields.String(attribute='blueprint_id'),
        'status': fields.String
    }

    def __init__(self):
        self.blueprint_id = None
        self.status = None

    def init(self, *args, **kwargs):
        self.blueprint_id = kwargs['blueprint_id']
        self.status = kwargs['status']
        return self


@swagger.model
class Topology(SerializableObjectBase):

    def __init__(self):
        self.id = None
        self.permalink = None
        self.nodes = None

    def init(self, *args, **kwargs):
        self.id = None  # TODO generate
        self.permalink = None  # TODO implement
        self.nodes = kwargs['nodes']
        return self


@swagger.model
class Deployment(SerializableObjectBase):

    resource_fields = {
        'id': fields.String,
        # 'permalink': fields.Url('blueprint_ep')
        'createdAt': fields.String(attribute='created_at'),
        'updatedAt': fields.String(attribute='updated_at'),
        'blueprintId': fields.String(attribute='blueprint_id'),
        'plan': fields.Raw,
    }

    def __init__(self):
        self.id = None
        self.permalink = None
        self.created_at = None
        self.updated_at = None
        self.blueprint_id = None
        self.plan = None
        self.workflows = None

    def init(self, *args, **kwargs):
        self.id = kwargs['deployment_id']
        self.permalink = None  # TODO implement
        now = str(datetime.now())
        self.created_at = now
        self.updated_at = now
        self.blueprint_id = kwargs['blueprint_id']
        self.plan = kwargs['plan']
        self.workflows = {key: Workflow().init(workflow_id=key,
                                               created_at=now)
                          for key in self.plan['workflows']}
        return self

    def workflows_list(self):
        return self.workflows.values()


@swagger.model
class Workflow(SerializableObjectBase):

    resource_fields = {
        'name': fields.String,
        'createdAt': fields.String(attribute='created_at')
    }

    def __init__(self):
        self.name = None
        self.created_at = None

    def init(self, *args, **kwargs):
        self.name = kwargs['workflow_id']
        self.created_at = str(kwargs['created_at'])
        return self


@swagger.model
@swagger.nested(workflows=Workflow.__name__)
class Workflows(SerializableObjectBase):

    resource_fields = {
        'workflows': fields.List(fields.Nested(Workflow.resource_fields)),
        'blueprintId': fields.String(attribute='blueprint_id'),
        'deploymentId': fields.String(attribute='deployment_id')
    }

    def __init__(self):
        self.workflows = None
        self.blueprint_id = None
        self.deployment_id = None

    def init(self, *args, **kwargs):
        self.workflows = kwargs['workflows']
        self.blueprint_id = kwargs['blueprint_id']
        self.deployment_id = kwargs['deployment_id']
        return self


@swagger.model
class Execution(SerializableObjectBase):

    resource_fields = {
        'id': fields.String,
        'workflowId': fields.String(attribute='workflow_id'),
        'blueprintId': fields.String(attribute='blueprint_id'),
        'deploymentId': fields.String(attribute='deployment_id'),
        'status': fields.String,
        'error': fields.String,
        'createdAt': fields.String(attribute='created_at')
    }

    def __init__(self):
        self.id = None
        self.status = None
        self.deployment_id = None
        self.internal_workflow_id = None
        self.workflow_id = None
        self.blueprint_id = None
        self.created_at = None
        self.error = None

    def init(self, *args, **kwargs):
        self.id = kwargs['id']
        self.status = kwargs['state']
        self.deployment_id = kwargs['deployment_id']
        self.internal_workflow_id = kwargs['internal_workflow_id']
        self.workflow_id = kwargs['workflow_id']
        self.blueprint_id = kwargs['blueprint_id']
        self.created_at = str(kwargs['created_at'])
        self.error = 'None'
        return self


@swagger.model
class DeploymentNodesNode(SerializableObjectBase):

    resource_fields = {
        'id': fields.String,
        'reachable': fields.Boolean
    }

    def __init__(self):
        self.id = None
        self.reachable = None

    def init(self, *args, **kwargs):
        self.id = kwargs['id']
        self.reachable = kwargs['reachable'] if 'reachable' in kwargs else None
        return self


@swagger.model
@swagger.nested(nodes=DeploymentNodesNode.__name__)
class DeploymentNodes(SerializableObjectBase):

    resource_fields = {
        'deploymentId': fields.String(attribute='deployment_id'),
        'nodes': fields.List(
            fields.Nested(DeploymentNodesNode.resource_fields))
    }

    def __init__(self):
        self.deployment_id = None
        self.nodes = None

    def init(self, *args, **kwargs):
        self.deployment_id = kwargs['deployment_id']
        self.nodes = kwargs['nodes']
        return self


@swagger.model
class Nodes(SerializableObjectBase):

    resource_fields = {
        'nodes': fields.List(fields.Raw)
    }

    def __init__(self):
        self.nodes = None

    def init(self, *args, **kwargs):
        self.nodes = kwargs['nodes']
        return self


@swagger.model
class Node(SerializableObjectBase):

    resource_fields = {
        'id': fields.String,
        'runtimeInfo': fields.Raw(attribute='runtime_info'),
        'reachable': fields.Boolean
    }

    def __init__(self):
        self.id = None
        self.runtime_info = None
        self.reachable = None

    def init(self, *args, **kwargs):
        self.id = kwargs['id']
        self.runtime_info = \
            kwargs['runtime_info'] if 'runtime_info' in kwargs else None
        self.reachable = kwargs['reachable'] if 'reachable' in kwargs else None
        return self
