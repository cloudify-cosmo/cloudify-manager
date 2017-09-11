#!/usr/bin/env python
#########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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

import sys
import json

from flask_migrate import upgrade

from manager_rest.storage import db, models, get_storage_manager
from manager_rest.amqp_manager import AMQPManager
from manager_rest.flask_utils import setup_flask_app
from manager_rest.storage.storage_utils import \
    create_default_user_tenant_and_roles


def _init_db_tables(config):
    print 'Setting up a Flask app'
    setup_flask_app(
        manager_ip=config['postgresql_host'],
        hash_salt=config['hash_salt'],
        secret_key=config['secret_key']
    )

    # Clean up the DB, in case it's not a clean install
    db.drop_all()
    db.engine.execute('DROP TABLE IF EXISTS alembic_version;')

    print 'Creating tables in the DB'
    upgrade(directory=config['db_migrate_dir'])


def _add_default_user_and_tenant(config, amqp_manager):
    print 'Creating bootstrap admin, default tenant and security roles'
    create_default_user_tenant_and_roles(
        admin_username=config['admin_username'],
        admin_password=config['admin_password'],
        amqp_manager=amqp_manager
    )


def _get_amqp_manager(config):
    return AMQPManager(
        host=config['amqp_host'],
        username=config['amqp_username'],
        password=config['amqp_password']
    )


def _add_provider_context(config):
    sm = get_storage_manager()
    provider_context = models.ProviderContext(
        id='CONTEXT',
        name='provider',
        context=config['provider_context']
    )
    sm.put(provider_context)


if __name__ == '__main__':
    # We're expecting to receive as an argument the path to the config file
    assert len(sys.argv) == 2, 'No config file path was provided'
    with open(sys.argv[1], 'r') as f:
        config = json.load(f)
    _init_db_tables(config)
    amqp_manager = _get_amqp_manager(config)
    _add_default_user_and_tenant(config, amqp_manager)
    _add_provider_context(config)
    print 'Finished creating bootstrap admin, default tenant and provider ctx'
