from flask import current_app

from manager_rest.config import instance
from manager_rest.manager_exceptions import NotFoundError
from manager_rest.storage import get_storage_manager
from manager_rest.constants import CLOUDIFY_TENANT_HEADER, ADMIN_ROLE_NAME

from .user_handler import unauthorized_user_handler
from .security_models import user_datastore


class TenantAuthorization(object):
    def authorize(self, user, request):
        logger = current_app.logger

        logger.debug('Tenant authorization for user {0}'.format(user))

        admin_role = user_datastore.find_role(ADMIN_ROLE_NAME)
        tenant_name = request.headers.get(
            CLOUDIFY_TENANT_HEADER,
            instance.default_tenant_name
        )
        logger.debug(
            'User attempting to connect with tenant `{0}`'.format(tenant_name)
        )
        try:
            tenant = get_storage_manager().get_tenant_by_name(tenant_name)
        except NotFoundError:
            raise unauthorized_user_handler(
                'Provided tenant name unknown: {0}'.format(tenant_name)
            )
        if tenant not in user.get_all_tenants() \
                and admin_role not in user.roles:
            raise unauthorized_user_handler(
                'User {0} is not associated with tenant {1}'.format(
                    user.username,
                    tenant_name
                )
            )

        current_app.config['tenant'] = tenant

tenant_authorizer = TenantAuthorization()
