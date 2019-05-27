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

from functools import wraps

from flask_restful import Resource
from flask_restful.utils import unpack
from werkzeug.exceptions import HTTPException
from flask import request, current_app, Response, jsonify

from manager_rest import premium_enabled
from manager_rest.utils import abort_error
from manager_rest.manager_exceptions import MissingPremiumPackage

from .authentication import authenticator


def authenticate(func):
    def _extend_response_headers(response, extra_headers):
        response = jsonify(response)
        response.headers.extend(extra_headers)
        return response

    def _extend_tuple_response_headers(response, extra_headers):
        data, code, headers = unpack(response)
        headers.update(extra_headers)
        return data, code, headers

    def _handle_exception_response_headers(auth_headers, e):
        """
        Also in a case of failure there is a need to add auth headers to
        the response.
        """
        if auth_headers:
            response = e.get_response()
            response.headers.extend(auth_headers)
            e.response = response

    @wraps(func)
    def wrapper(*args, **kwargs):
        auth_response = authenticator.authenticate(request)
        auth_headers = getattr(auth_response, 'response_headers', {})
        if isinstance(auth_response, Response):
            return auth_response
        try:
            response = func(*args, **kwargs)
        except HTTPException as e:
            # Handling werkzeug HTTPException instead of internal one
            # for gaining access to the returned error http response.
            _handle_exception_response_headers(auth_headers, e)
            raise e
        if auth_headers:
            if isinstance(response, tuple):
                response = _extend_tuple_response_headers(
                    response=response,
                    extra_headers=auth_response.response_headers)
            else:
                response = _extend_response_headers(
                    response=response,
                    extra_headers=auth_response.response_headers)
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


if premium_enabled:
    def premium_only(f):
        """A noop in place of a "missing premium" error.

        If this is on a premium-enabled manager, the premium_only decorator
        will do nothing.
        """
        return f
else:
    premium_only = missing_premium_feature_abort


class SecuredResource(Resource):
    method_decorators = [authenticate]


class MissingPremiumFeatureResource(Resource):
    method_decorators = [missing_premium_feature_abort]
