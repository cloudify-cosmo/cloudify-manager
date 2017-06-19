from flask import current_app

from manager_rest.storage.models import Tenant
from manager_rest.storage import get_storage_manager
from manager_rest.manager_exceptions import NotFoundError
from manager_rest.constants import (CLOUDIFY_TENANT_HEADER,
                                    CURRENT_TENANT_CONFIG)

from manager_rest.app_logging import raise_unauthorized_user_error


class TenantAuthorization(object):
    def authorize(self, user, request, tenant_name=None):
        logger = current_app.logger

        logger.debug('Tenant authorization for {0}'.format(user))

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
        if tenant not in user.all_tenants and not user.is_admin:
            raise_unauthorized_user_error(
                '{0} is not associated with {1}'.format(user, tenant)
            )

        current_app.config[CURRENT_TENANT_CONFIG] = tenant


tenant_authorizer = TenantAuthorization()
