import traceback
import os
import time
import yaml
from io import StringIO

from flask import Flask, jsonify, Blueprint, current_app
from flask_security import Security
import pydantic
from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm.session import close_all_sessions
from sqlalchemy.pool import Pool
from werkzeug.exceptions import InternalServerError
from pydantic import ValidationError


from manager_rest import (config,
                          premium_enabled,
                          manager_exceptions)
from manager_rest import persistent_storage
from manager_rest.storage import db, user_datastore, models
from manager_rest.security.user_handler import user_loader
from manager_rest.security import audit
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


@event.listens_for(Pool, 'close')
def handle_db_failover(conn, conn_record):
    current_app.update_db_uri()


@app_errors.app_errorhandler(manager_exceptions.ManagerException)
def manager_exception(error):
    if isinstance(error, manager_exceptions.NoAuthProvided):
        current_app.logger.debug(error)
    else:
        current_app.logger.error(error)
    return error.to_response(), error.status_code, error.additional_headers


@app_errors.app_errorhandler(pydantic.ValidationError)
def validation_error(e):
    return (
        manager_exceptions.BadParametersError(str(e)).to_response(),
        manager_exceptions.BadParametersError.status_code,
    )


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


@app_errors.app_errorhandler(ValidationError)
def _validation_error(e):
    return jsonify(
        message=str(e),
        error_code=manager_exceptions.BadParametersError.error_code,
    ), manager_exceptions.BadParametersError.status_code


def cope_with_db_failover():
    # These two when multiplied together should be over 30 seconds as that's
    # about how long a failover can take in reasonable (not overcommitted)
    # conditions.
    max_attempts = 45
    attempt_delay = 1
    for attempt in range(1, max_attempts + 1):
        try:
            standby = db.session.execute(
                'SELECT pg_is_in_recovery()').fetchall()[0][0]
            if standby:
                # This is a hot standby, we need to fail over
                current_app.logger.warning(
                    'Connection to standby db connected, reconnecting. '
                    'Attempt number %s/%s', attempt, max_attempts)
                current_app.update_db_uri()
                close_all_sessions()
                time.sleep(attempt_delay)
            else:
                break
        except OperationalError as err:
            current_app.logger.warning(
                'Database reconnection occurred. This is expected to happen '
                'when there has been a recent failover or DB proxy restart. '
                'Attempt number %s/%s. Error was: %s',
                attempt, max_attempts, err,
            )
            db.session.rollback()


def query_service_settings():
    """Check for when was the config updated, and if needed, reload it.

    This makes sure that config updates will (eventually) be propagated
    to all workers, and that every worker always has the most recent
    config/permissions settings available.
    """
    last_updated_subquery = (
        db.session.query(models.Role.updated_at.label('updated_at'))
        .union_all(
            db.session.query(models.Config.updated_at.label('updated_at'))
        ).subquery()
    )
    db_config_last_updated = db.session.query(
        db.func.max(last_updated_subquery.c.updated_at)
    ).scalar()
    current_app.logger.debug('Last updated locally: %s, in db: %s',
                             config.instance.last_updated,
                             db_config_last_updated)
    if db_config_last_updated is not None and (
            config.instance.last_updated is None or
            db_config_last_updated > config.instance.last_updated):
        current_app.logger.warning('Config has changed - reloading')
        config.instance.load_from_db()
        current_app.logger.setLevel(config.instance.rest_service_log_level)


def init_storage_handler():
    """Set up a storage handler used by upload_manager."""
    if 'storage_handler' not in current_app.extensions:
        current_app.extensions['storage_handler'] = \
            persistent_storage.init_storage_handler(config.instance)


class CloudifyFlaskApp(Flask):
    def __init__(self, load_config=True):
        _detect_debug_environment()
        super(CloudifyFlaskApp, self).__init__(__name__)
        with self.app_context():
            if load_config:
                config.instance.load_configuration()
            else:
                config.instance.can_load_from_db = False
            self._set_sql_alchemy()

        # This must be the first before_request, otherwise db access may break
        # after db failovers
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
        self.before_request(query_service_settings)
        self.before_request(init_storage_handler)
        self.before_request(maintenance_mode_handler)
        self.after_request(log_response)
        self.before_request(audit.reset)
        self.after_request(audit.extend_headers)
        self._set_flask_security()

        with self.app_context():
            roles = config.instance.authorization_roles
            if roles:
                for role in roles:
                    user_datastore.find_or_create_role(name=role['name'])
                user_datastore.commit()

        setup_resources(self)
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

    def update_db_uri(self):
        current = self.config.get('SQLALCHEMY_DATABASE_URI')
        self.config['SQLALCHEMY_DATABASE_URI'] = config.instance.db_url
        if current != self.config['SQLALCHEMY_DATABASE_URI']:
            new_host = self.config['SQLALCHEMY_DATABASE_URI']\
                .split('@')[1]\
                .split('/')[0]
            if current:
                self.logger.warning('DB leader changed: %s', new_host)
            else:
                self.logger.info('DB leader set to %s', new_host)

    def _set_sql_alchemy(self):
        """
        Set SQLAlchemy specific configurations, init the db object and create
        the tables if necessary
        """
        self.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_size': 1,
            'client_encoding': 'utf-8',
        }
        self.update_db_uri()
        self.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(self)  # Prepare the app for use with flask-sqlalchemy


app: CloudifyFlaskApp


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
