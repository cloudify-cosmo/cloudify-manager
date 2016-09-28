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

from flask import request
from flask_security import current_user

from manager_rest.storage import models
from manager_rest.security import SecuredResource
from manager_rest.resources import (marshal_with,
                                    exceptions_handled)
from manager_rest.resources_v2 import (create_filters,
                                       paginate,
                                       sortable,
                                       verify_json_content_type,
                                       verify_parameter_in_request_body)
try:
    from cloudify_premium import (TenantResponse,
                                  GroupResponse,
                                  UserResponse,
                                  SecuredTenantResource)
except:
    TenantResponse, GroupResponse, UserResponse = (None, ) * 3
    SecuredTenantResource = SecuredResource


class Tenants(SecuredTenantResource):
    @exceptions_handled
    @marshal_with(TenantResponse)
    @create_filters(models.Tenant.fields)
    @paginate
    @sortable
    def get(self, _include=None, filters=None, pagination=None, sort=None,
            multi_tenancy=None, **kwargs):
        """
        List tenants
        """
        return multi_tenancy.list_tenants(current_user.id,
                                          _include,
                                          filters,
                                          pagination,
                                          sort)


class TenantsId(SecuredTenantResource):
    @exceptions_handled
    @marshal_with(TenantResponse)
    def post(self, tenant_name, multi_tenancy=None):
        """
        Create a tenant
        """
        return multi_tenancy.create_tenant(tenant_name)


class TenantUsers(SecuredTenantResource):
    @exceptions_handled
    @marshal_with(UserResponse)
    def put(self, multi_tenancy):
        """
        Add a user to a tenant
        """
        verify_json_content_type()
        request_json = request.json
        verify_parameter_in_request_body('username', request_json)
        verify_parameter_in_request_body('tenant_name', request_json)
        return multi_tenancy.add_user_to_tenant(request_json['username'],
                                                request_json['tenant_name'])

    @exceptions_handled
    @marshal_with(UserResponse)
    def delete(self, multi_tenancy):
        """
        Remove a user from a tenant
        """
        verify_json_content_type()
        request_json = request.json
        verify_parameter_in_request_body('username', request_json)
        verify_parameter_in_request_body('tenant_name', request_json)
        user_name = request_json['username']
        tenant_name = request_json['tenant_name']
        return multi_tenancy.remove_user_from_tenant(user_name,
                                                     tenant_name)


class TenantGroups(SecuredTenantResource):
    @exceptions_handled
    @marshal_with(GroupResponse)
    def put(self, multi_tenancy):
        """
        Add a group to a tenant
        """
        verify_json_content_type()
        request_json = request.json
        verify_parameter_in_request_body('group_name', request_json)
        verify_parameter_in_request_body('tenant_name', request_json)
        return multi_tenancy.add_group_to_tenant(request_json['group_name'],
                                                 request_json['tenant_name'])

    @exceptions_handled
    @marshal_with(GroupResponse)
    def delete(self, multi_tenancy):
        """
        Remove a group from a tenant
        """
        verify_json_content_type()
        request_json = request.json
        verify_parameter_in_request_body('group_name', request_json)
        verify_parameter_in_request_body('tenant_name', request_json)
        return multi_tenancy.remove_group_from_tenant(
            request_json['group_name'],
            request_json['tenant_name']
        )


class UserGroups(SecuredTenantResource):
    @exceptions_handled
    @marshal_with(GroupResponse)
    @create_filters(models.Group.fields)
    @paginate
    @sortable
    def get(self, _include=None, filters=None, pagination=None, sort=None,
            multi_tenancy=None, **kwargs):
        """
        List groups
        """
        return multi_tenancy.list_groups(
            _include,
            filters,
            pagination,
            sort)


class UserGroupsId(SecuredTenantResource):
    @exceptions_handled
    @marshal_with(GroupResponse)
    def post(self, group_name, multi_tenancy):
        """
        Create a group
        """
        return multi_tenancy.create_group(group_name)


class UserGroupsUsers(SecuredTenantResource):
    @exceptions_handled
    @marshal_with(UserResponse)
    def put(self, multi_tenancy):
        """
        Add a user to a group
        """
        verify_json_content_type()
        request_json = request.json
        verify_parameter_in_request_body('username', request_json)
        verify_parameter_in_request_body('group_name', request_json)
        return multi_tenancy.add_user_to_group(request_json['username'],
                                               request_json['group_name'])

    @exceptions_handled
    @marshal_with(UserResponse)
    def delete(self, multi_tenancy):
        """
        Remove a user from a group
        """
        verify_json_content_type()
        request_json = request.json
        verify_parameter_in_request_body('username', request_json)
        verify_parameter_in_request_body('group_name', request_json)
        return multi_tenancy.remove_user_from_group(request_json['username'],
                                                    request_json['group_name'])
