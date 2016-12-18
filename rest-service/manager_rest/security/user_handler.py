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

from flask import current_app
from flask_security.utils import md5

from manager_rest.storage import user_datastore


def user_loader(request):
    """Attempt to retrieve the current user from the request
    Either from request's Authorization attribute, or from the token header

    Having this function makes sure that this will work:
    > from flask_security import current_user
    > current_user
    <manager_rest.storage.resource_models.py.User object at 0x50d9d10>

    :param request: flask's request
    :return: A user object, or None if not found
    """
    user, _ = get_user_and_hashed_pass(request)
    return user


def _get_user_from_token(token):
    """Return a tuple with a user object (or None) and its hashed pass
    using an authentication token

    :param token: A token generated from a user object
    """
    # Retrieve the default serializer used by flask_security
    serializer = current_app.extensions['security'].remember_token_serializer
    try:
        # The serializer can through exceptions if the token is incorrect,
        # and we want to handle it gracefully
        result = serializer.loads(token)
    except Exception:
        result = None

    # The result should be a list with two elements - the ID of the user and...
    if not result or not isinstance(result, list) or len(result) != 2:
        return None, None
    return user_datastore.get_user(int(result[0])), result[1]


def get_user_and_hashed_pass(request):
    """Similar to the `user_loader`, except it also return the hashed_pass

    :param request: flask's request
    :return: Return a tuple with a user object (or None) and its hashed pass
    """
    auth = request.authorization
    if auth:
        user = user_datastore.get_user(auth.username)
        hashed_pass = md5(auth.password)
    else:
        token_auth_header = current_app.config[
            'SECURITY_TOKEN_AUTHENTICATION_HEADER']
        token = request.headers.get(token_auth_header)
        if not token:
            return None, None
        user, hashed_pass = _get_user_from_token(token)

    return user, hashed_pass
