import pydantic
from typing import Any, Optional

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


class _TenantsListQuery(rest_utils.ListQuery):
    _get_data: Optional[bool] = False


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

        args = _TenantsListQuery.parse_obj(request.args)
        if args._get_data:
            _authorize_with_get_data()

        if multi_tenancy:
            tenants = multi_tenancy.list_tenants(_include,
                                                 filters,
                                                 pagination,
                                                 sort,
                                                 search,
                                                 args.get_all_results)
        else:
            # In community edition we have only the `default_tenant`, so it
            # should be safe to return it like this
            tenants = get_storage_manager().list(models.Tenant)

        if (
            _include is not None
            and any(f'rabbitmq_{attr}' in _include
                    for attr in ['password', 'username', 'vhost'])
        ):
            for tenant in tenants:
                if is_user_action_allowed('tenant_rabbitmq_credentials',
                                          tenant.name):
                    if 'rabbitmq_password' in _include:
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


class _TenantCreateArgs(pydantic.BaseModel):
    rabbitmq_password: Optional[str] = None


class TenantsId(SecuredMultiTenancyResource):
    @authorize('tenant_create')
    @rest_decorators.marshal_with(TenantResponse)
    def post(self, tenant_name, multi_tenancy):
        """
        Create a tenant
        """
        rest_utils.validate_inputs({'tenant_name': tenant_name})
        if request.content_length:
            args = _TenantCreateArgs.parse_obj(request.json)
            rabbitmq_password = args.rabbitmq_password
        else:
            rabbitmq_password = None
        if tenant_name in ('users', 'user-groups'):
            raise BadParametersError(
                '{0!r} is not allowed as a tenant name '
                "because it wouldn't be possible to remove it later due to "
                'a conflict with the remove {0} from tenant endpoint'
                .format(str(tenant_name))
            )
        return multi_tenancy.create_tenant(
            tenant_name,
            rabbitmq_password,
        )

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
        return "", 204


class _UserTenantArgs(pydantic.BaseModel):
    tenant_name: str
    username: str
    role: Optional[str] = constants.DEFAULT_TENANT_ROLE


class TenantUsers(SecuredMultiTenancyResource):
    @authorize('tenant_add_user', get_tenant_from='data')
    @rest_decorators.marshal_with(TenantResponse)
    @rest_decorators.check_external_authenticator('add user to tenant')
    def put(self, multi_tenancy):
        """
        Add a user to a tenant
        """
        request_dict = _UserTenantArgs.parse_obj(request.json).dict()
        rest_utils.validate_inputs(request_dict)
        role_name = request_dict.get('role')
        rest_utils.verify_role(role_name)

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
        request_dict = _UserTenantArgs.parse_obj(request.json).dict()
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
        request_dict = _UserTenantArgs.parse_obj(request.json).dict()
        rest_utils.validate_inputs(request_dict)
        multi_tenancy.remove_user_from_tenant(
            request_dict['username'],
            request_dict['tenant_name']
        )
        return "", 204


class _GroupTenantArgs(pydantic.BaseModel):
    tenant_name: str
    group_name: str
    role: Optional[str] = constants.DEFAULT_TENANT_ROLE


class TenantGroups(SecuredMultiTenancyResource):
    @authorize('tenant_add_group', get_tenant_from='data')
    @rest_decorators.marshal_with(TenantResponse)
    def put(self, multi_tenancy):
        """
        Add a group to a tenant
        """
        request_dict = _GroupTenantArgs.parse_obj(request.json).dict()
        rest_utils.validate_inputs(request_dict)
        role_name = request_dict.get('role')
        rest_utils.verify_role(role_name)

        return multi_tenancy.add_group_to_tenant(
            request_dict['group_name'],
            request_dict['tenant_name'],
            role_name,
        )

    @authorize('tenant_update_group', get_tenant_from='data')
    @rest_decorators.marshal_with(TenantResponse)
    def patch(self, multi_tenancy):
        """Update role in group tenant association."""
        request_dict = _GroupTenantArgs.parse_obj(request.json).dict()
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
        request_dict = _GroupTenantArgs.parse_obj(request.json).dict()
        rest_utils.validate_inputs(request_dict)
        multi_tenancy.remove_group_from_tenant(
            request_dict['group_name'],
            request_dict['tenant_name']
        )
        return "", 204
