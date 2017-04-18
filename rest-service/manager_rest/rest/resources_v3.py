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

from flask_security import current_user
from flask import current_app, request
from toolz import dicttoolz

from manager_rest.constants import (FILE_SERVER_BLUEPRINTS_FOLDER,
                                    FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
                                    FILE_SERVER_DEPLOYMENTS_FOLDER)

from manager_rest import config
from manager_rest.dsl_functions import evaluate_intrinsic_functions
from manager_rest.storage import models, get_storage_manager
from manager_rest.security import (SecuredResource,
                                   SecuredResourceSkipTenantAuth,
                                   MissingPremiumFeatureResource)
from manager_rest.manager_exceptions import (BadParametersError,
                                             MethodNotAllowedError,
                                             UnauthorizedError)

from .. import utils
from . import rest_decorators, rest_utils
from ..security.authentication import authenticator
from ..security.tenant_authorization import tenant_authorizer
from .resources_v1.nodes import NodeInstancesId as v1_NodeInstancesId
from .resources_v2 import (
    Events as v2_Events,
    Nodes as v2_Nodes,
)
from .responses_v3 import BaseResponse, ResourceID, SecretsListResponse

try:
    from cloudify_premium import (TenantResponse,
                                  GroupResponse,
                                  LdapResponse,
                                  UserResponse,
                                  SecuredMultiTenancyResource,
                                  ClusterResourceBase,
                                  ClusterState,
                                  ClusterNode,
                                  SecuredMultiTenancyResourceSkipTenantAuth)
except ImportError:
    TenantResponse, GroupResponse, UserResponse, ClusterNode, LdapResponse,\
        ClusterState = (BaseResponse, ) * 6
    SecuredMultiTenancyResource = MissingPremiumFeatureResource
    ClusterResourceBase = MissingPremiumFeatureResource
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
        Join the current manager to the cluster, or start a new one.

        If created, the cluster will already have one node (the current
        manager).
        """
        config = rest_utils.get_json_and_verify_params({
            'host_ip': {'type': unicode},
            'node_name': {'type': unicode},
            'join_addrs': {'type': list, 'optional': True},
            # opaque data - generated by the cluster, clients need
            # not examine it
            'credentials': {'optional': True},
        })
        if 'join_addrs' in config:
            return cluster.join(config)
        else:
            return cluster.start(config)

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(ClusterState)
    def patch(self, cluster):
        """
        Update the cluster config.

        Use this to change settings or promote a replica machine to master.
        """
        config = rest_utils.get_json_and_verify_params()
        return cluster.update_config(config)


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
    @rest_decorators.marshal_with(ClusterNode)
    def put(self, node_id, cluster):
        """Add a node to the cluster.

        Run validations, prepare credentials for that node to use.
        """
        details = rest_utils.get_json_and_verify_params({
            'host_ip': {'type': unicode},
            'node_name': {'type': unicode},
        })
        return cluster.add_node(details)

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(ClusterNode)
    def delete(self, node_id, cluster):
        """
        Remove the node from the cluster.

        Use this when a node is permanently down.
        """
        return cluster.remove_node(node_id)


class FileServerAuth(SecuredResourceSkipTenantAuth):
    @staticmethod
    def _verify_tenant(uri):
        tenanted_resources = [
            FILE_SERVER_BLUEPRINTS_FOLDER,
            FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
            FILE_SERVER_DEPLOYMENTS_FOLDER
        ]
        tenanted_resources = [r.strip('/') for r in tenanted_resources]
        uri = uri.strip('/')

        # verifying that the only tenant that can be accessed is the one in
        # the header
        for resource in tenanted_resources:
            if uri.startswith(resource):
                uri = uri.replace(resource, '').strip('/')
                uri_tenant, _ = uri.split('/', 1)
                user = authenticator.authenticate(request)
                tenant_authorizer.authorize(user, request, uri_tenant)

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(ResourceID)
    def get(self, **_):
        """
        Verify that the user is allowed to access requested resource.

        The user cannot access tenants except the one in the request's header.
        """
        uri = request.headers.get('X-Original-Uri')
        self._verify_tenant(uri)

        # verified successfully
        return {}


class LdapAuthentication(SecuredResource):
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(LdapResponse)
    def post(self):
        ldap_config = self._validate_set_ldap_request()

        from cloudify_premium.multi_tenancy.ldap_authentication \
            import LdapAuthentication

        # update current configuration
        for key, value in ldap_config.iteritems():
            setattr(config.instance, key, value)

        # assert LDAP configuration is valid.
        authenticator = LdapAuthentication()
        authenticator.configure_ldap()
        try:
            authenticator.authenticate_user(ldap_config.get('ldap_username'),
                                            ldap_config.get('ldap_password'))
        except UnauthorizedError:
            # reload previous configuration.
            config.instance.load_configuration()
            raise BadParametersError(
                'Failed setting LDAP authenticator: Invalid parameters '
                'provided.')

        config.reset(config.instance, write=True)

        # Restart the rest service so that each the LDAP configuration
        # be loaded to all flask processes.
        rest_utils.set_restart_task()

        ldap_config.pop('ldap_password')
        return ldap_config

    @staticmethod
    def _validate_set_ldap_request():
        if not current_user.is_admin:
            raise UnauthorizedError('User is not authorized to set LDAP '
                                    'configuration.')
        if not _only_admin_in_manager():
            raise MethodNotAllowedError('LDAP Configuration may be set only on'
                                        ' a clean manager.')
        if not current_app.premium_enabled:
            raise MethodNotAllowedError('LDAP is only supported in the '
                                        'Cloudify premium edition.')
        ldap_config = rest_utils.get_json_and_verify_params({
            'ldap_server',
            'ldap_username',
            'ldap_password',
            'ldap_domain',
            'ldap_is_active_directory',
            'ldap_dn_extra'
        })
        return ldap_config


class SecretsKey(SecuredResource):
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.Secret)
    def get(self, key):
        """
        Get secret by key
        """

        rest_utils.validate_inputs({'key': key})
        return get_storage_manager().get(models.Secret, key)

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.Secret)
    def put(self, key):
        """
        Create a new secret
        """

        key, value = self._validate_secret_inputs(key)

        return get_storage_manager().put(models.Secret(
            id=key,
            value=value,
            created_at=utils.get_formatted_timestamp(),
            updated_at=utils.get_formatted_timestamp()
        ))

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.Secret)
    def patch(self, key):
        """
        Update an existing secret
        """

        key, value = self._validate_secret_inputs(key)
        secret = get_storage_manager().get(models.Secret, key)
        secret.value = value
        secret.updated_at = utils.get_formatted_timestamp()
        return get_storage_manager().update(secret)

    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(models.Secret)
    def delete(self, key):
        """
        Delete a secret
        """

        rest_utils.validate_inputs({'key': key})
        storage_manager = get_storage_manager()
        secret = storage_manager.get(models.Secret, key)
        return storage_manager.delete(secret)

    def _validate_secret_inputs(self, key):
        request_dict = rest_utils.get_json_and_verify_params({'value'})
        value = request_dict['value']
        rest_utils.validate_inputs({'key': key})
        return key, value


class Secrets(SecuredResource):
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(SecretsListResponse)
    @rest_decorators.create_filters(models.Secret)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.Secret)
    @rest_decorators.all_tenants
    def get(self, _include=None, filters=None, pagination=None, sort=None,
            all_tenants=None, **kwargs):
        """
        List secrets
        """

        return get_storage_manager().list(
            models.Secret,
            include=_include,
            filters=filters,
            pagination=pagination,
            sort=sort,
            all_tenants=all_tenants
        )


class Nodes(v2_Nodes):
    @rest_decorators.evaluate_functions
    def get(self, evaluate_functions=False, *args, **kwargs):
        # We don't skip marshalling, because we want an already marshalled
        # object, to avoid setting evaluated secrets in the node's properties
        nodes = super(Nodes, self).get(*args, **kwargs)
        if evaluate_functions:
            for node in nodes['items']:
                evaluate_intrinsic_functions(node['properties'],
                                             node['deployment_id'])
        return nodes


class NodeInstancesId(v1_NodeInstancesId):
    @rest_decorators.evaluate_functions
    def get(self, evaluate_functions=False, *args, **kwargs):
        # We don't skip marshalling, because we want an already marshalled
        # object, to avoid setting evaluated secrets in the node instances's
        # runtime properties
        node_instance = super(NodeInstancesId, self).get(*args, **kwargs)
        if evaluate_functions:
            evaluate_intrinsic_functions(node_instance['runtime_properties'],
                                         node_instance['deployment_id'])
        return node_instance


class Events(v2_Events):
    """Events resource.

    Through the events endpoint a user can retrieve both events and logs as
    stored in the SQL database.

    """

    UNUSED_FIELDS = ['id', 'node_id', 'message_code']

    @staticmethod
    def _map_event_to_dict(_include, sql_event):
        """Map event to a dictionary to be sent as an API response.

        In this implementation, the goal is to return a flat structure as
        opposed to the nested one that was returned by Elasticsearch in the
        past (see v1 implementation for more information).

        :param _include:
            Projection used to get records from database
        :type _include: list(str)
        :param sql_event: Event data returned when SQL query was executed
        :type sql_event: :class:`sqlalchemy.util._collections.result`
        :returns: Event as would have returned by elasticsearch
        :rtype: dict(str)

        """
        event = {
            attr: getattr(sql_event, attr)
            for attr in sql_event.keys()
        }
        event['reported_timestamp'] = event['timestamp']

        for unused_field in Events.UNUSED_FIELDS:
            if unused_field in event:
                del event[unused_field]

        if event['type'] == 'cloudify_event':
            del event['logger']
            del event['level']
        elif event['type'] == 'cloudify_log':
            del event['event_type']

        # Keep only keys passed in the _include request argument
        # TBD: Do the projection at the database level
        if _include is not None:
            event = dicttoolz.keyfilter(lambda key: key in _include, event)

        return event


def _only_admin_in_manager():
    """
    True if no users other than the admin user exists.
    :return:
    """
    users = get_storage_manager().list(models.User)
    return len(users) == 1
