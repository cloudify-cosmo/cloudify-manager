#########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
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
#

from flask_restful import types
from flask_restful.reqparse import Argument
from flask_restful_swagger import swagger

from dsl_parser import utils as dsl_parser_utils
from manager_rest import manager_exceptions
from manager_rest.constants import PROVIDER_CONTEXT_ID
from manager_rest.resource_manager import get_resource_manager
from manager_rest.rest import (
    requests_schema,
    responses,
)
from manager_rest.rest.rest_decorators import (
    exceptions_handled,
    marshal_with,
)
from manager_rest.rest.rest_utils import (
    get_args_and_verify_arguments,
    get_json_and_verify_params,
)
from manager_rest.security import SecuredResource
from manager_rest.storage import (
    models,
    get_storage_manager,
)


class ProviderContext(SecuredResource):

    @swagger.operation(
        responseClass=models.ProviderContext,
        nickname="getContext",
        notes="Get the provider context"
    )
    @exceptions_handled
    @marshal_with(models.ProviderContext)
    def get(self, **kwargs):
        """
        Get provider context
        """
        return get_storage_manager().get(
            models.ProviderContext,
            PROVIDER_CONTEXT_ID
        )

    @swagger.operation(
        responseClass=responses.ProviderContextPostStatus,
        nickname='postContext',
        notes="Post the provider context",
        parameters=[{'name': 'body',
                     'description': 'Provider context',
                     'required': True,
                     'allowMultiple': False,
                     'dataType': requests_schema.PostProviderContextRequest.__name__,  # NOQA
                     'paramType': 'body'}],
        consumes=[
            "application/json"
        ]
    )
    @exceptions_handled
    @marshal_with(responses.ProviderContextPostStatus)
    def post(self, **kwargs):
        """
        Create provider context
        """
        request_dict = get_json_and_verify_params({'context', 'name'})
        args = get_args_and_verify_arguments(
            [Argument('update', type=types.boolean, default=False)]
        )
        update = args['update']
        context = dict(
            id=PROVIDER_CONTEXT_ID,
            name=request_dict['name'],
            context=request_dict['context']
        )

        status_code = 200 if update else 201

        try:
            get_resource_manager().update_provider_context(update, context)
            return dict(status='ok'), status_code
        except dsl_parser_utils.ResolverInstantiationError, ex:
            raise manager_exceptions.ResolverInstantiationError(str(ex))
