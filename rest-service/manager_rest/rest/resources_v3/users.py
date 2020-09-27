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

from flask_security import current_user

from manager_rest import constants
from manager_rest.storage import models, user_datastore
from manager_rest.security.authorization import authorize
from manager_rest.security import (SecuredResource,
                                   MissingPremiumFeatureResource)
from manager_rest.manager_exceptions import BadParametersError

from .. import rest_decorators, rest_utils
from ..responses_v3 import UserResponse

from cloudify._compat import text_type
try:
    from cloudify_premium.multi_tenancy.secured_tenant_resource \
        import SecuredMultiTenancyResource
except ImportError:
    SecuredMultiTenancyResource = MissingPremiumFeatureResource


class User(SecuredResource):
    @authorize('user_get_self')
    @rest_decorators.marshal_with(UserResponse)
    def get(self):
        """
        Get details for the current user
        """
        return user_datastore.get_user(current_user.username)


class Users(SecuredMultiTenancyResource):
    @authorize('user_list')
    @rest_decorators.marshal_with(UserResponse)
    @rest_decorators.create_filters(models.User)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.User)
    @rest_decorators.search('username')
    def get(self, multi_tenancy, _include=None, filters=None, pagination=None,
            sort=None, search=None, **kwargs):
        """
        List users
        """
        return multi_tenancy.list_users(
            _include,
            filters,
            pagination,
            sort,
            search
        )

    @authorize('user_create')
    @rest_decorators.marshal_with(UserResponse)
    @rest_decorators.no_external_authenticator('create user')
    def put(self, multi_tenancy):
        """
        Create a user
        """
        request_dict = rest_utils.get_json_and_verify_params(
            {
                'username': {
                    'type': text_type,
                },
                'password': {
                    'type': text_type,
                },
                'role': {
                    'type': text_type,
                    'optional': True,
                },
            }
        )

        # The password shouldn't be validated here
        password = request_dict.pop('password')
        password = rest_utils.validate_and_decode_password(password)
        rest_utils.validate_inputs(request_dict)
        role = request_dict.get('role', constants.DEFAULT_SYSTEM_ROLE)
        rest_utils.verify_role(role, is_system_role=True)
        return multi_tenancy.create_user(
            request_dict['username'],
            password,
            role,
        )


class UsersId(SecuredMultiTenancyResource):
    @authorize('user_update')
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
            rest_utils.verify_role(role_name, is_system_role=True)
            return multi_tenancy.set_user_role(username, role_name)
        else:
            raise BadParametersError('Neither `password` nor `role` provided')

    @authorize('user_get')
    @rest_decorators.marshal_with(UserResponse)
    def get(self, username, multi_tenancy):
        """
        Get details for a single user
        """
        rest_utils.validate_inputs({'username': username})
        return multi_tenancy.get_user(username)

    @authorize('user_delete')
    @rest_decorators.no_external_authenticator('delete user')
    def delete(self, username, multi_tenancy):
        """
        Delete a user
        """
        rest_utils.validate_inputs({'username': username})
        multi_tenancy.delete_user(username)
        return None, 204


class UsersActive(SecuredMultiTenancyResource):
    @authorize('user_set_activated')
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


class UsersUnlock(SecuredMultiTenancyResource):
    @authorize('user_unlock')
    @rest_decorators.marshal_with(UserResponse)
    def post(self, username, multi_tenancy):
        """
        Unlock user account
        """
        rest_utils.validate_inputs({'username': username})
        return multi_tenancy.unlock_user(username)
