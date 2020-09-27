#########
# Copyright (c) 2013-2019 Cloudify Platform Ltd. All rights reserved
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

import traceback
import os
import yaml
from contextlib import contextmanager

from flask_restful import Api
from flask import Flask, jsonify, Blueprint, current_app
from flask_security import Security
from sqlalchemy.exc import OperationalError
from werkzeug.exceptions import InternalServerError

from cloudify._compat import StringIO

from manager_rest import config, premium_enabled, manager_exceptions
from manager_rest.storage import db, user_datastore
from manager_rest.security.user_handler import user_loader
from manager_rest.maintenance import maintenance_mode_handler
from manager_rest.rest.endpoint_mapper import setup_resources
from manager_rest.flask_utils import set_flask_security_config
from manager_rest.manager_exceptions import INTERNAL_SERVER_ERROR_CODE
from manager_rest.app_logging import (setup_logger,
                                      log_request,
                                      log_response)

if premium_enabled:
    from cloudify_premium.authentication.extended_auth_handler \
        import configure_auth
    from cloudify_premium.license.license import LicenseHandler

SQL_DIALECT = 'postgresql'


app_errors = Blueprint('app_errors', __name__)


@app_errors.app_errorhandler(manager_exceptions.ManagerException)
def manager_exception(error):
    if isinstance(error, manager_exceptions.NoAuthProvided):
        current_app.logger.debug(error)
    else:
        current_app.logger.error(error)
    return jsonify(
        message=str(error),
        error_code=error.error_code,
        # useless, but v1 and v2 api clients require server_traceback
        # remove this after dropping v1 and v2 api clients
        server_traceback=None
    ), error.status_code


@app_errors.app_errorhandler(InternalServerError)
def internal_error(e):
    s_traceback = StringIO()
    traceback.print_exc(file=s_traceback)

    return jsonify(
        message="Internal error occurred in manager REST server - {0}: {1}"
                .format(type(e).__name__, e),
        error_code=INTERNAL_SERVER_ERROR_CODE,
        server_traceback=s_traceback.getvalue()
    ), 500


def cope_with_db_failover():
    try:
        db.engine.execute('SELECT 1')
    except OperationalError as err:
        current_app.logger.warning(
            'Database reconnection occurred. This is expected to happen when '
            'there has been a recent failover or DB proxy restart. '
            'Error was: {err}'.format(err=err)
        )


class CloudifyFlaskApp(Flask):
    def __init__(self, load_config=True):
        _detect_debug_environment()
        super(CloudifyFlaskApp, self).__init__(__name__)
        if load_config:
            config.instance.load_configuration()
        self._set_sql_alchemy()

        # This must be the first before_request, otherwise db access may break
        # after db failovers or db proxy restarts
        self.before_request(cope_with_db_failover)

        # These two need to be called after the configuration was loaded
        if config.instance.rest_service_log_path:
            setup_logger(self.logger)
        if premium_enabled and config.instance.file_server_root:
            self.external_auth = configure_auth(self.logger)
            self.before_request(LicenseHandler.check_license_expiration_date)
        else:
            self.external_auth = None

        self.before_request(log_request)
        self.before_request(maintenance_mode_handler)
        self.after_request(log_response)
        self._set_flask_security()

        with self.app_context():
            roles = config.instance.authorization_roles
            if roles:
                for role in roles:
                    user_datastore.find_or_create_role(name=role['name'])
                user_datastore.commit()

        with self._prevent_flask_restful_error_handling():
            setup_resources(Api(self))
        self.register_blueprint(app_errors)

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
        """
        Set SQLAlchemy specific configurations, init the db object and create
        the tables if necessary
        """
        self.config['SQLALCHEMY_POOL_SIZE'] = 1
        self.config['SQLALCHEMY_DATABASE_URI'] = config.instance.db_url
        self.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(self)  # Prepare the app for use with flask-sqlalchemy

    @contextmanager
    def _prevent_flask_restful_error_handling(self):
        """Add flask-restful under this, to avoid installing its errorhandlers

        Flask-restful's errorhandlers are both not flexible enough, and too
        complex. We want to simply use flask's error handling mechanism,
        so this will make sure that flask-restful's are overridden with the
        default ones.
        """
        orig_handle_exc = self.handle_exception
        orig_handle_user_exc = self.handle_user_exception
        yield
        self.handle_exception = orig_handle_exc
        self.handle_user_exception = orig_handle_user_exc


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
    except BaseException as e:
        raise Exception('Failed to connect to debug server, {0}: {1}'.
                        format(type(e).__name__, str(e)))
