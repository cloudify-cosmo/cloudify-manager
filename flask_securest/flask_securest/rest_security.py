from collections import namedtuple
from functools import wraps
from flask import _app_ctx_stack, current_app


# TODO decide which of the below 'abort' is better?
# TODO the werkzeug abort is referred to by flask's
# from werkzeug.exceptions import abort
from flask import abort, request, _request_ctx_stack
from flask.ext.securest.models import AnonymousUser

from flask.ext.securest.userstores.userstore_manager import UserstoreManager
from flask.ext.securest.authentication_providers.authentication_manager \
    import AuthenticationManager

#: Default name of the auth header (``Authorization``)
AUTH_HEADER_NAME = 'Authorization'
AUTH_TOKEN_HEADER_NAME = 'Authentication-Token'

SECUREST_SECRET_KEY = 'SECUREST_SECRET_KEY'
SECUREST_AUTHENTICATION_METHODS = 'SECUREST_AUTHENTICATION_METHODS'
SECUREST_USERSTORE_DRIVER = 'SECUREST_USERSTORE_DRIVER'
SECUREST_USERSTORE_IDENTIFIER_ATTRIBUTE = \
    'SECUREST_USERSTORE_IDENTIFIER_ATTRIBUTE'

# TODO is this required?
# PERMANENT_SESSION_LIFETIME = datetime.timedelta(seconds=30)
default_config = {
    'SECUREST_SECRET_KEY': 'SECUREST_SECRET_KEY',
    'SECUREST_AUTHENTICATION_METHODS': [
        'flask_securest.authentication_providers.password:'
        'PasswordAuthenticator'
    ],
    'SECUREST_USERSTORE_DRIVER': 'flask_securest.userstores.file:'
                                 'FileUserstore',
    'SECUREST_USERSTORE_IDENTIFIER_ATTRIBUTE': 'username',
}


class SecuREST(object):

    def __init__(self, app=None):
        self.app = app

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        # setting default security settings
        for key in default_config.keys():
            app.config.setdefault(key, default_config[key])

        app.teardown_appcontext(self.teardown)
        app.before_first_request(self.init_providers)
        app.before_request(self.authenticate_request_if_needed)
        app.after_request(self.filter_response_if_needed)

    def teardown(self, exception):
        # TODO log the exception if not None?
        top = _app_ctx_stack.top
        if hasattr(top, 'ssl_context'):
            self.unset_ssl_context()

    def set_ssl_context(self):
        pass

    def unset_ssl_context(self):
        pass

    def unauthorized_user_handler(self, unauthorized_user_handler):
        self.app.securest_unauthorized_user_handler = unauthorized_user_handler

    @staticmethod
    def init_providers():
        current_app.securest_userstore = \
            UserstoreManager(current_app).get_userstore_driver()
        current_app.securest_authentication_manager = \
            AuthenticationManager(current_app)

    @staticmethod
    def authenticate_request_if_needed():
        # TODO check if the resource is secured or not,
        # maybe through the api/resources, with something that gets the
        # resource for the "request.path" from the api and checks if it's
        # an instance of SecuredResource.
        # TODO otherwise use a mapping list like in Spring-Security
        if True:
            authenticate_request()

    def filter_response_if_needed(self, response=None):
        return response


def is_authenticated():
    authenticated = False
    # TODO is there a nicer way to do it?
    request_ctx = _request_ctx_stack.top
    if hasattr(request_ctx, 'user') and \
            not isinstance(request_ctx.user, AnonymousUser):
        authenticated = True

    return authenticated


def filter_results(results):
    return results


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            if is_authenticated():
                result = func(*args, **kwargs)
                return filter_results(result)
            else:
                handle_user_unauth()
        except Exception:
            # TODO decide if this mean user is unauthorized or a
            # TODO different exception ('authentication check failed')
            # TODO log this
            handle_user_unauth()
    return wrapper


def handle_user_unauth():
    if hasattr(current_app, 'securest_unauthorized_user_handler') \
            and current_app.securest_unauthorized_user_handler:
        current_app.securest_unauthorized_user_handler()
    else:
        # TODO verify this ends up in resources.abort_error
        abort(401)


def get_auth_info_from_request():
    user_id = None
    password = None
    token = None

    # TODO remember this is configurable - document
    app_config = current_app.config

    auth_header_name = app_config.get('AUTH_HEADER_NAME', AUTH_HEADER_NAME)
    auth_header = request.headers.get(auth_header_name) \
        if auth_header_name else None

    auth_token_header_name = app_config.get('AUTH_TOKEN_HEADER_NAME',
                                            AUTH_TOKEN_HEADER_NAME)
    if auth_token_header_name:
        token = request.headers.get(auth_token_header_name) \

    if not auth_header and not token:
        raise Exception('Failed to get authentication information from '
                        'request, headers not found: {0}, {1}'
                        .format(auth_header_name, auth_token_header_name))

    if auth_header:
        auth_header = auth_header.replace('Basic ', '', 1)
        try:
            from itsdangerous import base64_decode
            api_key = base64_decode(auth_header)
            # TODO parse better, with checks and all, this is shaky
        except TypeError:
            pass
        else:
            api_key_parts = api_key.split(':')
            user_id = api_key_parts[0]
            password = api_key_parts[1]

    auth_info = namedtuple('auth_info_type',
                           ['user_id', 'password', 'token'])

    return auth_info(user_id, password, token)


def authenticate_request():
    auth_info = get_auth_info_from_request()

    try:
        user = current_app.securest_authentication_manager.\
            authenticate(auth_info)
    except Exception:
        user = AnonymousUser()

    # TODO is the place to keep the loaded user? flask login does so.
    _request_ctx_stack.top.user = user
