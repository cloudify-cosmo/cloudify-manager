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

from flask_restful.reqparse import Argument
from flask_restful.inputs import boolean
from flask_restful_swagger import swagger

from manager_rest.storage import models
from manager_rest.security import SecuredResource

from manager_rest.security.authorization import authorize
from manager_rest.resource_manager import get_resource_manager
from manager_rest.storage.models_states import VisibilityState
from manager_rest.maintenance import is_bypass_maintenance_mode
from manager_rest.dsl_functions import evaluate_deployment_capabilities
from manager_rest.rest import (
    rest_utils,
    resources_v1,
    rest_decorators,
    responses_v3
)


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
    @rest_decorators.marshal_with(models.Deployment)
    def put(self, deployment_id, **kwargs):
        """
        Create a deployment
        """
        rest_utils.validate_inputs({'deployment_id': deployment_id})
        request_schema = self.create_request_schema()
        request_dict = rest_utils.get_json_and_verify_params(request_schema)
        blueprint_id = request_dict['blueprint_id']
        bypass_maintenance = is_bypass_maintenance_mode()
        args = rest_utils.get_args_and_verify_arguments(
            [Argument('private_resource', type=boolean)]
        )
        visibility = rest_utils.get_visibility_parameter(
            optional=True,
            valid_values=VisibilityState.STATES
        )
        deployment = get_resource_manager().create_deployment(
            blueprint_id,
            deployment_id,
            inputs=request_dict.get('inputs', {}),
            bypass_maintenance=bypass_maintenance,
            private_resource=args.private_resource,
            visibility=visibility,
            skip_plugins_validation=self.get_skip_plugin_validation_flag(
                request_dict)
        )
        return deployment, 201


class DeploymentsSetVisibility(SecuredResource):

    @rest_decorators.exceptions_handled
    @authorize('deployment_set_visibility')
    @rest_decorators.marshal_with(models.Deployment)
    def patch(self, deployment_id):
        """
        Set the deployment's visibility
        """
        visibility = rest_utils.get_visibility_parameter()
        return get_resource_manager().set_deployment_visibility(
            deployment_id,
            visibility
        )


class DeploymentsIdCapabilities(SecuredResource):

    @swagger.operation(
        responseClass=responses_v3.DeploymentCapabilities.__name__,
        nickname="get",
        notes="Gets a specific deployment's capabilities."
    )
    @rest_decorators.exceptions_handled
    @authorize('deployment_capabilities')
    @rest_decorators.marshal_with(responses_v3.DeploymentCapabilities)
    def get(self, deployment_id, **kwargs):
        """Get deployment capabilities"""
        capabilities = evaluate_deployment_capabilities(deployment_id)
        return dict(deployment_id=deployment_id, capabilities=capabilities)
