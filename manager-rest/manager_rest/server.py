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

import sys
import logging
import os

from flask import Flask
from flask.ext.restful import Api

import config
import resources
import blueprints_manager
import events_manager
import storage_manager


app = None


def reset_state(configuration=None):
    config.reset(configuration)
    blueprints_manager.reset()
    events_manager.reset()
    storage_manager.reset()


def setup_app():
    global app
    app = Flask(__name__)
    app.logger.setLevel(logging.DEBUG)
    app.logger.addHandler(logging.StreamHandler(sys.stdout))

    api = Api(app)
    resources.setup_resources(api)


if 'MANAGER_REST_FILE_SERVER_BASE_URI' in os.environ:
    config.instance().file_server_base_uri = \
        os.environ['MANAGER_REST_FILE_SERVER_BASE_URI']
    setup_app()
if 'MANAGER_REST_FILE_SERVER_ROOT' in os.environ:
    config.instance().file_server_root = \
        os.environ['MANAGER_REST_FILE_SERVER_ROOT']
if 'MANAGER_REST_WORKFLOW_SERVICE_BASE_URI' in os.environ:
    config.instance().workflow_service_base_uri = \
        os.environ['MANAGER_REST_WORKFLOW_SERVICE_BASE_URI']
if 'MANAGER_REST_EVENTS_FILE_PATH' in os.environ:
    config.instance().events_files_path = \
        os.environ['MANAGER_REST_EVENTS_FILE_PATH']
