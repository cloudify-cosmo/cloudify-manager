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
class MaintenanceMode(object):
    resource_fields = {
        'status': fields.String,
        'activated_at': fields.String,
        'activation_requested_at': fields.String,
        'remaining_executions': fields.Raw,
        'requested_by': fields.String
    }

    def __init__(self, **kwargs):
        self.status = kwargs['status']
        self.activated_at = kwargs['activated_at']
        self.activation_requested_at = kwargs['activation_requested_at']
        self.remaining_executions = kwargs['remaining_executions']
        self.requested_by = kwargs['requested_by']


@swagger.model
class DeploymentUpdateStep(object):
    resource_fields = {
        'id': fields.String,
        'operation': fields.String,
        'entity_type': fields.String,
        'entity_id': fields.String
    }

    def __init__(self, **kwargs):
        self.id = kwargs['id']
        self.operation = kwargs['operation']
        self.entity_type = kwargs['entity_type']
        self.entity_id = kwargs['entity_id']


@swagger.model
class DeploymentUpdate(object):
    resource_fields = {
        'id': fields.String,
        'deployment_id': fields.String,
        'state': fields.String,
        'steps': fields.Raw
    }

    def __init__(self, **kwargs):
        self.id = kwargs['id']
        self.deployment_id = kwargs['deployment_id']
        self.steps = kwargs['steps']
        self.state = kwargs['state']
