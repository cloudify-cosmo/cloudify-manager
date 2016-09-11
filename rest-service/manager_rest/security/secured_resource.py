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

from functools import wraps

from flask_restful import Resource
from flask import request

from .authentication import authenticator
from .role_authorization import role_authorizer
from .user_handler import get_user_and_hashed_pass
from .tenant_authorization import tenant_authorizer


def authenticate_and_authorize(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        auth = request.authorization
        user, hashed_pass = get_user_and_hashed_pass(request)
        user = authenticator.authenticate(user, hashed_pass, auth)
        role_authorizer.authorize(user, request)
        tenant_authorizer.authorize(user, request)

        # Passed authentication and authorization
        return func(*args, **kwargs)
    return wrapper


class SecuredResource(Resource):
    method_decorators = [authenticate_and_authorize]
