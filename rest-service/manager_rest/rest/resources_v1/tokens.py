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
from flask_security import current_user

from manager_rest.rest import responses
from manager_rest.rest.rest_decorators import (
    exceptions_handled,
    marshal_with,
)
from manager_rest.security import SecuredResourceSkipTenantAuth


class Tokens(SecuredResourceSkipTenantAuth):

    @swagger.operation(
        responseClass=responses.Tokens,
        nickname="get auth token for the request user",
        notes="Generate authentication token for the request user",
    )
    @exceptions_handled
    @marshal_with(responses.Tokens)
    def get(self, **kwargs):
        """
        Get authentication token
        """
        token = current_user.get_auth_token()
        return dict(value=token, role=current_user.role)
