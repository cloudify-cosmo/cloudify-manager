#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

import StringIO
import functools
import traceback
import os
import yaml

import opentracing
from flask_restful import Api
from flask_security import Security
from flask import Flask, jsonify, Blueprint
from flask import _request_ctx_stack as stack
from opentracing_instrumentation.request_context import span_in_context

from manager_rest import config, premium_enabled
from manager_rest.storage import db, user_datastore
from manager_rest.security.user_handler import user_loader
from manager_rest.maintenance import maintenance_mode_handler
from manager_rest.rest.endpoint_mapper import setup_resources
from manager_rest.flask_utils import set_flask_security_config
from manager_rest.manager_exceptions import INTERNAL_SERVER_ERROR_CODE
from manager_rest.app_logging import setup_logger, log_request, log_response

if premium_enabled:
    from cloudify_premium import configure_auth

SQL_DIALECT = 'postgresql'


app_errors = Blueprint('app_errors', __name__)


@app_errors.app_errorhandler(500)
def internal_error(e):
    s_traceback = StringIO.StringIO()
    traceback.print_exc(file=s_traceback)

    response = jsonify(
        {"message":
         "Internal error occurred in manager REST server - {0}: {1}"
         .format(type(e).__name__, str(e)),
         "error_code": INTERNAL_SERVER_ERROR_CODE,
         "server_traceback": s_traceback.getvalue()})
    response.status_code = 500
    return response


class CloudifyFlaskApp(Flask):
    def __init__(self, load_config=True):
        _detect_debug_environment()
        super(CloudifyFlaskApp, self).__init__(__name__)
        if load_config:
            config.instance.load_configuration()

        # These two need to be called after the configuration was loaded
        setup_logger(self.logger)
        if premium_enabled:
            self.external_auth = configure_auth(self.logger)
        else:
            self.external_auth = None

        self.before_request(log_request)
        self.before_request(maintenance_mode_handler)
        self.after_request(log_response)

        self._set_exception_handlers()
        self._set_sql_alchemy()
        self._set_flask_security()

        with self.app_context():
            roles = config.instance.authorization_roles
            if roles:
                for role in roles:
                    user_datastore.find_or_create_role(name=role['name'])
                user_datastore.commit()

        setup_resources(Api(self))
        self.register_blueprint(app_errors)

        self.tracer = None
        # Don't attempt tracer initiation when tracing isn't enabled
        if config.instance.enable_tracing:
            # Jaeger initialization while initializing this class causes a hang
            # due to tornado IOLoop initialization. Therefore, the
            # initialization is scheduled to be executed before the first
            # request, before there's anything to trace.
            self.before_first_request(self._init_jaeger_tracer)

    def _init_jaeger_tracer(self):
        """Initializes the Jaeger tracer.
        """
        self.logger.info("Initializing the Jaeger tracer...")
        if not config.instance.tracing_endpoint_ip:
            self.logger.error("Did not find 'tracing_endpoint_ip' in the "
                              "config. Aborting tracer initialization...")
            return
        self.tracer = config.instance.tracer_config.initialize_tracer()
        self.logger.debug("Done initializing Jaeger tracer.")

    def _set_flask_security(self):
        """Set Flask-Security specific configurations and init the extension
        """
        set_flask_security_config(self)
        Security(app=self, datastore=user_datastore)

        # Get the login manager and set our own callback to be the user getter
        login_manager = self.extensions['security'].login_manager
        login_manager.request_loader(user_loader)

        self.token_serializer = self.extensions[
            'security'].remember_token_serializer

    def _set_sql_alchemy(self):
        """Set SQLAlchemy specific configurations, init the db object and create
         the tables if necessary
        """
        cfy_config = config.instance

        self.config['SQLALCHEMY_DATABASE_URI'] = \
            '{0}://{1}:{2}@{3}/{4}'.format(
                SQL_DIALECT,
                cfy_config.postgresql_username,
                cfy_config.postgresql_password,
                cfy_config.postgresql_host,
                cfy_config.postgresql_db_name
        )
        self.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(self)  # Prepare the app for use with flask-sqlalchemy

    def _set_exception_handlers(self):
        """Set custom exception handlers for the Flask app
        """
        # saving flask's original error handlers
        flask_handle_exception = self.handle_exception
        flask_handle_user_exception = self.handle_user_exception

        # saving flask-restful's error handlers
        flask_restful_handle_exception = self.handle_exception
        flask_restful_handle_user_exception = self.handle_user_exception

        # setting it so that <500 codes use flask-restful's error handlers,
        # while 500+ codes use original flask's error handlers (for which we
        # register an error handler on somewhere else in this module)
        def handle_exception(flask_method, flask_restful_method, e):
            code = getattr(e, 'code', 500)
            if code >= 500:
                return flask_method(e)
            else:
                return flask_restful_method(e)

        self.handle_exception = functools.partial(
            handle_exception,
            flask_handle_exception,
            flask_restful_handle_exception)
        self.handle_user_exception = functools.partial(
            handle_exception,
            flask_handle_user_exception,
            flask_restful_handle_user_exception)
        self.config['ERROR_404_HELP'] = False

    def dispatch_request(self):
        """Wraps up the super 'dispatch_request' func to enable easier tracing.
        The super function does the request dispatching. Matches the URL and
        returns the return value of the view or error handler.
        This function creates a new span and injects it to the current thread
        local for other inner executions to fetch.
        """
        if not self.tracer:
            return super(CloudifyFlaskApp, self).dispatch_request()

        request = stack.top.request
        operation_name = '{} ({})'.format(request.endpoint, request.method)
        headers = {}
        for k, v in request.headers:
            headers[k.lower()] = v
        kw = {'operation_name': operation_name}
        try:
            span_ctx = self.tracer.extract(
                opentracing.Format.HTTP_HEADERS, headers)
            kw['child_of'] = span_ctx
        except opentracing.UnsupportedFormatException as e:
            kw['tags'] = {"Extract failed": str(e)}

        with self.tracer.start_span(**kw) as span:
            with span_in_context(span):
                return super(CloudifyFlaskApp, self).dispatch_request()


def reset_app(configuration=None):
    global app
    config.reset(configuration)
    app = CloudifyFlaskApp(False)


def _detect_debug_environment():
    """
    Detect whether server is running in a debug environment
    if so, connect to debug server at a port stored in env[DEBUG_REST_SERVICE]
    """
    try:
        docl_debug_path = os.environ.get('DEBUG_CONFIG')
        if docl_debug_path and os.path.isfile(docl_debug_path):
            with open(docl_debug_path, 'r') as docl_debug_file:
                debug_config = yaml.safe_load(docl_debug_file)
            if debug_config.get('is_debug_on'):
                import pydevd
                pydevd.settrace(
                    debug_config['host'], port=53100, stdoutToServer=True,
                    stderrToServer=True, suspend=False)
    except BaseException, e:
        raise Exception('Failed to connect to debug server, {0}: {1}'.
                        format(type(e).__name__, str(e)))
