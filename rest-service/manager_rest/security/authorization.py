
from functools import wraps

from flask import request, current_app
from flask_security import current_user

from manager_rest import config
from manager_rest.storage.models import Tenant
from manager_rest.storage import get_storage_manager
from manager_rest.app_logging import raise_unauthorized_user_error
from manager_rest.manager_exceptions import NotFoundError, UnauthorizedError
from manager_rest.constants import (CLOUDIFY_TENANT_HEADER,
                                    CURRENT_TENANT_CONFIG)


def authorize(action, request_tenant=None):
    def authorize_dec(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            tenant_name = request_tenant or request.headers.get(
                CLOUDIFY_TENANT_HEADER)
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

            if config.instance.test_mode:
                return func(*args, **kwargs)
            user_roles = current_user.all_tenants.get(tenant_name, []) \
                + [current_user.role]
            action_roles = config.instance.authorization_permissions[action]

            for user_role in user_roles:
                if user_role in action_roles:
                    return func(*args, **kwargs)
            raise UnauthorizedError(
                'User {0} is not permitted to perform the action {1}'.format(
                    current_user.username, action)
            )
        return wrapper
    return authorize_dec
