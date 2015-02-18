import datetime
from collections import namedtuple
from functools import wraps

# TODO decide which of the below 'abort' is better?
# TODO the werkzeug abort is referred to by flask's
# from werkzeug.exceptions import abort
from flask import abort, request, globals as flask_globals
from models import AnonymousUser

from security.userstores.userstore_manager import UserstoreManager
from security.authentication_providers.authentication_manager \
    import AuthenticationManager

#: Default name of the auth header (``Authorization``)
AUTH_HEADER_NAME = 'Authorization'
AUTH_TOKEN_HEADER_NAME = 'Authentication-Token'

unauthorized_user_handler = None
userstore = None


def load_security_config():
    # TODO read all this from a configuration file
    # TODO read only once
    flask_globals.current_app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(seconds=30)
    flask_globals.current_app.config['SECRET_KEY'] = 'the quick brown fox jumps over the lazy dog'
    # The order of authentication methods is important!
    flask_globals.current_app.config['AUTHENTICATION_METHODS'] = \
        ['security.authentication_providers.password:PasswordAuthenticator',
         'security.authentication_providers.token:TokenAuthenticator']
    global userstore
    userstore = UserstoreManager().get_userstore_driver(flask_globals.current_app)


def is_authenticated():
    authenticated = False
    # TODO is there a nicer way to do it?
    request_ctx = flask_globals._request_ctx_stack.top
    if hasattr(request_ctx, 'user') and \
            not isinstance(request_ctx.user, AnonymousUser):
        authenticated = True

    return authenticated


def filter_results(results):
    return results


def set_unauthorized_user_handler(unauthorized_handler):
    global unauthorized_user_handler
    unauthorized_user_handler = unauthorized_handler


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            if is_authenticated():
                result = func(*args, **kwargs)
                return filter_results(result)
            else:
                if unauthorized_user_handler:
                    unauthorized_user_handler()
                else:
                    # TODO verify this ends up in resources.abort_error
                    abort(401)
        except Exception as e:
            # TODO decide if this mean user is unauthorized or a different exception ('authentication check failed')
            if unauthorized_user_handler:
                unauthorized_user_handler(e)
            else:
                # TODO verify this ends up in resources.abort_error
                abort(401)
    return wrapper


def get_auth_info_from_request():
    user_id = None
    password = None
    token = None

    # TODO remember this is configurable - document
    app_config = flask_globals.current_app.config

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
    # TODO call 'load_security_context" once, after app context is available
    load_security_config()

    auth_info = get_auth_info_from_request()
    auth_manager = AuthenticationManager(flask_globals.current_app)
    try:
        user = auth_manager.authenticate(auth_info, userstore)
    except Exception:
        user = AnonymousUser()

    # TODO is the place to keep the loaded user? flask login does so.
    flask_globals._request_ctx_stack.top.user = user
