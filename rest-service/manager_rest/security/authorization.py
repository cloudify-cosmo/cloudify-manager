
from functools import wraps

from flask import request, current_app
from flask_security import current_user

from manager_rest import config
from manager_rest.storage.models import Tenant
from manager_rest.storage import get_storage_manager
from manager_rest.app_logging import raise_unauthorized_user_error
from manager_rest.rest.rest_utils import get_json_and_verify_params
from manager_rest.manager_exceptions import NotFoundError, ForbiddenError
from manager_rest.constants import (CLOUDIFY_TENANT_HEADER,
                                    CURRENT_TENANT_CONFIG)


def authorize(action, tenant_for_auth=None, get_tenant_from='header'):
    def authorize_dec(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if get_tenant_from == 'header':
                tenant_name = tenant_for_auth or request.headers.get(
                    CLOUDIFY_TENANT_HEADER)
            elif get_tenant_from == 'param':
                tenant_name = tenant_for_auth or kwargs['tenant_name']
            elif get_tenant_from == 'data':
                tenant_name = tenant_for_auth or get_json_and_verify_params(
                    {'tenant_name': {'type': unicode}}).get('tenant_name')
            else:
                tenant_name = tenant_for_auth

            # finding tenant to add to the app config
            if tenant_name:
                try:
                    tenant = get_storage_manager().get(
                        Tenant,
                        tenant_name,
                        filters={'name': tenant_name}
                    )
                    current_app.config[CURRENT_TENANT_CONFIG] = tenant
                except NotFoundError:
                    raise_unauthorized_user_error(
                        'Provided tenant name unknown: {0}'.format(tenant_name)
                    )

            # when running unittests, there is no authorization
            if config.instance.test_mode:
                return func(*args, **kwargs)

            # extracting tenant roles for user in the tenant
            tenant_roles = []
            for t in current_user.all_tenants:
                if t.name == tenant_name:
                    tenant_roles = current_user.all_tenants[t]
                    break

            # joining user's system role with his tenant roles
            user_roles = [role.name for role in tenant_roles] \
                + [current_user.role]

            # getting the roles allowed to perform requested action
            action_roles = config.instance.authorization_permissions[action]

            # checking if any of the user's roles is allowed to perform action
            for user_role in user_roles:
                if user_role in action_roles:
                    return func(*args, **kwargs)

            # none of the user's role is allowed to perform the action
            error_message = 'User `{0}` is not permitted to perform the ' \
                            'action {1}'.format(current_user.username, action)
            if tenant_name:
                error_message += ' in the tenant `{0}`'.format(tenant_name)
            raise ForbiddenError(error_message)
        return wrapper
    return authorize_dec
