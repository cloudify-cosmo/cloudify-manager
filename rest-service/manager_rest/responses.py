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
        'created_at': fields.String,
        'updated_at': fields.String
    }

    def __init__(self, **kwargs):
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

    def __init__(self, **kwargs):
        self.blueprint_id = kwargs['blueprint_id']
        self.status = kwargs['status']


@swagger.model
class Workflow(object):

    resource_fields = {
        'name': fields.String,
        'created_at': fields.String,
        'parameters': fields.Raw
    }

    def __init__(self, **kwargs):
        self.name = kwargs['name']
        self.created_at = kwargs['created_at']
        self.parameters = kwargs['parameters']


@swagger.model
@swagger.nested(workflows=Workflow.__name__)
class Deployment(object):

    resource_fields = {
        'id': fields.String,
        'created_at': fields.String,
        'updated_at': fields.String,
        'blueprint_id': fields.String,
        'workflows': fields.List(fields.Nested(Workflow.resource_fields)),
        'inputs': fields.Raw,
        'policy_types': fields.Raw,
        'policy_triggers': fields.Raw,
        'groups': fields.Raw
    }

    def __init__(self, **kwargs):
        self.id = kwargs['id']
        self.permalink = kwargs['permalink']
        self.created_at = kwargs['created_at']
        self.updated_at = kwargs['updated_at']
        self.blueprint_id = kwargs['blueprint_id']
        self.workflows = kwargs['workflows']
        self.inputs = kwargs['inputs']
        self.policy_types = kwargs['policy_types']
        self.policy_triggers = kwargs['policy_triggers']
        self.groups = kwargs['groups']


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
        'parameters': fields.Raw
    }

    def __init__(self, **kwargs):
        self.id = kwargs['id']
        self.status = kwargs['status']
        self.deployment_id = kwargs['deployment_id']
        self.workflow_id = kwargs['workflow_id']
        self.blueprint_id = kwargs['blueprint_id']
        self.created_at = kwargs['created_at']
        self.error = kwargs['error']
        self.parameters = kwargs['parameters']


@swagger.model
class Node(object):

    resource_fields = {
        'id': fields.String,
        'deployment_id': fields.String,
        'blueprint_id': fields.String,
        'type': fields.String,
        'type_hierarchy': fields.Raw,
        'number_of_instances': fields.String,
        'host_id': fields.String,
        'properties': fields.Raw,
        'operations': fields.Raw,
        'plugins': fields.Raw,
        'plugins_to_install': fields.Raw,
        'relationships': fields.Raw
    }

    def __init__(self, **kwargs):
        self.id = kwargs['id']
        self.deployment_id = kwargs['deployment_id']
        self.blueprint_id = kwargs['blueprint_id']
        self.type = kwargs['type']
        self.type_hierarchy = kwargs['type_hierarchy']
        self.number_of_instances = kwargs['number_of_instances']
        self.host_id = kwargs['host_id']
        self.properties = kwargs['properties']
        self.operations = kwargs['operations']
        self.plugins = kwargs['plugins']
        self.plugins_to_install = kwargs['plugins_to_install']
        self.relationships = kwargs['relationships']


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
        self.id = kwargs['id']
        self.deployment_id = kwargs['deployment_id']
        self.runtime_properties = kwargs['runtime_properties']
        self.version = kwargs['version']
        self.state = kwargs['state']
        self.node_id = kwargs['node_id']
        self.relationships = kwargs['relationships']
        self.host_id = kwargs['host_id']


@swagger.model
class Status(object):

    resource_fields = {
        'status': fields.String,
        'services': fields.Raw
    }

    def __init__(self, **kwargs):
        self.status = kwargs['status']
        self.services = kwargs['services']


@swagger.model
class ProviderContextPostStatus(object):

    resource_fields = {
        'status': fields.String
    }

    def __init__(self, **kwargs):
        self.status = kwargs['status']


@swagger.model
class ProviderContext(object):

    resource_fields = {
        'name': fields.String,
        'context': fields.Raw
    }

    def __init__(self, **kwargs):
        self.context = kwargs['context']
        self.name = kwargs['name']


@swagger.model
class Version(object):

    resource_fields = {
        'version': fields.String,
        'build': fields.String,
        'date': fields.String,
        'commit': fields.String,
    }

    def __init__(self, **kwargs):
        self.version = kwargs['version']
        self.build = kwargs['build']
        self.date = kwargs['date']
        self.commit = kwargs['commit']
