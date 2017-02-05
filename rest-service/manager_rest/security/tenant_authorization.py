from flask import current_app

from manager_rest.storage.models import Tenant
from manager_rest.manager_exceptions import NotFoundError
from manager_rest.storage import get_storage_manager, user_datastore
from manager_rest.constants import (CLOUDIFY_TENANT_HEADER,
                                    ADMIN_ROLE,
                                    CURRENT_TENANT_CONFIG)

from manager_rest.app_logging import raise_unauthorized_user_error


class TenantAuthorization(object):
    def authorize(self, user, request, tenant_name=None):
        logger = current_app.logger

        logger.debug('Tenant authorization for {0}'.format(user))

        admin_role = user_datastore.find_role(ADMIN_ROLE)
        if tenant_name is None:
            tenant_name = request.headers.get(CLOUDIFY_TENANT_HEADER)
        if not tenant_name:
            raise raise_unauthorized_user_error(
                'a Tenant name was not provided')
        try:
            tenant = get_storage_manager().get(
                Tenant,
                tenant_name,
                filters={'name': tenant_name}
            )
        except NotFoundError:
            raise_unauthorized_user_error(
                'Provided tenant name unknown: {0}'.format(tenant_name)
            )

        logger.debug('User attempting to connect with {0}'.format(tenant))
        if tenant not in user.all_tenants and admin_role not in user.roles:
            raise_unauthorized_user_error(
                '{0} is not associated with {1}'.format(user, tenant)
            )

        current_app.config[CURRENT_TENANT_CONFIG] = tenant


tenant_authorizer = TenantAuthorization()
