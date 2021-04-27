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

from flask_restful import fields
from flask_restful_swagger import swagger


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
        'plugin': fields.String,
        'operation': fields.String,
        'parameters': fields.Raw
    }

    def __init__(self, **kwargs):
        self.name = kwargs.get('name')
        self.created_at = kwargs.get('created_at')
        self.parameters = kwargs.get('parameters')
        self.plugin = kwargs.get('plugin')
        self.operation = kwargs.get('operation')

    def as_dict(self):
        return {
            'name': self.name,
            'created_at': self.created_at,
            'parameters': self.parameters,
            'plugin': self.plugin,
            'operation': self.operation,
        }

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        # could also consider params but currently it just merges by name
        return self.name == other.name


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
class Version(object):

    resource_fields = {
        'edition': fields.String,
        'version': fields.String,
        'build': fields.String,
        'date': fields.String,
        'commit': fields.String,
        'distribution': fields.String,
        'distro_release': fields.String,
    }

    def __init__(self, **kwargs):
        self.edition = kwargs.get('edition')
        self.version = kwargs.get('version')
        self.build = kwargs.get('build')
        self.date = kwargs.get('date')
        self.commit = kwargs.get('commit')
        self.distribution = kwargs.get('distribution')
        self.distro_release = kwargs.get('distro_release')


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
        'username': fields.String,
        'value': fields.String,
        'role': fields.String
    }

    def __init__(self, **kwargs):
        self.username = kwargs.get('username')
        self.value = kwargs.get('value')
        self.role = kwargs.get('role')


@swagger.model
class Label(object):

    resource_fields = {
        'key': fields.String,
        'value': fields.String,
        'created_at': fields.String,
        'creator_id': fields.Integer
    }

    def __init__(self, **kwargs):
        self.key = kwargs.get('key')
        self.value = kwargs.get('value')
        self.created_at = kwargs.get('created_at')
        self.creator_id = kwargs.get('creator_id')
