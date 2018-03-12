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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import json
import logging
import tempfile

from cloudify.utils import setup_logger

from manager_rest.storage import db, models
from integration_tests.framework import constants, utils
from integration_tests.framework.docl import execute, copy_file_to_manager
from integration_tests.tests.constants import PROVIDER_CONTEXT
from integration_tests.tests.utils import get_resource


logger = setup_logger('Flask Utils', logging.INFO)

SCRIPT_PATH = '/tmp/reset_storage.py'
CONFIG_PATH = '/tmp/reset_storage_config.json'


def prepare_reset_storage_script():
    reset_script = get_resource('scripts/reset_storage.py')
    copy_file_to_manager(reset_script, SCRIPT_PATH)
    with tempfile.NamedTemporaryFile(delete=False) as f:
        json.dump({
            'config': {
                '': constants.CONFIG_FILE_LOCATION,
                'security': constants.SECURITY_FILE_LOCATION,
                'authorization': constants.AUTHORIZATION_FILE_LOCATION
            },
            'ip': utils.get_manager_ip(),
            'username': utils.get_manager_username(),
            'password': utils.get_manager_password(),
            'provider_context': PROVIDER_CONTEXT
        }, f)
    try:
        copy_file_to_manager(f.name, CONFIG_PATH)
    finally:
        os.unlink(f.name)


def reset_storage():
    logger.info('Resetting PostgreSQL DB')
    # reset the storage by calling a script on the manager, to access
    # localhost-only APIs (rabbitmq management api)
    execute("/opt/manager/env/bin/python {script_path} --config {config_path}"
            .format(script_path=SCRIPT_PATH, config_path=CONFIG_PATH))


def close_session(app):
    db.session.remove()
    db.get_engine(app).dispose()


def load_user(app, username=None):
    if username:
        user = models.User.query.filter(username=username).first()
    else:
        user = models.User.query.get(0)  # Admin

    # This line is necessary for the `reload_user` method - we add a mock
    # request context to the flask stack
    app.test_request_context().push()

    # And then load the admin as the currently active user
    app.extensions['security'].login_manager.reload_user(user)
    return user
