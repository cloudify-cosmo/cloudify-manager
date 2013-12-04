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
        self.id = uuid.uuid4()
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

    def __init__(self, *args, **kwargs):
        self.id = None #TODO generate
        self.permalink = None #TODO implement
        self.created_at = kwargs['created_at']
        self.updated_at = kwargs['updated_at']
        self.execution_id = kwargs['execution_id']
        self.workflow_id = kwargs['workflow_id']
        self.blueprint_id = kwargs['blueprint_id']
        self.nodes = kwargs['nodes']


class Execution(object):

    resource_fields = {
        'id': fields.String,
        'workflowId': fields.String(attribute='workflow_id'),
        'blueprintId': fields.String(attribute='blueprint_id'),
        'status': fields.String,
        'error': fields.String,
        'createdAt': fields.String(attribute='created_at')
    }

    def __init__(self, *args, **kwargs):
        self.id = uuid.uuid4()
        self.status = kwargs['state']
        self.deployment_id = None #TODO
        self.internal_workflow_id = kwargs['internal_workflow_id']
        self.workflow_id = kwargs['workflow_id']
        self.blueprint_id = kwargs['blueprint_id']
        self.created_at = kwargs['created_at']
        self.error = 'None'
