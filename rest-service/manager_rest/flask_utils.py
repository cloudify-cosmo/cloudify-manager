from flask import Flask, current_app
from flask_migrate import Migrate
from flask_security import Security

from manager_rest import config, utils
from manager_rest.storage import user_datastore, db, models
from manager_rest.storage.models import Tenant
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
    manager_config.load_configuration(from_db=False)
    with app.app_context():
        app.config['SQLALCHEMY_DATABASE_URI'] = manager_config.db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['ENV'] = 'production'
    set_flask_security_config(app, hash_salt, secret_key)
    Security(app=app, datastore=user_datastore)
    Migrate(app=app, db=db)
    db.init_app(app)
    app.app_context().push()
    return app


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


def query_service_settings():
    """Check for when was the config updated, and if needed, reload it.

    This makes sure that config updates will (eventually) be propagated
    to all workers, and that every worker always has the most recent
    config/permissions settings available.
    """
    last_updated_subquery = (
        db.session.query(models.Role.updated_at.label('updated_at'))
        .union_all(
            db.session.query(models.Config.updated_at.label('updated_at'))
        ).subquery()
    )
    db_config_last_updated = db.session.query(
        db.func.max(last_updated_subquery.c.updated_at)
    ).scalar()
    current_app.logger.debug('Last updated locally: %s, in db: %s',
                             config.instance.last_updated,
                             db_config_last_updated)
    if db_config_last_updated is not None and (
            config.instance.last_updated is None or
            db_config_last_updated > config.instance.last_updated):
        current_app.logger.warning('Config has changed - reloading')
        config.instance.load_from_db()
        current_app.logger.setLevel(config.instance.rest_service_log_level)
