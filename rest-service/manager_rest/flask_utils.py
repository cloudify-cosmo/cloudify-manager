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

from manager_rest import config
from manager_rest.storage import user_datastore, db


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
    set_flask_security_config(app, hash_salt, secret_key)
    Security(app=app, datastore=user_datastore)
    Migrate(app=app, db=db)
    db.init_app(app)
    app.app_context().push()
    return app


def _get_postgres_db_uri(manager_ip, driver):
    """Get a valid SQLA DB URI
    """
    dialect = 'postgresql+{0}'.format(driver) if driver else 'postgres'
    conf = get_postgres_conf()
    return '{dialect}://{username}:{password}@{host}/{db_name}'.format(
        dialect=dialect,
        username=conf.username,
        password=conf.password,
        host=manager_ip,
        db_name=conf.db_name
    )


def get_postgres_conf():
    """Return a namedtuple with info used to connect to cloudify's PG DB
    """
    conf = namedtuple('PGConf', 'username password db_name')
    return conf(
        username='cloudify',
        password='cloudify',
        db_name='cloudify_db'
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
    app.config['SECURITY_TOKEN_MAX_AGE'] = 36000  # 10 hours

    app.config['SECURITY_PASSWORD_SALT'] = hash_salt
    app.config['SECURITY_REMEMBER_SALT'] = hash_salt
    app.config['SECRET_KEY'] = secret_key
