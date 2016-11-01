from flask import current_app

from manager_rest import config
from manager_rest.storage.models import Tenant
from manager_rest.manager_exceptions import NotFoundError
from manager_rest.storage import get_storage_manager, user_datastore
from manager_rest.constants import CLOUDIFY_TENANT_HEADER, SYSTEM_ADMIN_ROLE

from .user_handler import unauthorized_user_handler


class TenantAuthorization(object):
    def authorize(self, user, request):
        logger = current_app.logger

        logger.debug('Tenant authorization for {0}'.format(user))

        admin_role = user_datastore.find_role(SYSTEM_ADMIN_ROLE)
        tenant_name = request.headers.get(
            CLOUDIFY_TENANT_HEADER,
            config.instance.default_tenant_name
        )
        try:
            tenant = get_storage_manager().get(
                Tenant,
                tenant_name,
                filters={'name': tenant_name}
            )
        except NotFoundError:
            raise unauthorized_user_handler(
                'Provided tenant name unknown: {0}'.format(tenant_name)
            )

        logger.debug('User attempting to connect with {0}'.format(tenant))
        if tenant not in user.get_all_tenants() \
                and admin_role not in user.roles:
            raise unauthorized_user_handler(
                'User {0} is not associated with tenant {1}'.format(
                    user.username,
                    tenant_name
                )
            )

        current_app.config['tenant_id'] = tenant.id

tenant_authorizer = TenantAuthorization()
