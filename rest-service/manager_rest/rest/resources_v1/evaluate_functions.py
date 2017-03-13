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

from flask_restful_swagger import swagger

from manager_rest.rest import (
    requests_schema,
    responses,
)
from manager_rest.rest.rest_decorators import (
    exceptions_handled,
    marshal_with,
)
from manager_rest.security import SecuredResource
from manager_rest.dsl_functions import evaluate_intrinsic_functions
from manager_rest.rest.rest_utils import get_json_and_verify_params


class EvaluateFunctions(SecuredResource):

    @swagger.operation(
        responseClass=responses.EvaluatedFunctions,
        nickname='evaluateFunctions',
        notes="Evaluate provided payload for intrinsic functions",
        parameters=[{'name': 'body',
                     'description': '',
                     'required': True,
                     'allowMultiple': False,
                     'dataType': requests_schema.EvaluateFunctionsRequest.__name__,  # noqa
                     'paramType': 'body'}],
        consumes=[
            "application/json"
        ]
    )
    @exceptions_handled
    @marshal_with(responses.EvaluatedFunctions)
    def post(self, **kwargs):
        """
        Evaluate intrinsic in payload
        """
        request_dict = get_json_and_verify_params({
            'deployment_id': {},
            'context': {'optional': True, 'type': dict},
            'payload': {'type': dict}
        })

        deployment_id = request_dict['deployment_id']
        context = request_dict.get('context', {})
        payload = request_dict.get('payload')
        processed_payload = evaluate_intrinsic_functions(
            deployment_id=deployment_id,
            context=context,
            payload=payload)
        return dict(deployment_id=deployment_id, payload=processed_payload)
