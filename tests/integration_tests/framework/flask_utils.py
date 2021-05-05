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
import yaml
import json
import logging
import tempfile

from cloudify.utils import setup_logger

from manager_rest.storage import db, models
from manager_rest.constants import SECURITY_FILE_LOCATION

from integration_tests.framework import utils
from integration_tests.framework.docker import (execute,
                                                copy_file_to_manager,
                                                get_manager_ip,
                                                read_file as read_manager_file)
from integration_tests.tests.constants import MANAGER_CONFIG, MANAGER_PYTHON
from integration_tests.tests.utils import get_resource


logger = setup_logger('Flask Utils', logging.INFO)
security_config = None

PREPARE_SCRIPT_PATH = '/tmp/prepare_reset_storage.py'
SCRIPT_PATH = '/tmp/reset_storage.py'
CONFIG_PATH = '/tmp/reset_storage_config.json'


def prepare_reset_storage_script(container_id):
    reset_script = get_resource('scripts/reset_storage.py')
    prepare = get_resource('scripts/prepare_reset_storage.py')
    copy_file_to_manager(container_id, reset_script, SCRIPT_PATH)
    copy_file_to_manager(container_id, prepare, PREPARE_SCRIPT_PATH)
    with tempfile.NamedTemporaryFile(delete=False, mode='w') as f:
        json.dump({
            'manager_config': MANAGER_CONFIG,
        }, f)
    try:
        copy_file_to_manager(container_id, f.name, CONFIG_PATH)
        execute(container_id,
                [MANAGER_PYTHON, PREPARE_SCRIPT_PATH, '--config', CONFIG_PATH])
    finally:
        os.unlink(f.name)


def reset_storage(container_id):
    logger.info('Resetting PostgreSQL DB')
    # reset the storage by calling a script on the manager, to access
    # localhost-only APIs (rabbitmq management api)
    execute(container_id,
            [MANAGER_PYTHON, SCRIPT_PATH, '--config', CONFIG_PATH])


def set_ldap(config_data):
    logger.info('Setting LDAP configuration')
    _prepare_set_ldap_script()
    execute("{manager_python} {script_path} --config '{cfg_data}'"
            .format(manager_python=MANAGER_PYTHON,
                    script_path='/tmp/set_ldap.py',
                    cfg_data=json.dumps(config_data)))


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


def _prepare_set_ldap_script():
    set_ldap_script = get_resource('scripts/set_ldap.py')
    copy_file_to_manager(set_ldap_script, '/tmp/set_ldap.py')
