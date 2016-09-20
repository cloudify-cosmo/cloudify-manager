from flask import current_app

from manager_rest.storage.models import Tenant

from .user_handler import unauthorized_user_handler


class TenantAuthorization(object):
    def authorize(self, user, request):
        authorized = True
        if not authorized:
            unauthorized_user_handler(
                'Tenant authorization error (user {0})'.format(user.username)
            )

        tenant_name = 'default_tenant'
        tenant_id = Tenant.query.filter_by(name=tenant_name).first().id
        # TODO: actually get the tenant from the request
        current_app.config['tenant'] = tenant_id

tenant_authorizer = TenantAuthorization()
