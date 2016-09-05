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

from manager_rest.responses import (Node as NodeV1,
                                    NodeInstance as NodeInstanceV1,
                                    Deployment as DeploymentV1)
from manager_rest.responses_v2 import Plugin  # noqa


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
        self.status = kwargs.get('status')
        self.activated_at = kwargs.get('activated_at')
        self.activation_requested_at = kwargs.get('activation_requested_at')
        self.remaining_executions = kwargs.get('remaining_executions')
        self.requested_by = kwargs.get('requested_by')


@swagger.model
class DeploymentUpdateStep(object):
    resource_fields = {
        'id': fields.String,
        'action': fields.String,
        'entity_type': fields.String,
        'entity_id': fields.String
    }

    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.action = kwargs.get('action')
        self.entity_type = kwargs.get('entity_type')
        self.entity_id = kwargs.get('entity_id')


@swagger.model
class DeploymentUpdate(object):
    resource_fields = {
        'id': fields.String,
        'deployment_id': fields.String,
        'state': fields.String,
        'steps': fields.Raw,
        'execution_id': fields.String,
        'created_at': fields.String
    }

    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.deployment_id = kwargs.get('deployment_id')
        self.steps = kwargs.get('steps')
        self.state = kwargs.get('state')
        self.execution_id = kwargs.get('execution_id')
        self.created_at = kwargs.get('created_at')


class Deployment(DeploymentV1):

    resource_fields = dict(DeploymentV1.resource_fields.items() + {
        'scaling_groups': fields.Raw,
    }.items())

    def __init__(self, **kwargs):
        super(Deployment, self).__init__(**kwargs)
        self.scaling_groups = kwargs.get('scaling_groups')


@swagger.model
class Node(NodeV1):

    resource_fields = dict(NodeV1.resource_fields.items() + {
        'min_number_of_instances': fields.String,
        'max_number_of_instances': fields.String,
    }.items())

    def __init__(self, **kwargs):
        super(Node, self).__init__(**kwargs)
        self.min_number_of_instances = kwargs.get('min_number_of_instances')
        self.max_number_of_instances = kwargs.get('max_number_of_instances')


@swagger.model
class NodeInstance(NodeInstanceV1):

    resource_fields = dict(NodeInstanceV1.resource_fields.items() + {
        'scaling_groups': fields.Raw
    }.items())

    def __init__(self, **kwargs):
        super(NodeInstance, self).__init__(**kwargs)
        self.scaling_groups = kwargs.get('scaling_groups')
