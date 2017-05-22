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

from manager_rest.storage import models
from manager_rest.security import MissingPremiumFeatureResource

from ..responses_v3 import BaseResponse
from .. import rest_decorators, rest_utils

try:
    from cloudify_premium import (TenantResponse,
                                  SecuredMultiTenancyResource,
                                  SecuredMultiTenancyResourceSkipTenantAuth)
except ImportError:
    TenantResponse = BaseResponse
    SecuredMultiTenancyResource = MissingPremiumFeatureResource
    SecuredMultiTenancyResourceSkipTenantAuth = MissingPremiumFeatureResource


class Tenants(SecuredMultiTenancyResourceSkipTenantAuth):
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(TenantResponse)
    @rest_decorators.create_filters(models.Tenant)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.Tenant)
    def get(self, multi_tenancy, _include=None, filters=None, pagination=None,
            sort=None, **kwargs):
        """
        List tenants
        """
        return multi_tenancy.list_tenants(_include, filters, pagination, sort)


class TenantsId(SecuredMultiTenancyResource):
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(TenantResponse)
    def post(self, tenant_name, multi_tenancy):
        """
        Create a tenant
        """
        rest_utils.validate_inputs({'tenant_name': tenant_name})
        return multi_tenancy.create_tenant(tenant_name)

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(TenantResponse)
    def get(self, tenant_name, multi_tenancy):
        """
        Get details for a single tenant
        """
        rest_utils.validate_inputs({'tenant_name': tenant_name})
        return multi_tenancy.get_tenant(tenant_name)

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(TenantResponse)
    def delete(self, tenant_name, multi_tenancy):
        """
        Delete a tenant
        """
        rest_utils.validate_inputs({'tenant_name': tenant_name})
        return multi_tenancy.delete_tenant(tenant_name)


class TenantUsers(SecuredMultiTenancyResource):
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(TenantResponse)
    @rest_decorators.no_ldap('add user to tenant')
    def put(self, multi_tenancy):
        """
        Add a user to a tenant
        """
        request_dict = rest_utils.get_json_and_verify_params({'tenant_name',
                                                              'username'})
        rest_utils.validate_inputs(request_dict)
        return multi_tenancy.add_user_to_tenant(
            request_dict['username'],
            request_dict['tenant_name']
        )

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(TenantResponse)
    @rest_decorators.no_ldap('remove user from tenant')
    def delete(self, multi_tenancy):
        """
        Remove a user from a tenant
        """
        request_dict = rest_utils.get_json_and_verify_params({'tenant_name',
                                                              'username'})
        rest_utils.validate_inputs(request_dict)
        return multi_tenancy.remove_user_from_tenant(
            request_dict['username'],
            request_dict['tenant_name']
        )


class TenantGroups(SecuredMultiTenancyResource):
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(TenantResponse)
    def put(self, multi_tenancy):
        """
        Add a group to a tenant
        """
        request_dict = rest_utils.get_json_and_verify_params({'tenant_name',
                                                              'group_name'})
        rest_utils.validate_inputs(request_dict)
        return multi_tenancy.add_group_to_tenant(
            request_dict['group_name'],
            request_dict['tenant_name']
        )

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(TenantResponse)
    def delete(self, multi_tenancy):
        """
        Remove a group from a tenant
        """
        request_dict = rest_utils.get_json_and_verify_params({'tenant_name',
                                                              'group_name'})
        rest_utils.validate_inputs(request_dict)
        return multi_tenancy.remove_group_from_tenant(
            request_dict['group_name'],
            request_dict['tenant_name']
        )
