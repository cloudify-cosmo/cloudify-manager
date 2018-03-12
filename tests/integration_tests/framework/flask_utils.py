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

import logging

from cloudify.utils import setup_logger

from manager_rest.storage import db, models
from integration_tests.framework import utils
from integration_tests.framework.docl import execute, copy_file_to_manager
from integration_tests.tests.utils import get_resource

logger = setup_logger('Flask Utils', logging.INFO)


def reset_storage():
    logger.info('Resetting PostgreSQL DB')
    reset_script = get_resource('scripts/reset_storage.py')
    target_script_path = '/tmp/reset_storage.py'
    # reset the storage by calling a script on the manager, to access
    # localhost-only APIs (rabbitmq management api)
    copy_file_to_manager(reset_script, target_script_path)
    execute("bash -c 'MANAGER_REST_CONFIG_PATH={config_path} "
            "MANAGER_REST_SECURITY_CONFIG_PATH={security_config_path} "
            "MANAGER_REST_AUTHORIZATION_CONFIG_PATH={auth_config_path} "
            "/opt/manager/env/bin/python {target_script_path} "
            "--manager-ip {ip} "
            "--username {username} "
            "--password {password}'".format(
                config_path='/opt/manager/cloudify-rest.conf',
                security_config_path='/opt/manager/rest-security.conf',
                auth_config_path='/opt/manager/authorization.conf',
                target_script_path=target_script_path,
                ip=utils.get_manager_ip(),
                username=utils.get_manager_username(),
                password=utils.get_manager_password(),
            ))


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
