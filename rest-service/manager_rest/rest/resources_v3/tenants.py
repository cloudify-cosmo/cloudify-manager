from typing import Any

from flask import request

from manager_rest import constants
from manager_rest.manager_exceptions import (
    BadParametersError,
    MissingPremiumPackage
)
from manager_rest.storage import get_storage_manager, models
from manager_rest.security.authorization import authorize
from manager_rest.security import (MissingPremiumFeatureResource,
                                   SecuredResource,
                                   allow_on_community,
                                   is_user_action_allowed)
from .. import rest_decorators, rest_utils
from ..responses_v3 import TenantResponse

from cloudify.cryptography_utils import decrypt

TenantsListResource: Any
try:
    from cloudify_premium.multi_tenancy.secured_tenant_resource \
        import SecuredMultiTenancyResource
    TenantsListResource = SecuredMultiTenancyResource
except ImportError:
    SecuredMultiTenancyResource = MissingPremiumFeatureResource

    # In community edition tenants list should work without multi-tenancy
    TenantsListResource = SecuredResource


class Tenants(TenantsListResource):
    @authorize('tenant_list')
    @rest_decorators.marshal_with(TenantResponse)
    @rest_decorators.create_filters(models.Tenant)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.Tenant)
    @rest_decorators.search('name')
    def get(self, multi_tenancy=None, _include=None, filters=None,
            pagination=None, sort=None, search=None, **kwargs):
        """
        List tenants
        """
        @authorize('tenant_list_get_data')
        def _authorize_with_get_data():
            pass

        if rest_utils.verify_and_convert_bool(
                'get_data', request.args.get('_get_data', False)):
            _authorize_with_get_data()

        get_all_results = rest_utils.verify_and_convert_bool(
            '_get_all_results',
            request.args.get('_get_all_results', False)
        )
        if multi_tenancy:
            tenants = multi_tenancy.list_tenants(_include,
                                                 filters,
                                                 pagination,
                                                 sort,
                                                 search,
                                                 get_all_results)
        else:
            # In community edition we have only the `default_tenant`, so it
            # should be safe to return it like this
            tenants = get_storage_manager().list(models.Tenant)

        # if include is not passed in request, then the _include argument
        # will contain all fields. However, we only want to return these
        # fields, if the user _explicitly_ asked for them in request
        request_include = request.args.get('_include')
        if (
            request_include is not None
            and any(f'rabbitmq_{attr}' in request_include
                    for attr in ['password', 'username', 'vhost'])
        ):
            for tenant in tenants:
                if is_user_action_allowed('tenant_rabbitmq_credentials',
                                          tenant.name):
                    if 'rabbitmq_password' in request_include:
                        tenant.rabbitmq_password = decrypt(
                            tenant.rabbitmq_password)
                else:
                    _clear_tenant_rabbit_creds(tenant)
        else:
            for tenant in tenants:
                _clear_tenant_rabbit_creds(tenant)
        return tenants


def _clear_tenant_rabbit_creds(tenant):
    tenant.rabbitmq_password = None
    tenant.rabbitmq_username = None
    tenant.rabbitmq_vhost = None


class TenantsId(SecuredMultiTenancyResource):
    @authorize('tenant_create')
    @rest_decorators.marshal_with(TenantResponse)
    def post(self, tenant_name, multi_tenancy):
        """
        Create a tenant
        """
        rest_utils.validate_inputs({'tenant_name': tenant_name})
        if request.content_length:
            request_dict = rest_utils.get_json_and_verify_params({
                'rabbitmq_password': {'type': str, 'optional': True},
            })
        else:
            request_dict = {}
        if tenant_name in ('users', 'user-groups'):
            raise BadParametersError(
                '{0!r} is not allowed as a tenant name '
                "because it wouldn't be possible to remove it later due to "
                'a conflict with the remove {0} from tenant endpoint'
                .format(str(tenant_name))
            )
        return multi_tenancy.create_tenant(
            tenant_name,
            request_dict.get('rabbitmq_password'))

    @authorize('tenant_get', get_tenant_from='param')
    @rest_decorators.marshal_with(TenantResponse)
    @allow_on_community
    def get(self, tenant_name, multi_tenancy=None):
        """Get details for a single tenant

        On community, only getting the default tenant is allowed.
        """
        rest_utils.validate_inputs({'tenant_name': tenant_name})
        if tenant_name != constants.DEFAULT_TENANT_NAME and not multi_tenancy:
            raise MissingPremiumPackage()
        tenant = get_storage_manager().get(
            models.Tenant,
            None,
            filters={'name': tenant_name})
        if is_user_action_allowed(
                'tenant_rabbitmq_credentials', tenant_name):
            tenant.rabbitmq_password = decrypt(tenant.rabbitmq_password)
        else:
            _clear_tenant_rabbit_creds(tenant)
        return tenant

    @authorize('tenant_delete')
    def delete(self, tenant_name, multi_tenancy):
        """
        Delete a tenant
        """
        rest_utils.validate_inputs({'tenant_name': tenant_name})
        multi_tenancy.delete_tenant(tenant_name)
        return None, 204


class TenantUsers(SecuredMultiTenancyResource):
    @authorize('tenant_add_user', get_tenant_from='data')
    @rest_decorators.marshal_with(TenantResponse)
    @rest_decorators.check_external_authenticator('add user to tenant')
    def put(self, multi_tenancy):
        """
        Add a user to a tenant
        """
        request_dict = rest_utils.get_json_and_verify_params(
            {
                'tenant_name': {
                    'type': str
                },
                'username': {
                    'type': str
                },
                'role': {
                    'type': str
                },
            },
        )
        rest_utils.validate_inputs(request_dict)
        role_name = request_dict.get('role')
        if role_name:
            rest_utils.verify_role(role_name)
        else:
            role_name = constants.DEFAULT_TENANT_ROLE

        return multi_tenancy.add_user_to_tenant(
            request_dict['username'],
            request_dict['tenant_name'],
            role_name,
        )

    @authorize('tenant_update_user', get_tenant_from='data')
    @rest_decorators.marshal_with(TenantResponse)
    @rest_decorators.check_external_authenticator('update user in tenant')
    def patch(self, multi_tenancy):
        """Update role in user tenant association."""
        request_dict = rest_utils.get_json_and_verify_params(
            {
                'tenant_name': {
                    'type': str,
                },
                'username': {
                    'type': str,
                },
                'role': {
                    'type': str,
                },
            },
        )
        rest_utils.validate_inputs(request_dict)
        role_name = request_dict['role']
        rest_utils.verify_role(role_name)
        return multi_tenancy.update_user_in_tenant(
            request_dict['username'],
            request_dict['tenant_name'],
            role_name,
        )

    @authorize('tenant_remove_user', get_tenant_from='data')
    @rest_decorators.check_external_authenticator('remove user from tenant')
    def delete(self, multi_tenancy):
        """
        Remove a user from a tenant
        """
        request_dict = rest_utils.get_json_and_verify_params({'tenant_name',
                                                              'username'})
        rest_utils.validate_inputs(request_dict)
        multi_tenancy.remove_user_from_tenant(
            request_dict['username'],
            request_dict['tenant_name']
        )
        return None, 204


class TenantGroups(SecuredMultiTenancyResource):
    @authorize('tenant_add_group', get_tenant_from='data')
    @rest_decorators.marshal_with(TenantResponse)
    def put(self, multi_tenancy):
        """
        Add a group to a tenant
        """
        request_dict = rest_utils.get_json_and_verify_params(
            {
                'tenant_name': {
                    'type': str
                },
                'group_name': {
                    'type': str
                },
                'role': {
                    'type': str
                },
            })
        rest_utils.validate_inputs(request_dict)
        role_name = request_dict.get('role')
        if role_name:
            rest_utils.verify_role(role_name)
        else:
            role_name = constants.DEFAULT_TENANT_ROLE

        return multi_tenancy.add_group_to_tenant(
            request_dict['group_name'],
            request_dict['tenant_name'],
            role_name,
        )

    @authorize('tenant_update_group', get_tenant_from='data')
    @rest_decorators.marshal_with(TenantResponse)
    def patch(self, multi_tenancy):
        """Update role in group tenant association."""
        request_dict = rest_utils.get_json_and_verify_params(
            {
                'tenant_name': {
                    'type': str,
                },
                'group_name': {
                    'type': str,
                },
                'role': {
                    'type': str,
                },
            },
        )
        rest_utils.validate_inputs(request_dict)
        role_name = request_dict['role']
        rest_utils.verify_role(role_name)
        return multi_tenancy.update_group_in_tenant(
            request_dict['group_name'],
            request_dict['tenant_name'],
            role_name,
        )

    @authorize('tenant_remove_group', get_tenant_from='data')
    def delete(self, multi_tenancy):
        """
        Remove a group from a tenant
        """
        request_dict = rest_utils.get_json_and_verify_params({'tenant_name',
                                                              'group_name'})
        rest_utils.validate_inputs(request_dict)
        multi_tenancy.remove_group_from_tenant(
            request_dict['group_name'],
            request_dict['tenant_name']
        )
        return None, 204
