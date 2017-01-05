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
from manager_rest.security import (SecuredResource,
                                   MissingPremiumFeatureResource)
from manager_rest.manager_exceptions import (BadParametersError,
                                             MethodNotAllowedError)
from manager_rest.security.resource_permissions import PermissionsHandler

from flask import current_app

from . import rest_decorators
from .responses import BaseResponse, ResourceID
from .rest_utils import get_json_and_verify_params

try:
    from cloudify_premium import (TenantResponse,
                                  GroupResponse,
                                  UserResponse,
                                  SecuredMultiTenancyResource,
                                  ClusterResourceBase,
                                  ClusterState,
                                  ClusterNode)
except ImportError:
    TenantResponse, GroupResponse, UserResponse, ClusterNode, ClusterState = \
        (BaseResponse, ) * 5
    SecuredMultiTenancyResource = MissingPremiumFeatureResource
    ClusterResourceBase = MissingPremiumFeatureResource


class Tenants(SecuredMultiTenancyResource):
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(TenantResponse)
    @rest_decorators.create_filters(models.Tenant.resource_fields)
    @rest_decorators.paginate
    @rest_decorators.sortable
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
        return multi_tenancy.create_tenant(tenant_name)

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(TenantResponse)
    def get(self, tenant_name, multi_tenancy):
        """
        Get details for a single tenant
        """
        return multi_tenancy.get_tenant(tenant_name)

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(TenantResponse)
    def delete(self, tenant_name, multi_tenancy):
        """
        Delete a tenant
        """
        return multi_tenancy.delete_tenant(tenant_name)


class TenantUsers(SecuredMultiTenancyResource):
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(UserResponse)
    def put(self, multi_tenancy):
        """
        Add a user to a tenant
        """
        request_dict = get_json_and_verify_params({'tenant_name', 'username'})
        return multi_tenancy.add_user_to_tenant(
            request_dict['username'],
            request_dict['tenant_name']
        )

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(UserResponse)
    def delete(self, multi_tenancy):
        """
        Remove a user from a tenant
        """
        request_dict = get_json_and_verify_params({'tenant_name', 'username'})
        return multi_tenancy.remove_user_from_tenant(
            request_dict['username'],
            request_dict['tenant_name']
        )


class TenantGroups(SecuredMultiTenancyResource):
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(GroupResponse)
    def put(self, multi_tenancy):
        """
        Add a group to a tenant
        """
        request_dict = get_json_and_verify_params({'tenant_name',
                                                   'group_name'})
        return multi_tenancy.add_group_to_tenant(
            request_dict['group_name'],
            request_dict['tenant_name']
        )

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(GroupResponse)
    def delete(self, multi_tenancy):
        """
        Remove a group from a tenant
        """
        request_dict = get_json_and_verify_params({'tenant_name',
                                                   'group_name'})
        return multi_tenancy.remove_group_from_tenant(
            request_dict['group_name'],
            request_dict['tenant_name']
        )


class UserGroups(SecuredMultiTenancyResource):
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(GroupResponse)
    @rest_decorators.create_filters(models.Group.resource_fields)
    @rest_decorators.paginate
    @rest_decorators.sortable
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
        request_dict = get_json_and_verify_params()
        group_name = request_dict['group_name']
        ldap_group_dn = request_dict.get('ldap_group_dn')
        return multi_tenancy.create_group(group_name, ldap_group_dn)


class UserGroupsId(SecuredMultiTenancyResource):

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(GroupResponse)
    def get(self, group_name, multi_tenancy):
        """
        Get info for a single group
        """
        return multi_tenancy.get_group(group_name)

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(GroupResponse)
    def delete(self, group_name, multi_tenancy):
        """
        Delete a user group
        """
        return multi_tenancy.delete_group(group_name)


class Users(SecuredMultiTenancyResource):
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(UserResponse)
    @rest_decorators.create_filters(models.User.resource_fields)
    @rest_decorators.paginate
    @rest_decorators.sortable
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
    def put(self, multi_tenancy):
        """
        Create a user
        """
        request_dict = get_json_and_verify_params(
            {'username', 'password', 'role'}
        )
        return multi_tenancy.create_user(
            request_dict['username'],
            request_dict['password'],
            request_dict['role']
        )


class UsersId(SecuredMultiTenancyResource):
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(UserResponse)
    def post(self, username, multi_tenancy):
        """
        Set password/role for a certain user
        """
        request_dict = get_json_and_verify_params()
        password = request_dict.get('password')
        role_name = request_dict.get('role')
        if password:
            if role_name:
                raise BadParametersError('Both `password` and `role` provided')
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
        return multi_tenancy.get_user(username)

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(UserResponse)
    def delete(self, username, multi_tenancy):
        """
        Delete a user
        """
        return multi_tenancy.delete_user(username)


class UserGroupsUsers(SecuredMultiTenancyResource):
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(GroupResponse)
    def put(self, multi_tenancy):
        """
        Add a user to a group
        """
        if current_app.is_ldap_configured:
            raise MethodNotAllowedError(
                'Explicit group to user association is not permitted when '
                'using LDAP. Group association to users is done automatically'
                ' according to the groups associated with the user in LDAP.')
        request_dict = get_json_and_verify_params({'username', 'group_name'})
        return multi_tenancy.add_user_to_group(
            request_dict['username'],
            request_dict['group_name']
        )

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(GroupResponse)
    def delete(self, multi_tenancy):
        """
        Remove a user from a group
        """
        request_dict = get_json_and_verify_params({'username', 'group_name'})
        return multi_tenancy.remove_user_from_group(
            request_dict['username'],
            request_dict['group_name']
        )


class Cluster(ClusterResourceBase):
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(ClusterState)
    @rest_decorators.create_filters()
    def get(self, cluster, _include=None, filters=None):
        """
        Current state of the cluster.
        """
        return cluster.cluster_status(_include=_include, filters=filters)

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(ClusterState)
    def put(self, cluster):
        """
        Start the "create cluster" execution.

        The created cluster will already have one node (the current manager).
        """
        request_dict = get_json_and_verify_params({'config'})
        return cluster.start(request_dict['config'])

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(ClusterState)
    def patch(self, cluster):
        """
        Update the cluster config.

        Use this to change settings or promote a replica machine to master.
        """
        request_dict = get_json_and_verify_params({'config'})
        return cluster.update_config(request_dict['config'])


class ClusterNodes(ClusterResourceBase):
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(ClusterNode)
    def get(self, cluster):
        """
        List the nodes in the current cluster.

        This will also list inactive nodes that weren't deleted. 404 if the
        cluster isn't created yet.
        """
        return cluster.list_nodes()


class ClusterNodesId(ClusterResourceBase):
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(ClusterNode)
    def get(self, node_id, cluster):
        """
        Details of a node from the cluster.
        """
        return cluster.get_node(node_id)

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(ClusterState)
    def put(self, node_id, cluster):
        """
        Join the current manager to the cluster.
        """
        request_dict = get_json_and_verify_params({'config'})
        return cluster.join(request_dict['config'])

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(ClusterNode)
    def delete(self, node_id, cluster):
        """
        Remove the node from the cluster.

        Use this when a node is permanently down.
        """
        return cluster.remove_node(node_id)


class Permissions(SecuredResource):
    @staticmethod
    def _get_and_validate_params():
        return get_json_and_verify_params({
            'resource_type': {},
            'resource_id': {},
            'users': {'type': list},
            'permission': {'optional': True}
        })

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(ResourceID)
    def put(self):
        """Add permissions to a resource
        """
        params = self._get_and_validate_params()
        return PermissionsHandler.add_permissions(params)

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(ResourceID)
    def delete(self):
        """Remove permissions from a resource
        """
        params = self._get_and_validate_params()
        return PermissionsHandler.remove_permissions(params)
