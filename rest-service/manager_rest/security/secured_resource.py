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
from flask import request, current_app, Response, jsonify

from manager_rest.utils import abort_error, with_tracing
from manager_rest.manager_exceptions import MissingPremiumPackage

from .authentication import authenticator


def authenticate(func):
    @wraps(func)
    @with_tracing('authenticate')
    def wrapper(*args, **kwargs):
        auth_response = authenticator.authenticate(request)
        if isinstance(auth_response, Response):
            return auth_response
        response = func(*args, **kwargs)
        if hasattr(auth_response, 'response_headers'):
            # to set additional headers
            response = jsonify(response)
            for header, value in auth_response.response_headers.iteritems():
                response.headers[header] = value
        return response
    return wrapper


def missing_premium_feature_abort(func):
    @wraps(func)
    def abort(*args, **kwargs):
        abort_error(
            error=MissingPremiumPackage(
                'This feature exists only in the premium edition of Cloudify.'
                '\nPlease contact sales for additional info.'
            ),
            logger=current_app.logger,
            hide_server_message=True
        )
    return abort


class SecuredResource(Resource):
    method_decorators = [authenticate]


class MissingPremiumFeatureResource(Resource):
    method_decorators = [missing_premium_feature_abort]
