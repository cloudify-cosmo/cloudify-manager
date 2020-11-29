#########
# Copyright (c) 2018 Cloudify Platform Ltd. All rights reserved
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

from flask import request

from flask_restful.inputs import boolean
from flask_restful.reqparse import Argument
from flask_restful_swagger import swagger

from cloudify._compat import text_type
from cloudify.models_states import VisibilityState, BlueprintUploadState

from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.resource_manager import get_resource_manager
from manager_rest.upload_manager import (UploadedBlueprintsManager,
                                         UploadedBlueprintsValidator)
from manager_rest.rest import (rest_utils,
                               resources_v2,
                               rest_decorators)
from manager_rest.utils import get_formatted_timestamp
from manager_rest.storage import models, get_storage_manager
from manager_rest.rest.rest_utils import get_args_and_verify_arguments
from manager_rest.manager_exceptions import (ConflictError,
                                             IllegalActionError,
                                             BadParametersError)


class BlueprintsSetGlobal(SecuredResource):

    @authorize('resource_set_global')
    @rest_decorators.marshal_with(models.Blueprint)
    def patch(self, blueprint_id):
        """
        Set the blueprint's visibility to global
        """
        return get_resource_manager().set_visibility(
            models.Blueprint,
            blueprint_id,
            VisibilityState.GLOBAL
        )


class BlueprintsSetVisibility(SecuredResource):

    @authorize('resource_set_visibility')
    @rest_decorators.marshal_with(models.Blueprint)
    def patch(self, blueprint_id):
        """
        Set the blueprint's visibility
        """
        visibility = rest_utils.get_visibility_parameter()
        return get_resource_manager().set_visibility(models.Blueprint,
                                                     blueprint_id,
                                                     visibility)


class BlueprintsId(resources_v2.BlueprintsId):
    @authorize('blueprint_upload')
    @rest_decorators.marshal_with(models.Blueprint)
    def put(self, blueprint_id, **kwargs):
        """
        Upload a blueprint (id specified)
        """
        rest_utils.validate_inputs({'blueprint_id': blueprint_id})
        visibility = rest_utils.get_visibility_parameter(
            optional=True,
            is_argument=True,
            valid_values=VisibilityState.STATES
        )
        # Fail fast if trying to upload a duplicate blueprint
        current_tenant = request.headers.get('tenant')
        if visibility == VisibilityState.GLOBAL:
            existing_duplicates = get_storage_manager().list(
                models.Blueprint, filters={'id': blueprint_id})
            if existing_duplicates:
                raise IllegalActionError(
                    "Can't set or create the resource `{0}`, it's visibility "
                    "can't be global because it also exists in other "
                    "tenants".format(blueprint_id))
        else:
            existing_duplicates = get_storage_manager().list(
                models.Blueprint, filters={'id': blueprint_id,
                                           'tenant_name': current_tenant})
            if existing_duplicates:
                raise ConflictError(
                    'blueprint with id={0} already exists on tenant {1} or '
                    'with global visibility'.format(blueprint_id,
                                                    current_tenant))
        return UploadedBlueprintsManager().\
            receive_uploaded_data(data_id=blueprint_id,
                                  visibility=visibility)

    @swagger.operation(
        responseClass=models.Blueprint,
        nickname="deleteById",
        notes="deletes a blueprint by its id."
    )
    @authorize('blueprint_delete')
    def delete(self, blueprint_id, **kwargs):
        """
        Delete blueprint by id
        """
        query_args = get_args_and_verify_arguments(
            [Argument('force', type=boolean, default=False)])
        get_resource_manager().delete_blueprint(
            blueprint_id,
            force=query_args.force)
        return None, 204

    @authorize('blueprint_upload')
    @rest_decorators.marshal_with(models.Blueprint)
    def patch(self, blueprint_id, **kwargs):
        """
        Update a blueprint.

        Used for updating the blueprint's state (and error) while uploading,
        and updating the blueprint's other attributes upon a successful upload.
        This method is for internal use only.
        """
        if not request.json:
            raise IllegalActionError('Update a blueprint request must include'
                                     ' at least one parameter to update')

        request_schema = {
            'plan': {'type': dict, 'optional': True},
            'description': {'type': text_type, 'optional': True},
            'main_file_name': {'type': text_type, 'optional': True},
            'visibility': {'type': text_type, 'optional': True},
            'state': {'type': text_type, 'optional': True},
            'error': {'type': text_type, 'optional': True},
        }
        request_dict = rest_utils.get_json_and_verify_params(request_schema)

        invalid_params = set(request_dict.keys()) - set(request_schema.keys())
        if invalid_params:
            raise BadParametersError(
                "Unknown parameters: {}".format(','.join(invalid_params))
            )
        sm = get_storage_manager()
        blueprint = sm.get(models.Blueprint, blueprint_id)

        # set blueprint state
        state = request_dict.get('state')
        if state:
            if state not in BlueprintUploadState.STATES:
                raise BadParametersError(
                    "Invalid state: `{0}`. Valid blueprint state values are: "
                    "{1}".format(state, BlueprintUploadState.STATES)
                )
            blueprint.state = state
            blueprint.error = request_dict.get('error')

        # set blueprint visibility
        visibility = request_dict.get('visibility')
        if visibility:
            if visibility not in VisibilityState.STATES:
                raise BadParametersError(
                    "Invalid visibility: `{0}`. Valid visibility's values "
                    "are: {1}".format(visibility, VisibilityState.STATES)
                )
            blueprint.visibility = visibility

        # set other blueprint attributes.
        if 'plan' in request_dict:
            blueprint.plan = request_dict['plan']
        if 'description' in request_dict:
            blueprint.plan = request_dict['description']
        if 'main_file_name' in request_dict:
            blueprint.main_file_name = request_dict['main_file_name']

        blueprint.updated_at = get_formatted_timestamp()
        return sm.update(blueprint)


class BlueprintsIdValidate(BlueprintsId):
    @authorize('blueprint_upload')
    def put(self, blueprint_id, **kwargs):
        """
        Validate a blueprint (id specified)
        """
        rest_utils.validate_inputs({'blueprint_id': blueprint_id})
        visibility = rest_utils.get_visibility_parameter(
            optional=True,
            is_argument=True,
            valid_values=VisibilityState.STATES
        )
        return UploadedBlueprintsValidator().\
            receive_uploaded_data(data_id=blueprint_id,
                                  visibility=visibility)
