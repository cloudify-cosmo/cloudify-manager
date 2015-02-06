import datetime
from collections import namedtuple
from functools import wraps

# TODO decide which of the below 'abort' is better?
# TODO the werkzeug abort is referred to by flask's
# from werkzeug.exceptions import abort
from flask import abort, request, globals as flask_globals

from security.datastores.datastore_manager import DatastoreManager
from security.authentication_providers.authentication_manager \
    import AuthenticationManager

#: Default name of the auth header (``Authorization``)
AUTH_HEADER_NAME = 'Authorization'

unauthorized_user_handler = None
datastore = None


def load_security_config():
    # TODO read all this from a configuration file
    # TODO read only once
    flask_globals.current_app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(seconds=30)
    flask_globals.current_app.config['SECRET_KEY'] = 'the quick brown fox jumps over the lazy dog'
    global datastore
    datastore = DatastoreManager().get_datastore_driver(flask_globals.current_app)


def is_authenticated():
    # TODO is there a nicer way to do it?
    if hasattr(flask_globals._request_ctx_stack.top, 'user'):
        return True
    else:
        return False


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
                    unauthorized_user_handler(Exception(401, 'UNAUTHORIZED'))
                else:
                    abort(401)
        except Exception as e:
            # TODO raise 'failed to authenticate' or something..
            if unauthorized_user_handler:
                unauthorized_user_handler(e)
            else:
                abort(401)
    return wrapper


def get_auth_info_from_request(auth_header_name):
    # TODO remember this is configurable - document
    auth_header = request.headers.get(auth_header_name)
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
    user_id = api_key_parts[0]
    password = api_key_parts[1]
    token = None

    auth_info = namedtuple('auth_info_type',
                           ['user_id', 'password', 'token'])

    return auth_info(user_id, password, token)


def authenticate_request_user():
    # TODO call 'load_security_context" once, after app context is available
    load_security_config()
    auth_header_name = flask_globals.current_app.config.get('AUTH_HEADER_NAME', AUTH_HEADER_NAME)
    # auth_header_name = self.app.config.get('AUTH_HEADER_NAME', AUTH_HEADER_NAME)
    auth_info = get_auth_info_from_request(auth_header_name)

    # TODO should use find or get here?
    user = datastore.get_user(auth_info.user_id)
    # user = User.query.filter_by(api_key=api_key).first()
    try:
        if authenticate_user(user, auth_info):
            # TODO is the place to keep the loaded user? flask login does so.
            # TODO verify this is nullified for new requests
            flask_globals._request_ctx_stack.top.user = user
        else:
            if unauthorized_user_handler:
                unauthorized_user_handler()
            else:
                abort(401)
    except Exception as e:
        if unauthorized_user_handler:
            unauthorized_user_handler(e)
        else:
            abort(401)


def authenticate_user(user, auth_info):
    authentication_provider = \
        AuthenticationManager().get_authentication_provider()

    return authentication_provider.authenticate(user, auth_info)