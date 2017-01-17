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

from flask_restful import Api
from flask import Flask, jsonify
from flask_security import Security

from manager_rest import config
from manager_rest.storage import db, user_datastore
from manager_rest.flask_utils import set_flask_security_config
from manager_rest.security.user_handler import user_loader
from manager_rest.maintenance import maintenance_mode_handler
from manager_rest.rest.endpoint_mapper import setup_resources
from manager_rest.app_logging import setup_logger, log_request, log_response
from manager_rest.manager_exceptions import INTERNAL_SERVER_ERROR_CODE

try:
    from cloudify_premium import configure_ldap
    premium_enabled = True
except ImportError:
    configure_ldap = None
    premium_enabled = False

SQL_DIALECT = 'postgresql'


class CloudifyFlaskApp(Flask):
    def __init__(self, load_config=True):
        _detect_debug_environment()
        super(CloudifyFlaskApp, self).__init__(__name__)
        if load_config:
            config.instance.load_configuration()

        # These two need to be called after the configuration was loaded
        setup_logger(self.logger)
        self.premium_enabled = premium_enabled
        if self.premium_enabled:
            self.ldap = configure_ldap()
        else:
            self.ldap = None

        self.before_request(log_request)
        self.before_request(maintenance_mode_handler)
        self.after_request(log_response)

        self._set_exception_handlers()
        self._set_sql_alchemy()
        self._set_flask_security()

        setup_resources(Api(self))

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
        with self.app_context():
            db.init_app(self)  # Set the app to use the SQLAlchemy DB

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


app = CloudifyFlaskApp()


@app.errorhandler(500)
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
