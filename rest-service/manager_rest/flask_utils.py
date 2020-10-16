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

from collections import namedtuple

from flask import Flask
from flask_migrate import Migrate
from flask_security import Security

from manager_rest import config, utils
from manager_rest.storage import user_datastore, db
from manager_rest.storage.models import User, Tenant
from manager_rest.config import instance as manager_config


def setup_flask_app(manager_ip='localhost',
                    driver='',
                    hash_salt=None,
                    secret_key=None):
    """Setup a functioning flask app, when working outside the rest-service

    :param manager_ip: The IP of the manager
    :param driver: SQLA driver for postgres (e.g. pg8000)
    :param hash_salt: The salt to be used when creating user passwords
    :param secret_key: Secret key used when hashing flask tokens
    :return: A Flask app
    """
    app = Flask(__name__)
    db_uri = _get_postgres_db_uri(manager_ip, driver)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['ENV'] = 'production'
    set_flask_security_config(app, hash_salt, secret_key)
    Security(app=app, datastore=user_datastore)
    Migrate(app=app, db=db)
    db.init_app(app)
    app.app_context().push()
    return app


def _get_postgres_db_uri(manager_ip, driver):
    """Get a valid SQLA DB URI"""
    dialect = 'postgresql+{0}'.format(driver) if driver else 'postgres'
    conf = get_postgres_conf(manager_ip)
    conn_string = '{dialect}://{username}:{password}@{host}/{db_name}'.format(
        dialect=dialect,
        username=conf.username,
        password=conf.password,
        host=conf.host,
        db_name=conf.db_name
    )
    if config.instance.postgresql_ssl_enabled:
        params = {}
        ssl_mode = 'verify-full'
        if config.instance.postgresql_ssl_client_verification:
            params.update({
                'sslcert': config.instance.postgresql_ssl_cert_path,
                'sslkey': config.instance.postgresql_ssl_key_path,
            })
        params.update({
            'sslmode': ssl_mode,
            'sslrootcert': config.instance.postgresql_ca_cert_path
        })
        if any(params.values()):
            query = '&'.join('{0}={1}'.format(key, value)
                             for key, value in params.items()
                             if value)
            conn_string = '{0}?{1}'.format(conn_string, query)
    return conn_string


def get_postgres_conf(manager_ip='localhost'):
    """Return a namedtuple with info used to connect to cloudify's PG DB
    """
    # can't load from db yet - we're just loading the settings to connect to
    # the db at all
    manager_config.load_configuration(from_db=False)
    conf = namedtuple('PGConf', 'host username password db_name')
    return conf(
        host=manager_config.postgresql_host or manager_ip,
        username=manager_config.postgresql_username or 'cloudify',
        password=manager_config.postgresql_password or 'cloudify',
        db_name=manager_config.postgresql_db_name or 'cloudify_db',
    )


def set_flask_security_config(app, hash_salt=None, secret_key=None):
    """Set all necessary Flask-Security configurations

    :param app: Flask app object
    :param hash_salt: The salt to be used when creating user passwords
    :param secret_key: Secret key used when hashing flask tokens
    """
    hash_salt = hash_salt or config.instance.security_hash_salt
    secret_key = secret_key or config.instance.security_secret_key

    # Make sure that it's possible to get users from the datastore
    # by username and not just by email (the default behavior)
    app.config['SECURITY_USER_IDENTITY_ATTRIBUTES'] = 'username, email'
    app.config['SECURITY_PASSWORD_HASH'] = 'pbkdf2_sha256'
    app.config['SECURITY_HASHING_SCHEMES'] = ['pbkdf2_sha256']
    app.config['SECURITY_DEPRECATED_HASHING_SCHEMES'] = []
    app.config['SECURITY_TOKEN_MAX_AGE'] = 36000  # 10 hours

    app.config['SECURITY_PASSWORD_SALT'] = hash_salt
    app.config['SECURITY_REMEMBER_SALT'] = hash_salt
    app.config['SECRET_KEY'] = secret_key


def set_tenant_in_app(tenant):
    """Set the tenant as the current tenant in the flask app.

    Requires app context (using `with app.app_context()` or push as returned
    by setup_flask_app"""
    utils.set_current_tenant(tenant)


def get_tenant_by_name(tenant_name):
    """Get the tenant name, or fail noisily.
    """
    tenant = Tenant.query.filter_by(name=tenant_name).first()
    if not tenant:
        raise Exception(
            'Could not restore into tenant "{name}" as this tenant does '
            'not exist.'.format(name=tenant_name)
        )
    return tenant


def set_admin_current_user(app):
    """Set the admin as the current user in the flask app

    :return: The admin user
    """
    admin = User.query.get(0)
    # This line is necessary for the `reload_user` method - we add a mock
    # request context to the flask stack
    app.test_request_context().push()

    # And then load the admin as the currently active user
    app.extensions['security'].login_manager.reload_user(admin)
    return admin
