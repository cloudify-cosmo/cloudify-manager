#########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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

from flask_restful import types
from flask_restful.reqparse import Argument

from manager_rest.storage import models
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.rest import rest_decorators, resources_v1
from manager_rest.resource_manager import get_resource_manager
from manager_rest.maintenance import is_bypass_maintenance_mode
from manager_rest.rest.rest_utils import (get_args_and_verify_arguments,
                                          get_json_and_verify_params)


class DeploymentsId(resources_v1.DeploymentsId):

    def create_request_schema(self):
        request_schema = super(DeploymentsId, self).create_request_schema()
        request_schema['skip_plugins_validation'] = {
            'optional': True, 'type': bool}
        return request_schema

    def get_skip_plugin_validation_flag(self, request_dict):
        return request_dict.get('skip_plugins_validation', False)

    @rest_decorators.exceptions_handled
    @authorize('deployment_create')
    @rest_decorators.verify_params({'availability': ['private', 'tenant']})
    @rest_decorators.marshal_with(models.Deployment)
    def put(self, deployment_id, **kwargs):
        """
        Create a deployment
        """
        request_schema = self.create_request_schema()
        request_dict = get_json_and_verify_params(request_schema)
        blueprint_id = request_dict['blueprint_id']
        bypass_maintenance = is_bypass_maintenance_mode()
        args = get_args_and_verify_arguments(
            [Argument('private_resource', type=types.boolean)]
        )
        deployment = get_resource_manager().create_deployment(
            blueprint_id,
            deployment_id,
            inputs=request_dict.get('inputs', {}),
            bypass_maintenance=bypass_maintenance,
            private_resource=args.private_resource,
            availability=request_dict.get('availability', None),
            skip_plugins_validation=self.get_skip_plugin_validation_flag(
                request_dict)
        )
        return deployment, 201


class DeploymentsSetAvailability(SecuredResource):

    @rest_decorators.exceptions_handled
    @authorize('deployment_set_availability')
    @rest_decorators.verify_params({'availability': ['tenant']})
    @rest_decorators.marshal_with(models.Deployment)
    def patch(self, deployment_id, availability):
        """
        Set the deployment's availability
        """
        return get_resource_manager().set_availability(models.Deployment,
                                                       deployment_id,
                                                       availability)
