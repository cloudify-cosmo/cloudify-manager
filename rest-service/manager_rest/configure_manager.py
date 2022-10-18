import argparse
import os
import random
import string
import yaml

from collections.abc import MutableMapping

from flask_security.utils import hash_password

from manager_rest import config, constants
from manager_rest.storage import db, models, user_datastore
from manager_rest.amqp_manager import AMQPManager
from manager_rest.flask_utils import setup_flask_app


def dict_merge(target, source):
    """Merge source into target (like dict.update, but deep)

    Returns the merged-into dict.
    """
    to_merge = [(target, source)]
    while to_merge:
        left, right = to_merge.pop()
        overrides = {}
        for k in left.keys() | right.keys():
            if k not in right:
                continue
            original = left.get(k)
            updated = right[k]
            if (
                isinstance(original, MutableMapping) and
                isinstance(updated, MutableMapping)
            ):
                to_merge.append((original, updated))
            else:
                overrides[k] = updated
        left.update(overrides)
    return target


def _generate_password(length=12):
    chars = string.ascii_lowercase + string.ascii_uppercase + string.digits
    password = ''.join(random.choice(chars) for _ in range(length))

    return password


def _get_admin_username(user_config):
    try:
        admin_username = user_config['manager']['security']['admin_username']
    except KeyError:
        admin_username = None
    return admin_username or 'admin'


def _get_admin_password(user_config):
    try:
        admin_password = user_config['manager']['security']['admin_password']
    except KeyError:
        admin_password = None
    return admin_password


def _update_admin_user(admin_user, user_config):
    admin_password = _get_admin_password(user_config)
    if admin_password:
        admin_user.password = hash_password(admin_password)


def _get_default_tenant():
    default_tenant = models.Tenant.query.get(
        constants.DEFAULT_TENANT_ID,
    )
    return default_tenant


def _create_default_tenant():
    """Create the default tenant, and its resources in rabbitmq"""
    default_tenant = models.Tenant(
        id=constants.DEFAULT_TENANT_ID,
        name=constants.DEFAULT_TENANT_NAME
    )
    db.session.add(default_tenant)

    if config.instance.amqp_management_host:
        amqp_manager = AMQPManager(
            host=config.instance.amqp_management_host,
            username=config.instance.amqp_username,
            password=config.instance.amqp_password,
            cadata=config.instance.amqp_ca,
        )
        amqp_manager.create_tenant_vhost_and_user(tenant=default_tenant)

    return default_tenant


def _get_user_tenant_association(user, tenant):
    user_tenant_association = models.UserTenantAssoc.query.filter_by(
        user=user,
        tenant=tenant,
    ).first()
    return user_tenant_association


def _create_admin_user(user_config):
    """Create the admin user based on the passed-in config

    The admin user will have the username&password from the config,
    or use defaults if not provided.
    """
    admin_username = _get_admin_username(user_config)
    admin_password = _get_admin_password(user_config) or _generate_password()

    admin_role = models.Role.query.filter_by(name='sys_admin').one()
    admin_user = user_datastore.create_user(
        id=constants.BOOTSTRAP_ADMIN_ID,
        username=admin_username,
        password=hash_password(admin_password),
        roles=[admin_role]
    )

    print('####################################')
    print(f'USERNAME: {admin_username}')
    print(f'PASSWORD: {admin_password}')
    print('####################################')
    return admin_user


def _setup_user_tenant_assoc(admin_user, default_tenant):
    user_tenant_association = _get_user_tenant_association(
        admin_user,
        default_tenant,
    )

    if not user_tenant_association:
        user_role = user_datastore.find_role(constants.DEFAULT_TENANT_ROLE)

        user_tenant_association = models.UserTenantAssoc(
            user=admin_user,
            tenant=default_tenant,
            role=user_role,
        )
        db.session.add(user_tenant_association)


def configure(user_config):
    """Configure the manager based on the provided config"""
    default_tenant = _get_default_tenant()
    need_assoc = False
    if not default_tenant:
        need_assoc = True
        default_tenant = _create_default_tenant()

    admin_user = user_datastore.get_user(constants.BOOTSTRAP_ADMIN_ID)
    if admin_user:
        _update_admin_user(admin_user, user_config)
    else:
        admin_user = _create_admin_user(user_config)
        need_assoc = True

    if need_assoc:
        _setup_user_tenant_assoc(admin_user, default_tenant)

    db.session.commit()


def _load_user_config(paths):
    """Load and merge the config files provided by paths"""
    user_config = {}
    for config_path in paths:
        if not config_path:
            continue
        with open(config_path) as f:
            config_source = yaml.safe_load(f)
        dict_merge(user_config, config_source)
    return user_config


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create admin user in DB')
    parser.add_argument(
        '-c',
        '--config-file-path',
        help='Path to a config file containing info needed by this script',
        action='append',
        required=False,
        default=[os.environ.get('CONFIG_FILE_PATH')],
    )
    args = parser.parse_args()

    with setup_flask_app().app_context():
        config.instance.load_configuration()
        user_config = _load_user_config(args.config_file_path)
        configure(user_config)