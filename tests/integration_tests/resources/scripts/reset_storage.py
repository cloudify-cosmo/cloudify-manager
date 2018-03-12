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

import os
import argparse

from manager_rest.storage import db, models

from flask_migrate import upgrade
from manager_rest import config
from manager_rest.amqp_manager import AMQPManager
from manager_rest.flask_utils import setup_flask_app
from manager_rest.constants import (PROVIDER_CONTEXT_ID,
                                    CURRENT_TENANT_CONFIG,
                                    DEFAULT_TENANT_NAME)
from manager_rest.storage.storage_utils import \
    create_default_user_tenant_and_roles


# This is a hacky way to get to the migrations folder
migrations_dir = '/opt/manager/resources/cloudify/migrations'
PROVIDER_NAME = 'integration_tests'
PROVIDER_CONTEXT = {
    'cloudify': {
        'workflows': {
            'task_retries': 0,
            'task_retry_interval': 0,
            'subgraph_retries': 0
        },
        'cloudify_agent':
            {
                'broker_ip': '',
                'broker_user': 'cloudify',
                'broker_pass': 'c10udify',
                'networks': {}
        },
    }
}


def setup_amqp_manager():
    amqp_manager = AMQPManager(
        host=config.instance.amqp_management_host,
        username=config.instance.amqp_username,
        password=config.instance.amqp_password,
        verify=config.instance.amqp_ca_path
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


def _add_defaults(app, amqp_manager, manager_ip, username, password):
    """Add default tenant, admin user and provider context to the DB
    """
    # Add the default network to the provider context
    networks = PROVIDER_CONTEXT['cloudify']['cloudify_agent']['networks']
    networks['default'] = manager_ip

    provider_context = models.ProviderContext(
        id=PROVIDER_CONTEXT_ID,
        name=PROVIDER_NAME,
        context=PROVIDER_CONTEXT
    )
    db.session.add(provider_context)

    default_tenant = create_default_user_tenant_and_roles(
        admin_username=username,
        admin_password=password,
        amqp_manager=amqp_manager,
        authorization_file_path=os.environ[
            'MANAGER_REST_AUTHORIZATION_CONFIG_PATH']
    )

    app.config[CURRENT_TENANT_CONFIG] = default_tenant
    return default_tenant


def close_session(app):
    db.session.remove()
    db.get_engine(app).dispose()


def reset_storage(manager_ip, username, password):
    app = setup_flask_app()
    amqp_manager = setup_amqp_manager()

    # Clear the old RabbitMQ resources
    amqp_manager.remove_tenant_vhost_and_user(DEFAULT_TENANT_NAME)

    # Rebuild the DB
    safe_drop_all(keep_tables=['roles'])
    upgrade(directory=migrations_dir)

    # Add default tenant, admin user and provider context
    _add_defaults(app, amqp_manager, manager_ip, username, password)

    # Clear the connection
    close_session(app)


if __name__ == '__main__':
    for required_env_var in [
        'MANAGER_REST_CONFIG_PATH',
        'MANAGER_REST_SECURITY_CONFIG_PATH',
        'MANAGER_REST_AUTHORIZATION_CONFIG_PATH'
    ]:
        if required_env_var not in os.environ:
            raise RuntimeError('{0} is a required environment variable'
                               .format(required_env_var))
    parser = argparse.ArgumentParser()
    parser.add_argument('--manager-ip', dest='manager_ip')
    parser.add_argument('--username', dest='username')
    parser.add_argument('--password', dest='password')
    args = parser.parse_args()
    config.instance.load_configuration()
    reset_storage(args.manager_ip, args.username, args.password)
