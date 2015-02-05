import datetime
import StringIO
import traceback
from functools import wraps

# TODO decide which of the below 'abort' is better,
# TODO the werkzeug is referred to by flask
from werkzeug.exceptions import abort
# from flask import abort
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

        self.security.login_manager.header_loader(self._header_loader)
        self.security.login_manager.unauthorized_handler(self._unauthorized_handler)

    # TODO can be called on a wsgi hook (_on_before_request)
    # TODO or by
    def _header_loader(self, auth_header):
        user = None

        if not auth_header:
            raise Exception('Authorization header not found on request')

        auth_header = auth_header.replace('Basic ', '', 1)
        try:
            from itsdangerous import base64_decode
            api_key = base64_decode(auth_header)
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
    @property
    def unauthorized_handler(self, unauthorized):
        unauthorized()

    def login_required(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                if is_authenticated():
                    result = func(*args, **kwargs)
                    return filter_results(result)
                else:
                    if self.unauthorized_handler:
                        self.unauthorized_handler()
                    else:
                        abort(401)
            except Exception as e:
                self.abort_error(e)
        return wrapper
