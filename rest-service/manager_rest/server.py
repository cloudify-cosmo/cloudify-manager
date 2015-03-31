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
import logging
import functools
import traceback
import os
import yaml
from logging.handlers import RotatingFileHandler

from flask import (
    Flask,
    jsonify,
    request,
    current_app
)
from flask_restful import Api

from flask_securest.rest_security import SecuREST

from manager_rest import config
from manager_rest import storage_manager
from manager_rest import resources
from manager_rest import manager_exceptions
from manager_rest import utils


# app factory
def setup_app():
    app = Flask(__name__)

    # setting up the app logger with a rotating file handler, in addition to
    #  the built-in flask logger which can be helpful in debug mode.
    additional_log_handlers = [
        RotatingFileHandler(
            config.instance().rest_service_log_path,
            maxBytes=1024 * 1024 * 100,
            backupCount=20)
    ]

    app.logger_name = 'manager-rest'
    utils.setup_logger(logger_name=app.logger.name,
                       logger_level=logging.DEBUG,
                       handlers=additional_log_handlers,
                       remove_existing_handlers=False)

    # secure the app according to manager configuration
    if config.instance().secured_server:
        init_secured_app(app)

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


def init_secured_app(_app):
    cfy_config = config.instance()
    secure_app = SecuREST(_app)
    register_userstore_driver(secure_app, cfy_config.securest_userstore_driver)
    register_authentication_methods(secure_app,
                                    cfy_config.securest_authentication_methods)

    def unauthorized_user_handler():
        utils.abort_error(
            manager_exceptions.UnauthorizedError('user unauthorized'),
            current_app.logger)

    secure_app.unauthorized_user_handler(unauthorized_user_handler)
    if config.instance().security_bypass_port:
        secure_app.request_security_bypass_handler = \
            request_security_bypass_handler


def request_security_bypass_handler(req):
    server_port = req.headers.get('X-Server-Port')
    return str(server_port) == str(config.instance().security_bypass_port)


def register_userstore_driver(secure_app, userstore_driver):
    implementation = userstore_driver.get('implementation')
    properties = userstore_driver.get('properties')
    secure_app.app.logger.debug('registering userstore driver {0}'
                                .format(userstore_driver))
    userstore = utils.get_class_instance(implementation, properties)
    secure_app.set_userstore_driver(userstore)


def register_authentication_methods(secure_app, authentication_providers):
    # Note: the order of registration is important here
    for auth_method in authentication_providers:
        implementation = auth_method.get('implementation')
        properties = auth_method.get('properties')
        secure_app.app.logger.debug('registering authentication method '
                                    '{0}'.format(auth_method))
        auth_provider = utils.get_class_instance(implementation,
                                                 properties)
        secure_app.register_authentication_provider(auth_provider)


def load_configuration():
    obj_conf = config.instance()

    def load_config(env_var_name):
        if env_var_name in os.environ:
            with open(os.environ[env_var_name]) as f:
                yaml_conf = yaml.load(f.read())
            for key, value in yaml_conf.iteritems():
                if hasattr(obj_conf, key):
                    setattr(obj_conf, key, value)

    load_config('MANAGER_REST_CONFIG_PATH')
    load_config('MANAGER_REST_SECURITY_CONFIG_PATH')

load_configuration()
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
