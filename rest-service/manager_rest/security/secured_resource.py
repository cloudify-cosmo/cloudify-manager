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

from functools import wraps, partial

from flask_restful import Resource
from flask import request, current_app

from manager_rest.utils import abort_error
from manager_rest.manager_exceptions import MissingPremiumPackage

from .authentication import authenticator
from .role_authorization import role_authorizer
from .tenant_authorization import tenant_authorizer


def authenticate_and_authorize(func, skip_tenant_auth=False):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = authenticator.authenticate(request)
        role_authorizer.authorize(user, request)
        if not skip_tenant_auth:
            tenant_authorizer.authorize(user, request)

        # Passed authentication and authorization
        return func(*args, **kwargs)
    return wrapper


def missing_premium_feature_abort(func):
    @wraps(func)
    def abort():
        abort_error(
            error=MissingPremiumPackage(
                'This feature exists only in the premium edition of Cloudify.'
                '\nPlease contact sales for additional info.'
            ),
            logger=current_app.logger,
            hide_server_message=True
        )
    return abort


# A decorator that is identical to authenticate_and_authorize,
# except that no tenant authorization is performed
authenticate_and_authorize_skip_tenant = partial(
    authenticate_and_authorize,
    skip_tenant_auth=True
)


class SecuredResource(Resource):
    method_decorators = [authenticate_and_authorize]


class SecuredResourceSkipTenantAuth(Resource):
    method_decorators = [authenticate_and_authorize_skip_tenant]


class MissingPremiumFeatureResource(Resource):
    method_decorators = [missing_premium_feature_abort]
