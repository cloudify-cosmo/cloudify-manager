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
import logging
from path import path
from tempfile import mkstemp
from contextlib import contextmanager

from flask_migrate import upgrade

from cloudify.utils import setup_logger

import manager_rest
from manager_rest.storage import db, models
from manager_rest.amqp_manager import AMQPManager
from manager_rest.flask_utils import setup_flask_app as _setup_flask_app
from manager_rest.storage.storage_utils import \
    create_default_user_tenant_and_roles
from manager_rest.constants import (PROVIDER_CONTEXT_ID,
                                    CURRENT_TENANT_CONFIG,
                                    DEFAULT_TENANT_NAME)
from integration_tests.framework import utils
from integration_tests.framework.postgresql import safe_drop_all
from integration_tests.framework.docl import read_file as read_manager_file
from integration_tests.tests.constants import PROVIDER_NAME, PROVIDER_CONTEXT
from integration_tests.framework.constants import AUTHORIZATION_FILE_LOCATION


logger = setup_logger('Flask Utils', logging.INFO)

security_config = None
amqp_manager = None

# This is a hacky way to get to the migrations folder
base_dir = path(manager_rest.__file__).parent.parent.parent
migrations_dir = base_dir / 'resources' / 'rest-service' / \
                            'cloudify' / 'migrations'


def setup_flask_app():
    global security_config
    if not security_config:
        conf_file_str = read_manager_file('/opt/manager/rest-security.conf')
        security_config = yaml.load(conf_file_str)

    manager_ip = utils.get_manager_ip()
    return _setup_flask_app(
        manager_ip=manager_ip,
        hash_salt=security_config['hash_salt'],
        secret_key=security_config['secret_key']
    )


def setup_amqp_manager():
    global amqp_manager
    if not amqp_manager:
        conf_file_str = read_manager_file('/opt/manager/cloudify-rest.conf')
        config = yaml.load(conf_file_str)
        amqp_manager = AMQPManager(
            host=config['amqp_management_host'],
            username=config['amqp_username'],
            password=config['amqp_password'],
            verify=config['amqp_ca_path']
        )
    return amqp_manager


def reset_storage():
    logger.info('Resetting PostgreSQL DB')
    app = setup_flask_app()
    setup_amqp_manager()

    # Clear the old RabbitMQ resources
    amqp_manager.remove_tenant_vhost_and_user(DEFAULT_TENANT_NAME)

    # Rebuild the DB
    safe_drop_all(keep_tables=['roles'])
    upgrade(directory=migrations_dir)

    # Add default tenant, admin user and provider context
    _add_defaults(app)

    # Clear the connection
    close_session(app)


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


def _add_defaults(app):
    """Add default tenant, admin user and provider context to the DB
    """
    # Add the default network to the provider context
    networks = PROVIDER_CONTEXT['cloudify']['cloudify_agent']['networks']
    networks['default'] = utils.get_manager_ip()

    provider_context = models.ProviderContext(
        id=PROVIDER_CONTEXT_ID,
        name=PROVIDER_NAME,
        context=PROVIDER_CONTEXT
    )
    db.session.add(provider_context)

    with _get_local_authorization_conf_path() as auth_conf_path:
        default_tenant = create_default_user_tenant_and_roles(
            admin_username=utils.get_manager_username(),
            admin_password=utils.get_manager_password(),
            amqp_manager=amqp_manager,
            authorization_file_path=auth_conf_path
        )

    app.config[CURRENT_TENANT_CONFIG] = default_tenant
    return default_tenant


@contextmanager
def _get_local_authorization_conf_path():
    """ Read the auth config from the manager, and write it to a temp file """

    content = read_manager_file(AUTHORIZATION_FILE_LOCATION)
    yaml_content = yaml.load(content)
    fd, file_path = mkstemp()
    os.close(fd)
    with open(file_path, 'w') as f:
        yaml.dump(yaml_content, f)

    yield file_path

    os.remove(file_path)
