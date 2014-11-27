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

import logging
import functools
import traceback
import os
import yaml
from logging.handlers import RotatingFileHandler

from flask import (
    Flask,
    jsonify,
    request
)
from flask_restful import Api

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
            '/home/ubuntu/cloudify-rest-service.log',
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
