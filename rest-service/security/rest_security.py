import datetime

from flask import abort
from flask.ext.security import Security

from security.datastores.datastore_manager import DatastoreManager
from security.authentication_providers.authentication_manager \
    import AuthenticationManager


class RestSecurity():

    def __init__(self, app):
        self.security = None
        self.app = app
        if not app:
            raise Exception('required parameter "app" is not set')

        self.secure_app()

    def secure_app(self):
        self.app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(seconds=30)
        self.app.config['SECRET_KEY'] = 'the quick brown fox jumps over the lazy dog'
        user_datastore = DatastoreManager().get_datastore_driver(self.app)
        self.security = Security(self.app, user_datastore)

        self.security.login_manager.request_loader(self._request_loader)
        self.security.login_manager.unauthorized_handler(self._unauthorized_handler)

    def _request_loader(self, request):
        user = None

        '''
        # first, try to login using the api_key url arg
        api_key = request.args.get('api_key')
        if api_key:
            # TODO should use find or get here?
            api_key_parts = api_key.split(':')
            username = api_key_parts[0]
            password = api_key_parts[1]
            user = self.security.datastore.get_user(username)
        '''

        # next, try to login using Basic Auth
        # if not user:

        api_key = request.headers.get('Authorization')
        if not api_key:
            raise Exception('Authorization header not found on request')

        api_key = api_key.replace('Basic ', '', 1)
        try:
            from itsdangerous import base64_decode
            api_key = base64_decode(api_key)
        except TypeError:
            pass

        # TODO parse better, with checks and all, this is shaky
        api_key_parts = api_key.split(':')
        username = api_key_parts[0]
        password = api_key_parts[1]

        authentication_provider = \
            AuthenticationManager().get_authentication_provider()

        try:
            user = authentication_provider.authenticate(username,
                                                        password,
                                                        self.security.datastore,
                                                        self.security.pwd_context)
        except Exception:
            abort(401)

        return user

    @staticmethod
    def _unauthorized_handler(self):
        abort(401)