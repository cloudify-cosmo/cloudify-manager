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

__author__ = 'dan'

import logging
import sys
import functools
import traceback
import os
import yaml

from flask import Flask, jsonify
from flask_restful import Api

from manager_rest import config
# from manager_rest import blueprints_manager
from manager_rest import storage_manager
from manager_rest import resources
from manager_rest import manager_exceptions


# app factory
def setup_app():
    app = Flask(__name__)

    app.logger.setLevel(logging.DEBUG)
    app.logger.addHandler(logging.StreamHandler(sys.stdout))

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
    if 'workflow_service_base_uri' in yaml_conf:
        obj_conf.workflow_service_base_uri = \
            yaml_conf['workflow_service_base_uri']

app = setup_app()


@app.errorhandler(500)
def internal_error(e):
    response = jsonify(
        {"message":
         "Internal error occurred in manager REST server - {0}: {1}"
            .format(type(e).__name__, str(e)),
         "errorCode": manager_exceptions.INTERNAL_SERVER_ERROR_CODE,
         "traceback": traceback.format_tb(sys.exc_info()[2])})
    response.status_code = 500
    return response
