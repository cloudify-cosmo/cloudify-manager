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


from manager_rest.constants import VIEWER_ROLE, SUSPENDED_ROLE

from .user_handler import unauthorized_user_handler


class RoleAuthorization(object):
    def __init__(self):
        self._endpoint = None
        self._method = None
        self._role = None

    def authorize(self, user, request):
        """Assert that the user is allowed to access a certain endpoint via
         a certain method

        :param user: A valid user object
        :param request: A flask request
        """
        self._role = user.role
        self._method = request.method
        self._endpoint = request.path

        if self._role == SUSPENDED_ROLE:
            unauthorized_user_handler(
                'User `{0}` is suspended'.format(user.username)
            )

        if self._role == VIEWER_ROLE and self._method != 'GET':
            unauthorized_user_handler(
                'User `{0}` only has read-only permissions on '
                'resources'.format(user.username)
            )


role_authorizer = RoleAuthorization()
