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

from flask_restful.inputs import boolean
from flask_restful.reqparse import Argument
from flask_restful_swagger import swagger

from cloudify.models_states import VisibilityState

from manager_rest.storage import models
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.resource_manager import get_resource_manager
from manager_rest.upload_manager import UploadedBlueprintsManager
from manager_rest.rest import (rest_utils,
                               resources_v2,
                               rest_decorators)
from manager_rest.rest.rest_utils import get_args_and_verify_arguments


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
        return UploadedBlueprintsManager().\
            receive_uploaded_data(data_id=blueprint_id,
                                  visibility=visibility)

    @swagger.operation(
        responseClass=models.Blueprint,
        nickname="deleteById",
        notes="deletes a blueprint by its id."
    )
    @authorize('blueprint_delete')
    @rest_decorators.marshal_with(models.Blueprint)
    def delete(self, blueprint_id, **kwargs):
        """
        Delete blueprint by id
        """
        query_args = get_args_and_verify_arguments(
            [Argument('force', type=boolean, default=False)])
        blueprint = get_resource_manager().delete_blueprint(
            blueprint_id,
            force=query_args.force)
        return blueprint, 200
