from flask import current_app
from flask_restful_swagger import swagger

from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize


class Idp(SecuredResource):
    @swagger.operation(
        nickname="idp",
        notes="Returns which identity service is used on this manager"
    )
    @authorize('identity_provider_get')
    def get(self):
        """Get the current identity provider for this manager"""
        if current_app.external_auth:
            return ','.join(
                current_app.external_auth.all_authenticators.keys())
        else:
            return 'local'
