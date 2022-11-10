#########
# Copyright (c) 2018-2019 Cloudify Platform Ltd. All rights reserved
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
from flask import request, Response, jsonify

from manager_rest import premium_enabled
from manager_rest.manager_exceptions import MissingPremiumPackage
from .authentication import authenticate as auth_user


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
        auth_response = auth_user(request)
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


def _abort_on_premium_missing(func):
    """Mark a method as requiring premium.

    Not for direct use, use MissingPremiumFeatureResource instead.
    """
    if getattr(func, 'allow_on_community', False):
        return func

    @wraps(func)
    def abort(*args, **kwargs):
        raise MissingPremiumPackage()
    return abort


if premium_enabled:
    def premium_only(f):
        """A noop in place of a "missing premium" error.

        If this is on a premium-enabled manager, the premium_only decorator
        will do nothing.
        """
        return f
else:
    premium_only = _abort_on_premium_missing


def allow_on_community(func):
    """Mark a method to be allowed on community.

    This is only useful in combination with MissingPremiumFeatureResource,
    where one specific method should be exempt from the premium check.
    """
    func.allow_on_community = True
    return func


class SecuredResource(Resource):
    method_decorators = [authenticate]


class MissingPremiumFeatureResource(Resource):
    method_decorators = [_abort_on_premium_missing]

    def get(self):
        pass
