from collections import namedtuple
from functools import wraps
from flask import _app_ctx_stack, current_app
import utils
from authentication_providers.abstract_authentication_provider \
    import AbstractAuthenticationProvider


# TODO decide which of the below 'abort' is better?
# TODO the werkzeug abort is referred to by flask's
# from werkzeug.exceptions import abort
from flask import abort, request, _request_ctx_stack
from flask.ext.securest.models import AnonymousUser

from flask.ext.securest.userstores.userstore_manager import UserstoreManager


#: Default name of the auth header (``Authorization``)
AUTH_HEADER_NAME = 'Authorization'
AUTH_TOKEN_HEADER_NAME = 'Authentication-Token'

SECUREST_SECRET_KEY = 'SECUREST_SECRET_KEY'
SECUREST_USERSTORE_DRIVER = 'SECUREST_USERSTORE_DRIVER'
SECUREST_USERSTORE_IDENTIFIER_ATTRIBUTE = \
    'SECUREST_USERSTORE_IDENTIFIER_ATTRIBUTE'

# TODO is this required?
# PERMANENT_SESSION_LIFETIME = datetime.timedelta(seconds=30)
default_config = {
    'SECUREST_SECRET_KEY': 'SECUREST_SECRET_KEY',
    'SECUREST_USERSTORE_DRIVER': 'flask_securest.userstores.file:'
                                 'FileUserstore',
    'SECUREST_USERSTORE_IDENTIFIER_ATTRIBUTE': 'username',
}


secured_resources = []


class SecuREST(object):

    def __init__(self, app=None):
        self.app = app
        self.app.securest_unauthorized_user_handler = None
        self.app.securest_authentication_providers = []

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        # setting default security settings
        for key in default_config.keys():
            app.config.setdefault(key, default_config[key])

        app.teardown_appcontext(self.teardown)
        app.before_first_request(validate_configuration)
        app.before_first_request(init_providers)
        app.before_request(authenticate_request_if_needed)
        app.after_request(filter_response_if_needed)

    def teardown(self, exception):
        # TODO log the exception if not None/empty?
        top = _app_ctx_stack.top
        if hasattr(top, 'ssl_context'):
            self.unset_ssl_context()

    def set_ssl_context(self):
        pass

    def unset_ssl_context(self):
        pass

    def unauthorized_user_handler(self, unauthorized_user_handler):
        self.app.securest_unauthorized_user_handler = unauthorized_user_handler

    def authentication_provider(self, provider):
        """
        Registers the given authentication method.
        :param authentication_method: appends the given authentication
        provider to the list of providers
        Note: Pay attention to the order of the registered providers.
        authentication well attempted on each of the registered providers,
        according to their registration order, until successful.
        """
        print 'validating auth provider: ', provider
        if not isinstance(provider, AbstractAuthenticationProvider):
            raise Exception('authentication provider "{0}" must inherit "{1}"'
                            .format(utils.get_instance_class_fqn(provider),
                                    utils.get_class_fqn(
                                        AbstractAuthenticationProvider)))

        provider.init(self.app)
        self.app.securest_authentication_providers.append(provider)


def init_providers():
    current_app.securest_userstore = \
        UserstoreManager(current_app).get_userstore_driver()


def validate_configuration():
    if not current_app.securest_authentication_providers:
        raise Exception('authentication methods not set')


def authenticate_request_if_needed():
    # TODO check if the resource is secured or not,

    if True:
        from flask import globals
        g_request = globals.request
        print '----- authenticating request...'
        print '----- g_request.endpoint', g_request.endpoint
        print '----- secured_resources: ', secured_resources
        endpoint = g_request.endpoint
        view_func = current_app.view_functions.get(endpoint)

        if not view_func:
            raise Exception('endpoint {0} is not mapped to a REST resource'
                            .format(endpoint))

        global secured_resources
        if not hasattr(view_func, 'view_class'):
            print '----- view_class attribute not found on view func {0}'\
                .format(view_func)
        else:
            view_class = getattr(view_func, 'view_class')
            if utils.get_class_fqn(view_class) in secured_resources:
                print '----- accessing secured resource {0}, attempting ' \
                      'authentication'.format(utils.get_class_fqn(view_class))
                # accessing a secured resource, must authenticate
                authenticate_request()
            else:
                print '----- accessing open resource {0}, not authenticating'\
                    .format(utils.get_class_fqn(view_class))


def secure(resource_class):
    print '----- adding resource to secured_resources: ', \
        utils.get_class_fqn(resource_class)
    global secured_resources
    secured_resources.append(utils.get_class_fqn(resource_class))

    return resource_class


def filter_response_if_needed(response=None):
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
                handle_unauthorized_user()
        except Exception:
            # TODO decide if this mean user is unauthorized or a
            # TODO different exception ('authentication check failed')
            # TODO log this
            handle_unauthorized_user()
    return wrapper


def handle_unauthorized_user():
    if current_app.securest_unauthorized_user_handler:
        current_app.securest_unauthorized_user_handler()
    else:
        # TODO verify this ends up in resources.abort_error
        # TODO do this? from flask_restful import abort
        abort(401)


def get_auth_info_from_request():
    user_id = None
    password = None
    token = None

    # TODO remember this is configurable - document
    app_config = current_app.config

    auth_header_name = app_config.get('AUTH_HEADER_NAME', AUTH_HEADER_NAME)
    if auth_header_name:
        auth_header = request.headers.get(auth_header_name)

    auth_token_header_name = app_config.get('AUTH_TOKEN_HEADER_NAME',
                                            AUTH_TOKEN_HEADER_NAME)
    if auth_token_header_name:
        token = request.headers.get(auth_token_header_name)

    if not auth_header and not token:
        raise Exception('Failed to get authentication information from '
                        'request, headers not found: {0}, {1}'
                        .format(auth_header_name, auth_token_header_name))

    if auth_header:
        auth_header = auth_header.replace('Basic ', '', 1)
        print '----- GOT AUTH_HEADER: ', auth_header
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
        user = authenticate(current_app.securest_authentication_providers,
                            auth_info)
    except Exception:
        user = AnonymousUser()

    # TODO is the place to keep the loaded user? flask login does so.
    _request_ctx_stack.top.user = user


def authenticate(authentication_providers, auth_info):
    user = None
    for auth_provider in authentication_providers:
        try:
            print '***** userstore is: ', current_app.securest_userstore
            user = auth_provider.authenticate(auth_info,
                                              current_app.securest_userstore)
            break
        except Exception as e:
            #  TODO use the caught exception?
            print '***** caught authentication exception: ', e.message
            continue  # try the next authentication method until successful

    if not user:
        raise Exception('Unauthorized')

    return user
