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

from flask import current_app

from manager_rest import constants
from manager_rest.storage import models
from manager_rest.security.authorization import authorize
from manager_rest.security import MissingPremiumFeatureResource
from manager_rest.manager_exceptions import (
    BadParametersError,
    MethodNotAllowedError,
)

from .. import rest_decorators, rest_utils
from ..responses_v3 import BaseResponse

try:
    from cloudify_premium.multi_tenancy.responses import GroupResponse
    from cloudify_premium.multi_tenancy.secured_tenant_resource \
        import SecuredMultiTenancyResource
except ImportError:
    GroupResponse = BaseResponse
    SecuredMultiTenancyResource = MissingPremiumFeatureResource


class UserGroups(SecuredMultiTenancyResource):
    @authorize('user_group_list')
    @rest_decorators.marshal_with(GroupResponse)
    @rest_decorators.create_filters(models.Group)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.Group)
    @rest_decorators.search('name')
    def get(self, multi_tenancy, _include=None, filters=None, pagination=None,
            sort=None, search=None, **kwargs):
        """
        List groups
        """
        return multi_tenancy.list_groups(
            _include,
            filters,
            pagination,
            sort,
            search
        )

    @authorize('user_group_create')
    @rest_decorators.marshal_with(GroupResponse)
    def post(self, multi_tenancy):
        """
        Create a group
        """
        request_dict = rest_utils.get_json_and_verify_params()
        group_name = request_dict['group_name']
        ldap_group_dn = request_dict.get('ldap_group_dn')
        role = request_dict.get('role', constants.DEFAULT_SYSTEM_ROLE)
        rest_utils.verify_role(role, is_system_role=True)
        rest_utils.validate_inputs({'group_name': group_name})
        if group_name == 'users':
            raise BadParametersError(
                '{0!r} is not allowed as a user group name '
                "because it wouldn't be possible to remove it later due to "
                'a conflict with the remove {0} from user group endpoint'
                .format(str(group_name))
            )
        return multi_tenancy.create_group(group_name, ldap_group_dn, role)


class UserGroupsId(SecuredMultiTenancyResource):

    @authorize('user_group_update')
    @rest_decorators.marshal_with(GroupResponse)
    def post(self, group_name, multi_tenancy):
        """
        Set role for a certain group
        """
        request_dict = rest_utils.get_json_and_verify_params()
        role_name = request_dict.get('role')
        if not role_name:
            raise BadParametersError('`role` not provided')
        rest_utils.verify_role(role_name, is_system_role=True)
        return multi_tenancy.set_group_role(group_name, role_name)

    @authorize('user_group_get')
    @rest_decorators.marshal_with(GroupResponse)
    def get(self, group_name, multi_tenancy):
        """
        Get info for a single group
        """
        rest_utils.validate_inputs({'group_name': group_name})
        return multi_tenancy.get_group(group_name)

    @authorize('user_group_delete')
    def delete(self, group_name, multi_tenancy):
        """
        Delete a user group
        """
        rest_utils.validate_inputs({'group_name': group_name})
        multi_tenancy.delete_group(group_name)
        return None, 204


class UserGroupsUsers(SecuredMultiTenancyResource):
    @authorize('user_group_add_user')
    @rest_decorators.marshal_with(GroupResponse)
    @rest_decorators.no_external_authenticator('add user to group')
    def put(self, multi_tenancy):
        """
        Add a user to a group
        """
        if current_app.external_auth \
                and current_app.external_auth.configured():
            raise MethodNotAllowedError(
                'Explicit group to user association is not permitted when '
                'using LDAP. Group association to users is done automatically'
                ' according to the groups associated with the user in LDAP.')
        request_dict = rest_utils.get_json_and_verify_params({'username',
                                                              'group_name'})
        rest_utils.validate_inputs(request_dict)
        return multi_tenancy.add_user_to_group(
            request_dict['username'],
            request_dict['group_name']
        )

    @authorize('user_group_remove_user')
    @rest_decorators.no_external_authenticator('remove user from group')
    def delete(self, multi_tenancy):
        """
        Remove a user from a group
        """
        request_dict = rest_utils.get_json_and_verify_params({'username',
                                                              'group_name'})
        multi_tenancy.remove_user_from_group(
            request_dict['username'],
            request_dict['group_name']
        )
        return None, 204
