#########
# Copyright (c) 2017-2019 Cloudify Platform Ltd. All rights reserved
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

import pydantic
from flask import request
from typing import Any, Dict, Optional

from manager_rest.rest import requests_schema, responses, swagger
from manager_rest.rest.rest_decorators import marshal_with
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.dsl_functions import evaluate_intrinsic_functions


class _EvaluateFunctionsArgs(pydantic.BaseModel):
    deployment_id: str
    context: Optional[Dict[str, Any]] = {}
    payload: Dict[str, Any]


class EvaluateFunctions(SecuredResource):
    @swagger.operation(
        responseClass=responses.EvaluatedFunctions,
        nickname='evaluateFunctions',
        notes="Evaluate provided payload for intrinsic functions",
        parameters=[
            {'name': 'body',
             'description': '',
             'required': True,
             'allowMultiple': False,
             'dataType': requests_schema.EvaluateFunctionsRequest.__name__,
             'paramType': 'body'}],
        consumes=[
            "application/json"
        ]
    )
    @authorize('functions_evaluate')
    @marshal_with(responses.EvaluatedFunctions)
    def post(self, **kwargs):
        """Evaluate intrinsic in payload"""
        args = _EvaluateFunctionsArgs.parse_obj(request.json)
        processed_payload = evaluate_intrinsic_functions(
            deployment_id=args.deployment_id,
            context=args.context,
            payload=args.payload,
        )
        return dict(
            deployment_id=args.deployment_id,
            payload=processed_payload,
        )
