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
        'parameters': fields.Raw
    }

    def __init__(self, **kwargs):
        self.name = kwargs.get('name')
        self.created_at = kwargs.get('created_at')
        self.parameters = kwargs.get('parameters')


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
    }

    def __init__(self, **kwargs):
        self.edition = kwargs.get('edition')
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
        'value': fields.String,
        'role': fields.String
    }

    def __init__(self, **kwargs):
        self.value = kwargs.get('value')
        self.role = kwargs.get('role')
