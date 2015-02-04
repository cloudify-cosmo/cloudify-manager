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

__author__ = 'dan'

import base64
import logging
import functools
import traceback
import os
import yaml
from logging.handlers import RotatingFileHandler
import datetime

from flask import (
    Flask,
    jsonify,
    request,
    abort
)
from flask_restful import Api
from flask.ext.mongoengine import MongoEngine
from flask.ext.security import Security, MongoEngineUserDatastore, UserMixin, \
    RoleMixin

from manager_rest import config
# from manager_rest import blueprints_manager
from manager_rest import storage_manager
from manager_rest import resources
from manager_rest import manager_exceptions
from util import setup_logger


# app factory
def setup_app():
    app = Flask(__name__)

    # setting up the app logger with a rotating file handler, in addition to
    #  the built-in flask logger which can be helpful in debug mode.


    additional_log_handlers = [
        RotatingFileHandler(
            # config.instance().rest_service_log_path,
            '/tmp/tmplog',
            maxBytes=1024*1024*100,
            backupCount=20)
    ]

    app.logger_name = 'manager-rest'
    setup_logger(logger_name=app.logger.name,
                 logger_level=logging.DEBUG,
                 handlers=additional_log_handlers,
                 remove_existing_handlers=False)

    app.before_request(log_request)
    app.after_request(log_response)

    # saving flask's original error handlers
    flask_handle_exception = app.handle_exception
    flask_handle_user_exception = app.handle_user_exception

    api = Api(app)

    # saving flask-restful's error handlers
    flask_restful_handle_exception = app.handle_exception
    flask_restful_handle_user_exception = app.handle_user_exception

    # setting it so that <500 codes use flask-restful's error handlers,
    # while 500+ codes use original flask's error handlers (for which we
    # register an error handler on somewhere else in this module)
    def handle_exception(flask_method, flask_restful_method, e):
        code = getattr(e, 'code', 500)
        if code >= 500:
            return flask_method(e)
        else:
            return flask_restful_method(e)

    app.handle_exception = functools.partial(
        handle_exception,
        flask_handle_exception,
        flask_restful_handle_exception)
    app.handle_user_exception = functools.partial(
        handle_exception,
        flask_handle_user_exception,
        flask_restful_handle_user_exception)

    resources.setup_resources(api)

    app.config['MONGODB_DB'] = 'mydatabase'
    app.config['MONGODB_HOST'] = 'localhost'
    app.config['MONGODB_PORT'] = 27017

    app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(seconds=30)
    app.config['SECRET_KEY'] = 'the quick brown fox jumps over the lazy dog'
    # app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
    # app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True

    db = MongoEngine(app)

    class Role(db.Document, RoleMixin):
        name = db.StringField(max_length=80, unique=True)
        description = db.StringField(max_length=255)

    class User(db.Document, UserMixin):  # for SQLAlchemy this is db.Model

        email = db.StringField(max_length=255)
        password = db.StringField(max_length=255)   # this password is hashed
        active = db.BooleanField(default=True)
        confirmed_at = db.DateTimeField()
        roles = db.ListField(db.ReferenceField(Role), default=[])

    user_datastore = MongoEngineUserDatastore(db, User, Role)
    security = Security(app, user_datastore)

    def _request_loader(request):
        user = None

        # first, try to login using the api_key url arg
        api_key = request.args.get('api_key')
        if api_key:
            # TODO should use find or get here?
            api_key_parts = api_key.split(':')
            username = api_key_parts[0]
            password = api_key_parts[1]
            user = security.datastore.get_user(username)

        if not user:
            # next, try to login using Basic Auth
            api_key = request.headers.get('Authorization')
            if api_key:
                api_key = api_key.replace('Basic ', '', 1)
                try:
                    from itsdangerous import base64_decode
                    api_key = base64_decode(api_key)
                    # api_key = base64.b64decode(api_key)
                except TypeError:
                    pass
                print '***** HERE, api_key: ', api_key
                api_key_parts = api_key.split(':')
                username = api_key_parts[0]
                password = api_key_parts[1]
                user = security.datastore.get_user(username)
                # user = User.query.filter_by(api_key=api_key).first()

            # validate...
            if not user:
                # self.email.errors.append(get_message('USER_DOES_NOT_EXIST')[0])
                print '***** error: USER_DOES_NOT_EXIST'
                abort(401)
            if not user.password:
                # self.password.errors.append(get_message('PASSWORD_NOT_SET')[0])
                print '***** error: PASSWORD_NOT_SET'
                abort(401)
                # TODO maybe use verify_and_update()?
            if not security.pwd_context.verify(password, getattr(user, 'password')):
                # self.password.errors.append(get_message('INVALID_PASSWORD')[0])
                print '***** error: INVALID_PASSWORD'
                abort(401)
            if not user.is_active():
                # self.email.errors.append(get_message('DISABLED_ACCOUNT')[0])
                print '***** error: DISABLED_ACCOUNT'
                abort(401)

            return user

        # finally, return None if both methods did not login the user
        return None

    security.login_manager.request_loader(_request_loader)

    def _unauthorized_handler():
        abort(401)

    security.login_manager.unauthorized_handler(_unauthorized_handler)

    return app


def log_request():
    # form and args parameters are "multidicts", i.e. values are not
    # flattened and will appear in a list (even if single value)
    form_data = request.form.to_dict(False)
    # args is the parsed query string data
    args_data = request.args.to_dict(False)
    # json data; other data (e.g. binary) is available via request.data,
    #  but is not logged
    json_data = request.json if hasattr(request, 'json') else None

    # content-type and content-length are already included in headers

    app.logger.debug(
        '\nRequest ({0}):\n'
        '\tpath: {1}\n'
        '\thttp method: {2}\n'
        '\tjson data: {3}\n'
        '\tquery string data: {4}\n'
        '\tform data: {5}\n'
        '\theaders: {6}'.format(
            id(request),
            request.path,  # includes "path parameters"
            request.method,
            json_data,
            args_data,
            form_data,
            headers_pretty_print(request.headers)))


def log_response(response):
    # content-type and content-length are already included in headers
    # not logging response.data as volumes are massive

    app.logger.debug(
        '\nResponse ({0}):\n'
        '\tstatus: {1}\n'
        '\theaders: {2}'
        .format(
            id(request),
            response.status,
            headers_pretty_print(response.headers)))
    return response


def headers_pretty_print(headers):
    pp_headers = ''.join(['\t\t{0}: {1}\n'.format(k, v) for k, v in headers])
    return '\n' + pp_headers


def reset_state(configuration=None):
    global app
    # print "resetting state in server"
    config.reset(configuration)
    # this doesn't really do anything
    # blueprints_manager.reset()
    storage_manager.reset()
    app = setup_app()

if 'MANAGER_REST_CONFIG_PATH' in os.environ:
    print '***** os.environ MANAGER_REST_CONFIG_PATH: ', os.environ['MANAGER_REST_CONFIG_PATH']
    with open(os.environ['MANAGER_REST_CONFIG_PATH']) as f:
        yaml_conf = yaml.load(f.read())
    obj_conf = config.instance()
    if 'file_server_root' in yaml_conf:
        obj_conf.file_server_root = yaml_conf['file_server_root']
    if 'file_server_base_uri' in yaml_conf:
        obj_conf.file_server_base_uri = yaml_conf['file_server_base_uri']
    if 'file_server_blueprints_folder' in yaml_conf:
        obj_conf.file_server_blueprints_folder = \
            yaml_conf['file_server_blueprints_folder']
    if 'file_server_uploaded_blueprints_folder' in yaml_conf:
        obj_conf.file_server_uploaded_blueprints_folder = \
            yaml_conf['file_server_uploaded_blueprints_folder']
    if 'file_server_resources_uri' in yaml_conf:
        obj_conf.file_server_resources_uri = \
            yaml_conf['file_server_resources_uri']
    if 'rest_service_log_path' in yaml_conf:
        obj_conf.rest_service_log_path = \
            yaml_conf['rest_service_log_path']
else:
    print '***** no MANAGER_REST_CONFIG_PATH in os.environ'
app = setup_app()


@app.errorhandler(500)
def internal_error(e):

    # app.logger.exception(e)  # gets logged automatically

    s_traceback = StringIO.StringIO()
    traceback.print_exc(file=s_traceback)

    response = jsonify(
        {"message":
         "Internal error occurred in manager REST server - {0}: {1}"
            .format(type(e).__name__, str(e)),
         "error_code": manager_exceptions.INTERNAL_SERVER_ERROR_CODE,
         "server_traceback": s_traceback.getvalue()})
    response.status_code = 500
    return response
