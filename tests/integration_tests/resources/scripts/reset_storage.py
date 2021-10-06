########
# Copyright (c) 2018 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import json
import logging
import os
import shutil

import argparse
from flask_migrate import upgrade

from manager_rest import config
from manager_rest.storage import db, models, idencoder
from manager_rest.amqp_manager import AMQPManager
from manager_rest.flask_utils import setup_flask_app
from manager_rest.constants import (
    DEFAULT_TENANT_NAME,
    CURRENT_TENANT_CONFIG
)
from manager_rest.storage.storage_utils import (
    create_default_user_tenant_and_roles
)

# This is a hacky way to get to the migrations folder
migrations_dir = '/opt/manager/resources/cloudify/migrations'
PROVIDER_NAME = 'integration_tests'
DEFAULT_CA_CERT = "/etc/cloudify/ssl/cloudify_internal_ca_cert.pem"
AUTH_TOKEN_LOCATION = '/opt/mgmtworker/work/admin_token'


def setup_amqp_manager():
    amqp_manager = AMQPManager(
        host=config.instance.amqp_management_host or "localhost",
        username=config.instance.amqp_username or "cloudify",
        password=config.instance.amqp_password or "c10udify",
        verify=config.instance.amqp_ca_path or DEFAULT_CA_CERT,
    )
    return amqp_manager


def safe_drop_all(keep_tables):
    """Creates a single transaction that *always* drops all tables, regardless
    of relationships and foreign key constraints (as opposed to `db.drop_all`)
    """
    meta = db.metadata
    for table in reversed(meta.sorted_tables):
        if table.name in keep_tables:
            continue
        db.session.execute(table.delete())
    db.session.commit()


def _add_defaults(app, amqp_manager, script_config):
    """Add default tenant and admin user to the DB"""
    default_tenant = create_default_user_tenant_and_roles(
        admin_username='admin',
        admin_password=None,
        password_hash=script_config['password_hash'],
        amqp_manager=amqp_manager
    )
    for scope, configs in script_config['manager_config'].items():
        for name, value in configs.items():
            item = (
                db.session.query(models.Config)
                .filter_by(scope=scope, name=name).one()
            )
            item.value = value
            db.session.add(item)
    db.session.commit()
    app.config[CURRENT_TENANT_CONFIG] = default_tenant
    return default_tenant


def close_session(app):
    db.session.remove()
    db.get_engine(app).dispose()


def reset_storage(app, script_config):
    amqp_manager = setup_amqp_manager()

    # Clear the old RabbitMQ resources
    amqp_manager.remove_tenant_vhost_and_user(DEFAULT_TENANT_NAME)
    # Rebuild the DB
    safe_drop_all(keep_tables=['roles', 'config', 'rabbitmq_brokers',
                               'certificates', 'managers', 'db_nodes',
                               'licenses', 'usage_collector',
                               'permissions', 'provider_context'])
    upgrade(directory=migrations_dir)
    # Add default tenant, admin user and provider context
    _add_defaults(app, amqp_manager, script_config)


def regenerate_auth_token():
    token_key = models.User.query.get(0).api_token_key
    enc_uid = idencoder.get_encoder().encode(0)
    with open(AUTH_TOKEN_LOCATION, 'w') as f:
        f.write(enc_uid + token_key)


def clean_dirs():
    dirs_to_clean = [
        '/opt/mgmtworker/env/plugins',
        '/opt/mgmtworker/env/source_plugins',
        '/opt/mgmtworker/work/deployments',
        '/opt/manager/resources/blueprints',
        '/opt/manager/resources/uploaded-blueprints',
        '/opt/manager/resources/snapshots/'
    ]
    for directory in dirs_to_clean:
        if not os.path.isdir(directory):
            continue
        for item in os.listdir(directory):
            full_item = os.path.join(directory, item)
            if os.path.isdir(full_item):
                shutil.rmtree(full_item)
            else:
                os.unlink(full_item)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', dest='config', type=argparse.FileType('r'))
    args = parser.parse_args()
    with args.config as f:
        script_config = json.load(f)

    config.instance.logger = logging.getLogger('integration_tests')
    config.instance.load_from_file('/opt/manager/cloudify-rest.conf')
    config.instance.load_from_file('/opt/manager/rest-security.conf',
                                   namespace='security')
    config.instance.load_configuration()

    app = setup_flask_app()
    reset_storage(app, script_config)
    regenerate_auth_token()
    clean_dirs()
    close_session(app)
