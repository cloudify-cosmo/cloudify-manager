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
import secrets
import shutil
from string import ascii_uppercase, ascii_lowercase, digits

import argparse
from flask_migrate import upgrade
from flask_security.utils import hash_password

from manager_rest import config
from manager_rest.storage import db, models, get_storage_manager
from manager_rest.flask_utils import setup_flask_app
from manager_rest.constants import (
    BOOTSTRAP_ADMIN_ID,
    DEFAULT_TENANT_ID,
)

# This is a hacky way to get to the migrations folder
migrations_dir = '/opt/manager/resources/cloudify/migrations'
PROVIDER_NAME = 'integration_tests'
DEFAULT_CA_CERT = "/etc/cloudify/ssl/cloudify_internal_ca_cert.pem"
AUTH_TOKEN_LOCATION = '/opt/mgmtworker/work/admin_token'


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


def _reset_config(app, script_config):
    for scope, configs in script_config['manager_config'].items():
        for name, value in configs.items():
            item = (
                db.session.query(models.Config)
                .filter_by(scope=scope, name=name).one()
            )
            item.value = value
            db.session.add(item)
    db.session.commit()


def _reset_admin_user(script_config):
    admin = models.User.query.filter_by(username='admin').one()
    tenant = models.Tenant.query.filter_by(name='default_tenant').one()
    admin.password = script_config['password_hash']
    admin.active = True
    tenant.rabbitmq_password = script_config['default_tenant_password']
    db.session.commit()


def _delete_users():
    """Delete all users and tenants, except for admin and default_tenant"""
    db.session.execute(
        models.User.__table__.delete()
        .where(models.User.id != BOOTSTRAP_ADMIN_ID)
    )
    db.session.execute(
        models.Tenant.__table__.delete()
        .where(models.Tenant.id != DEFAULT_TENANT_ID)
    )
    db.session.commit()


def close_session(app):
    db.session.remove()
    db.get_engine(app).dispose()


def reset_storage(app, script_config):
    # Rebuild the DB
    safe_drop_all(keep_tables=['roles', 'config', 'rabbitmq_brokers',
                               'certificates', 'managers', 'db_nodes',
                               'licenses', 'usage_collector',
                               'permissions', 'provider_context',
                               'users', 'tenants', 'users_tenants',
                               'users_roles'])
    _delete_users()
    upgrade(directory=migrations_dir)
    _reset_config(app, script_config)
    _reset_admin_user(script_config)


def _random_string(length=10):
    """A random string that is a bit more user friendly than uuids"""
    charset = ascii_uppercase + ascii_lowercase + digits
    return ''.join(secrets.choice(charset) for i in range(length))


def regenerate_auth_token():
    sm = get_storage_manager()
    secret = _random_string()
    token = models.Token(
        id='abc123def4',
        description='Inte-tests mgmtworker',
        secret_hash=hash_password(secret),
        expiration_date=None,
        _user_fk=0,
    )
    sm.put(token)

    token._secret = secret
    value = token.to_response()['value']

    with open(AUTH_TOKEN_LOCATION, 'w') as f:
        f.write(value)


def clean_dirs():
    dirs_to_clean = [
        '/opt/mgmtworker/env/plugins',
        '/opt/mgmtworker/env/source_plugins',
        '/opt/mgmtworker/work/deployments',
        '/opt/manager/resources/blueprints',
        '/opt/manager/resources/deployments',
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
