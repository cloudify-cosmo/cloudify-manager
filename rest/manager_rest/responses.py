__author__ = 'dan'

from datetime import datetime

class BlueprintState(object):

    def __init__(self, *args, **kwargs):
        self.id = None #TODO generate
        self.permalink = None #TODO implement
        self.yml = kwargs['yml']
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.topology = None #TODO kwargs['topology']
        self.deployments = None #TODO kwargs['deployments']


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
