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
class ExecutionRequest(object):

    resource_fields = {
        'workflow_id': fields.String,
        'parameters': fields.Raw,
        'allow_custom_parameters': fields.Boolean,
        'force': fields.Boolean
    }


@swagger.model
class DeploymentRequest(object):

    resource_fields = {
        'blueprint_id': fields.String,
    }


@swagger.model
class DeploymentModificationRequest(object):

    resource_fields = {
        'stage': fields.String,
        'nodes': fields.Raw,
    }


@swagger.model
class ModifyExecutionRequest(object):

    resource_fields = {
        'action': fields.String
    }


@swagger.model
class PostProviderContextRequest(object):

    resource_fields = {
        'name': fields.String,
        'context': fields.Raw
    }


@swagger.model
class AttributesRequest(object):

    resource_fields = {
        'deployment_id': fields.String,
        'context': fields.Raw,
        'payload': fields.Raw
    }
