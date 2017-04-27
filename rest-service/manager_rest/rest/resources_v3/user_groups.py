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

from flask import current_app

from manager_rest.storage import models
from manager_rest.security import MissingPremiumFeatureResource
from manager_rest.manager_exceptions import MethodNotAllowedError

from ..responses_v3 import BaseResponse
from .. import rest_decorators, rest_utils

try:
    from cloudify_premium import (GroupResponse,
                                  SecuredMultiTenancyResource)
except ImportError:
    GroupResponse = BaseResponse
    SecuredMultiTenancyResource = MissingPremiumFeatureResource


class UserGroups(SecuredMultiTenancyResource):
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(GroupResponse)
    @rest_decorators.create_filters(models.Group)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.Group)
    def get(self, multi_tenancy, _include=None, filters=None, pagination=None,
            sort=None, **kwargs):
        """
        List groups
        """
        return multi_tenancy.list_groups(
            _include,
            filters,
            pagination,
            sort)

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(GroupResponse)
    def post(self, multi_tenancy):
        """
        Create a group
        """
        request_dict = rest_utils.get_json_and_verify_params()
        group_name = request_dict['group_name']
        ldap_group_dn = request_dict.get('ldap_group_dn')
        rest_utils.validate_inputs({'group_name': group_name})
        return multi_tenancy.create_group(group_name, ldap_group_dn)


class UserGroupsId(SecuredMultiTenancyResource):

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(GroupResponse)
    def get(self, group_name, multi_tenancy):
        """
        Get info for a single group
        """
        rest_utils.validate_inputs({'group_name': group_name})
        return multi_tenancy.get_group(group_name)

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(GroupResponse)
    def delete(self, group_name, multi_tenancy):
        """
        Delete a user group
        """
        rest_utils.validate_inputs({'group_name': group_name})
        return multi_tenancy.delete_group(group_name)


class UserGroupsUsers(SecuredMultiTenancyResource):
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(GroupResponse)
    @rest_decorators.no_ldap('add user to group')
    def put(self, multi_tenancy):
        """
        Add a user to a group
        """
        if current_app.ldap:
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

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(GroupResponse)
    @rest_decorators.no_ldap('remove user from group')
    def delete(self, multi_tenancy):
        """
        Remove a user from a group
        """
        request_dict = rest_utils.get_json_and_verify_params({'username',
                                                              'group_name'})
        rest_utils.validate_inputs(request_dict)
        return multi_tenancy.remove_user_from_group(
            request_dict['username'],
            request_dict['group_name']
        )
