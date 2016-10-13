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

from manager_rest.storage import models
from manager_rest.security import SecuredResource
from manager_rest.resources import (marshal_with,
                                    exceptions_handled)
from manager_rest.resources_v2 import (create_filters,
                                       paginate,
                                       sortable,
                                       verify_json_content_type,
                                       verify_parameter_in_request_body)
from manager_rest.manager_exceptions import BadParametersError
from manager_rest.security.security_models import User as UserModel

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
        (None, ) * 5
    SecuredMultiTenancyResource, ClusterResourceBase = (SecuredResource, ) * 2


class Tenants(SecuredMultiTenancyResource):
    @exceptions_handled
    @marshal_with(TenantResponse)
    @create_filters(models.Tenant.fields)
    @paginate
    @sortable
    def get(self, multi_tenancy, _include=None, filters=None, pagination=None,
            sort=None, **kwargs):
        """
        List tenants
        """
        return multi_tenancy.list_tenants(_include, filters, pagination, sort)


class TenantsId(SecuredMultiTenancyResource):
    @exceptions_handled
    @marshal_with(TenantResponse)
    def post(self, tenant_name, multi_tenancy):
        """
        Create a tenant
        """
        return multi_tenancy.create_tenant(tenant_name)

    @exceptions_handled
    @marshal_with(TenantResponse)
    def get(self, tenant_name, multi_tenancy):
        """
        Get details for a single tenant
        """
        return multi_tenancy.get_tenant(tenant_name)


class TenantUsers(SecuredMultiTenancyResource):
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


class TenantGroups(SecuredMultiTenancyResource):
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


class UserGroups(SecuredMultiTenancyResource):
    @exceptions_handled
    @marshal_with(GroupResponse)
    @create_filters(models.Group.fields)
    @paginate
    @sortable
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


class UserGroupsId(SecuredMultiTenancyResource):
    @exceptions_handled
    @marshal_with(GroupResponse)
    def post(self, group_name, multi_tenancy):
        """
        Create a group
        """
        return multi_tenancy.create_group(group_name)

    @exceptions_handled
    @marshal_with(GroupResponse)
    def get(self, group_name, multi_tenancy):
        """
        Get info for a single group
        """
        return multi_tenancy.get_group(group_name)


class Users(SecuredMultiTenancyResource):
    @exceptions_handled
    @marshal_with(UserResponse)
    @create_filters(UserModel.fields)
    @paginate
    @sortable
    def get(self, multi_tenancy, _include=None, filters=None, pagination=None,
            sort=None, **kwargs):
        """
        List users
        """
        return multi_tenancy.list_users(_include,
                                        filters,
                                        pagination,
                                        sort)

    @exceptions_handled
    @marshal_with(UserResponse)
    def put(self, multi_tenancy):
        """
        Create a user
        """
        verify_json_content_type()
        request_json = request.json
        verify_parameter_in_request_body('username', request_json)
        verify_parameter_in_request_body('password', request_json)
        username = request_json['username']
        password = request_json['password']
        role_name = request_json.get('role')

        return multi_tenancy.create_user(username, password, role_name)


class UsersId(SecuredMultiTenancyResource):
    @exceptions_handled
    @marshal_with(UserResponse)
    def post(self, username, multi_tenancy):
        """
        Set password/role for a certain user
        """
        verify_json_content_type()
        request_json = request.json
        password = request_json.get('password')
        role_name = request_json.get('role')
        if password:
            if role_name:
                raise BadParametersError('Both `password` and `role` provided')
            return multi_tenancy.set_user_password(username, password)
        elif role_name:
            return multi_tenancy.set_user_role(username, role_name)
        else:
            raise BadParametersError('Neither `password` nor `role` provided')

    @exceptions_handled
    @marshal_with(UserResponse)
    def get(self, username, multi_tenancy):
        """
        Get details for a single user
        """
        return multi_tenancy.get_user(username)


class UsersGroups(SecuredMultiTenancyResource):
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
        return multi_tenancy.remove_user_from_group(
            request_json['username'],
            request_json['group_name']
        )


class Cluster(ClusterResourceBase):
    @exceptions_handled
    @marshal_with(ClusterState)
    @create_filters()
    def get(self, cluster, _include=None, filters=None):
        """
        Current state of the cluster.
        """
        return cluster.cluster_status(_include=_include, filters=filters)

    @exceptions_handled
    @marshal_with(ClusterState)
    def put(self, cluster):
        """
        Start the "create cluster" execution.

        The created cluster will already have one node (the current manager).
        """
        verify_json_content_type()
        request_json = request.get_json()
        verify_parameter_in_request_body('config', request_json)
        config = request_json['config']
        return cluster.start(config)

    @exceptions_handled
    @marshal_with(ClusterState)
    def patch(self, cluster):
        """
        Update the cluster config.

        Use this to change settings or promote a replica machine to master.
        """
        verify_json_content_type()
        request_json = request.get_json()
        verify_parameter_in_request_body('config', request_json)
        config = request_json['config']
        return cluster.update_config(config)


class ClusterNodes(ClusterResourceBase):
    @exceptions_handled
    @marshal_with(ClusterNode)
    def get(self, cluster):
        """
        List the nodes in the current cluster.

        This will also list inactive nodes that weren't deleted. 404 if the
        cluster isn't created yet.
        """
        return cluster.list_nodes()


class ClusterNodesId(ClusterResourceBase):
    @exceptions_handled
    @marshal_with(ClusterNode)
    def get(self, node_id, cluster):
        """
        Details of a node from the cluster.
        """
        return cluster.get_node(node_id)

    @exceptions_handled
    @marshal_with(ClusterState)
    def put(self, node_id, cluster):
        """
        Join the current manager to the cluster.
        """
        verify_json_content_type()
        request_json = request.get_json()
        verify_parameter_in_request_body('config', request_json)
        config = request_json['config']
        return cluster.join(config)

    @exceptions_handled
    @marshal_with(ClusterNode)
    def delete(self, node_id, cluster):
        """
        Remove the node from the cluster.

        Use this when a node is permanently down.
        """
        return cluster.remove_node(node_id)
