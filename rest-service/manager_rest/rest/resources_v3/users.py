#########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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

from manager_rest.storage import models
from manager_rest.security import MissingPremiumFeatureResource
from manager_rest.manager_exceptions import BadParametersError

from ..responses_v3 import BaseResponse
from .. import rest_decorators, rest_utils

try:
    from cloudify_premium import (UserResponse,
                                  SecuredMultiTenancyResource)
except ImportError:
    UserResponse = BaseResponse
    SecuredMultiTenancyResource = MissingPremiumFeatureResource


class Users(SecuredMultiTenancyResource):
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(UserResponse)
    @rest_decorators.create_filters(models.User)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.User)
    def get(self, multi_tenancy, _include=None, filters=None, pagination=None,
            sort=None, **kwargs):
        """
        List users
        """
        return multi_tenancy.list_users(
            _include,
            filters,
            pagination,
            sort
        )

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(UserResponse)
    @rest_decorators.no_ldap('create user')
    def put(self, multi_tenancy):
        """
        Create a user
        """
        request_dict = rest_utils.get_json_and_verify_params(
            {'username', 'password', 'role'}
        )
        # The password shouldn't be validated here
        password = request_dict.pop('password')
        password = rest_utils.validate_and_decode_password(password)
        rest_utils.validate_inputs(request_dict)
        return multi_tenancy.create_user(
            request_dict['username'],
            password,
            request_dict['role']
        )


class UsersId(SecuredMultiTenancyResource):
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(UserResponse)
    def post(self, username, multi_tenancy):
        """
        Set password/role for a certain user
        """
        request_dict = rest_utils.get_json_and_verify_params()
        password = request_dict.get('password')
        role_name = request_dict.get('role')
        if password:
            if role_name:
                raise BadParametersError('Both `password` and `role` provided')
            password = rest_utils.validate_and_decode_password(password)
            return multi_tenancy.set_user_password(username, password)
        elif role_name:
            return multi_tenancy.set_user_role(username, role_name)
        else:
            raise BadParametersError('Neither `password` nor `role` provided')

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(UserResponse)
    def get(self, username, multi_tenancy):
        """
        Get details for a single user
        """
        rest_utils.validate_inputs({'username': username})
        return multi_tenancy.get_user(username)

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(UserResponse)
    @rest_decorators.no_ldap('delete user')
    def delete(self, username, multi_tenancy):
        """
        Delete a user
        """
        rest_utils.validate_inputs({'username': username})
        return multi_tenancy.delete_user(username)


class UsersActive(SecuredMultiTenancyResource):
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(UserResponse)
    def post(self, username, multi_tenancy):
        """
        Activate a user
        """
        request_dict = rest_utils.get_json_and_verify_params({'action'})
        if request_dict['action'] == 'activate':
            return multi_tenancy.activate_user(username)
        else:
            return multi_tenancy.deactivate_user(username)
