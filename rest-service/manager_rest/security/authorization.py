
from functools import wraps

from flask import request
from flask_security import current_user

from cloudify._compat import text_type

from manager_rest import config, utils, execution_token
from manager_rest.security import audit
from manager_rest.storage.models import Tenant
from manager_rest.storage import get_storage_manager
from manager_rest.constants import CLOUDIFY_TENANT_HEADER
from manager_rest.manager_exceptions import NotFoundError, ForbiddenError
from manager_rest.rest.rest_utils import (get_json_and_verify_params,
                                          request_use_all_tenants)


def authorize(action,
              tenant_for_auth=None,
              get_tenant_from='header',
              allow_all_tenants=False,
              allow_if_execution=False):
    def authorize_dec(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            execution = execution_token.current_execution
            if execution and allow_if_execution:
                utils.set_current_tenant(execution.tenant)
                return func(*args, **kwargs)

            # getting the tenant name
            if get_tenant_from == 'header':
                tenant_name = tenant_for_auth or request.headers.get(
                    CLOUDIFY_TENANT_HEADER)
            elif get_tenant_from == 'param':
                tenant_name = tenant_for_auth or kwargs['tenant_name']
            elif get_tenant_from == 'data':
                tenant_name = tenant_for_auth or get_json_and_verify_params(
                    {'tenant_name': {'type': text_type}}).get('tenant_name')
            else:
                tenant_name = tenant_for_auth

            # finding tenant to add to the app config
            if tenant_name:
                try:
                    tenant = get_storage_manager().get(
                        Tenant,
                        None,
                        filters={'name': tenant_name}
                    )
                    utils.set_current_tenant(tenant)
                    audit.set_tenant(tenant.name)
                except NotFoundError:
                    raise ForbiddenError(
                        'Authorization failed: Tried to authenticate with '
                        'invalid tenant name: {0}'.format(tenant_name)
                    )

            # when running unittests, there is no authorization
            if config.instance.test_mode:
                return func(*args, **kwargs)

            # checking if any of the user's roles is allowed to perform action
            if is_user_action_allowed(action, tenant_name, allow_all_tenants):
                return func(*args, **kwargs)

        return wrapper
    return authorize_dec


def get_current_user_roles(tenant_name=None, allow_all_tenants=False):
    if not current_user.is_authenticated:
        return []

    tenant_roles = []

    # extracting tenant roles for user in the tenant
    for t in current_user.all_tenants:
        if (allow_all_tenants and request_use_all_tenants()) \
                or t.name == tenant_name:
            tenant_roles += current_user.all_tenants[t]

    # joining user's system role with his tenant roles
    user_roles = [role.name for role in tenant_roles] \
        + current_user.system_roles
    return user_roles


def is_user_action_allowed(action, tenant_name=None, allow_all_tenants=False):
    if not current_user.active:
        raise ForbiddenError(
            'Authorization failed: '
            'User `{0}` is deactivated'.format(current_user.username)
        )
    user_roles = get_current_user_roles(tenant_name, allow_all_tenants)
    action_roles = config.instance.authorization_permissions[action]
    if not set(user_roles) & set(action_roles):
        # none of the user's role is allowed to perform the action
        error_message = 'User `{0}` is not permitted to perform the ' \
                        'action {1}'.format(current_user.username, action)
        if tenant_name:
            error_message += ' in the tenant `{0}`'.format(tenant_name)
        raise ForbiddenError(error_message)
    return True
