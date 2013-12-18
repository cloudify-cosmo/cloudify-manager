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
        self.yml = None #TODO kwargs['yml']
        self.topology = None #TODO kwargs['topology']
        self.deployments = None #TODO kwargs['deployments']
        self.executions = {}

    def add_execution(self, execution):
        self.executions[str(execution.id)] = execution

    def executions_list(self):
        return self.executions.values()


class BlueprintValidationStatus(object):

    resource_fields = {
        'blueprintId': fields.String(attribute='blueprint_id'),
        'status': fields.String
    }

    def __init__(self, *args, **kwargs):
        self.blueprint_id = kwargs['blueprint_id']
        self.status = kwargs['status']


class Topology(object):

    def __init__(self, *args, **kwargs):
        self.id = None #TODO generate
        self.permalink = None #TODO implement
        self.nodes = kwargs['nodes']


class Node(object):

    def __init__(self, *args, **kwargs):
        self.id = None #TODO generate
        self.permalink = None #TODO implement
        self.name = kwargs['name']
        self.type = kwargs['type']
        self.base_type = kwargs['base_type']
        self.required_instances = kwargs['required_instances']
        self.relationships = kwargs['relationships']
        self.properties = kwargs['properties']
        self.deployment_ids = kwargs['deployment_ids']


class Deployment(object):

    resource_fields = {
        'id': fields.String,
        # 'permalink': fields.Url('blueprint_ep')
        'createdAt': fields.String(attribute='created_at'),# TODO should be DateTime?
        'updatedAt': fields.String(attribute='updated_at'),# TODO should be DateTime?
        'executionId': fields.String(attribute='execution_id'),
        'workflowId': fields.String(attribute='workflow_id'),
        'blueprintId': fields.String(attribute='blueprint_id'),
        'plan': fields.String,
    }

    def __init__(self, *args, **kwargs):
        self.id = kwargs['deployment_id']
        self.permalink = None #TODO implement
        self.created_at = kwargs['created_at']
        self.updated_at = kwargs['updated_at']
        self.execution_id = kwargs['execution_id']
        self.workflow_id = kwargs['workflow_id']
        self.blueprint_id = kwargs['blueprint_id']
        self.plan = kwargs['plan']


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
        self.id = uuid.uuid4()
        self.status = kwargs['state']
        self.deployment_id = kwargs['deployment_id']
        self.internal_workflow_id = kwargs['internal_workflow_id']
        self.workflow_id = kwargs['workflow_id']
        self.blueprint_id = kwargs['blueprint_id']
        self.created_at = kwargs['created_at']
        self.error = 'None'


class DeploymentEvents(object):

    resource_fields = {
        'id': fields.String,
        'firstEvent': fields.Integer(attribute='first_event'),
        'lastEvent': fields.Integer(attribute='last_event'),
        'events': fields.List(fields.Raw),
        'deploymentTotalEvents': fields.Integer(attribute='deployment_total_events')
    }

    def __init__(self, *args, **kwargs):
        self.id = kwargs['id']
        self.first_event = kwargs['first_event']
        self.last_event = kwargs['last_event']
        self.events = kwargs['events']
        self.deployment_total_events = kwargs['deployment_total_events']
        self.deployment_events_bytes = kwargs['deployment_events_bytes']


class Nodes(object):

    resource_fields = {
        'nodes': fields.List(fields.Raw)
    }

    def __init__(self, *args, **kwargs):
        self.nodes = kwargs['nodes']


class Node(object):

    resource_fields = {
        'id': fields.String,
        'runtimeInfo': fields.Raw(attribute='runtime_info')
    }

    def __init__(self, *args, **kwargs):
        self.id = kwargs['id']
        self.runtime_info = kwargs['runtime_info']
