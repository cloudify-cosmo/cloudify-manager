#########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

import re

from .user_handler import unauthorized_user_handler


ANY = '*'


class RoleAuthorization(object):
    def __init__(self):
        self._endpoint = None
        self._method = None
        self._roles = None

    def authorize(self, user, request):
        """Assert that the user is allowed to access a certain endpoint via
         a certain method

        :param user: A valid user object
        :param request: A flask request
        """
        self._roles = user.roles
        self._method = request.method
        self._endpoint = request.path

        if not self._is_allowed() or self._is_denied():
            unauthorized_user_handler(
                'Role authorization error (user: `{0}`)'.format(user.username)
            )

    def _is_allowed(self):
        """Assert that the user is allowed to access a certain endpoint via
         a certain method
        """
        return self._evaluate_permission_by_type('allowed')

    def _is_denied(self):
        """Assert that the user is *not* allowed to access a certain endpoint
        via a certain method
        """
        return self._evaluate_permission_by_type('denied')

    def _evaluate_permission_by_type(self, permission_type):
        for role in self._roles:
            configured_permissions = getattr(role, permission_type) or {}
            for endpoint, methods in configured_permissions.iteritems():
                if self._is_endpoint_matching(endpoint) and \
                        self._is_method_matching(methods):
                    return True
        return False

    def _is_endpoint_matching(self, role_endpoint):
        if role_endpoint == ANY:
            return True

        pattern = role_endpoint.replace('/', '\/').replace('*', '.*') + '$'
        if re.match(pattern, self._endpoint):
            return True
        else:
            # this is so that endpoint "v2/blueprints/*" would match
            # requests to "v2/blueprints"
            if role_endpoint.endswith('/*'):
                return self._is_endpoint_matching(role_endpoint[:-2])
            return False

    def _is_method_matching(self, role_methods):
        if role_methods == [ANY]:
            return True
        role_methods = [value.upper() for value in role_methods]
        return self._method.upper() in role_methods

role_authorizer = RoleAuthorization()
