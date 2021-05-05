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
import subprocess

import argparse
from flask_migrate import upgrade

from manager_rest import config
from manager_rest.storage import db, models
from manager_rest.amqp_manager import AMQPManager
from manager_rest.flask_utils import setup_flask_app
from manager_rest.constants import (
    PROVIDER_CONTEXT_ID,
    DEFAULT_TENANT_NAME,
    CURRENT_TENANT_CONFIG
)
from manager_rest.storage.storage_utils import (
    create_default_user_tenant_and_roles
)

# This is a hacky way to get to the migrations folder
migrations_dir = '/opt/manager/resources/cloudify/migrations'
PROVIDER_NAME = 'integration_tests'
ADMIN_TOKEN_RESET_SCRIPT = '/opt/cloudify/mgmtworker/create-admin-token.py'
DEFAULT_CA_CERT = "/etc/cloudify/ssl/cloudify_internal_ca_cert.pem"


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
    """Add default tenant, admin user and provider context to the DB
    """
    # Add the default network to the provider context
    context = script_config['provider_context']
    networks = context['cloudify']['cloudify_agent']['networks']
    networks['default'] = script_config['ip']

    provider_context = models.ProviderContext(
        id=PROVIDER_CONTEXT_ID,
        name=PROVIDER_NAME,
        context=context
    )
    db.session.add(provider_context)

    default_tenant = create_default_user_tenant_and_roles(
        admin_username=script_config['username'],
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


def reset_storage(script_config):
    app = setup_flask_app()
    config.instance.load_configuration()
    amqp_manager = setup_amqp_manager()

    # Clear the old RabbitMQ resources
    amqp_manager.remove_tenant_vhost_and_user(DEFAULT_TENANT_NAME)

    # Rebuild the DB
    safe_drop_all(keep_tables=['roles', 'config', 'rabbitmq_brokers',
                               'certificates', 'managers', 'db_nodes',
                               'licenses', 'usage_collector',
                               'permissions'])
    upgrade(directory=migrations_dir)

    # Add default tenant, admin user and provider context
    _add_defaults(app, amqp_manager, script_config)

    # Clear the connection
    close_session(app)

    subprocess.check_call(['sudo', ADMIN_TOKEN_RESET_SCRIPT])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', dest='config', type=argparse.FileType('r'))
    args = parser.parse_args()
    with args.config as f:
        script_config = json.load(f)
    for namespace, path in script_config['config'].items():
        config.instance.load_from_file(path, namespace=namespace)
    reset_storage(script_config)
