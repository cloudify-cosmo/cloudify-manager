import argparse
import datetime
import logging
import os
import socket
import sys
import time
import yaml

from collections.abc import MutableMapping

from flask_security.utils import hash_password

from cloudify.utils import ipv6_url_compat

from manager_rest import config, constants, permissions, version
from manager_rest.storage import (
    db,
    models,
    user_datastore,
)
from manager_rest.amqp_manager import AMQPManager
from manager_rest.flask_utils import setup_flask_app


REST_LOG_DIR = '/var/log/cloudify/rest'
REST_HOME_DIR = '/opt/manager'
DEFAULT_FILE_SERVER_ROOT = os.path.join(REST_HOME_DIR, 'resources')
DEFAULT_INTERNAL_REST_PORT = 53333


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


def _get_rabbitmq_ca_path(user_config):
    try:
        value = user_config['rabbitmq']['ca_path']
    except KeyError:
        value = ''

    return value or '/etc/cloudify/ssl/cloudify_internal_ca_cert.pem'


def _get_manager_ca_path():
    # not configurable currently
    return '/etc/cloudify/ssl/cloudify_internal_ca_cert.pem'


def _get_rabbitmq_use_hostnames_in_db(user_config):
    try:
        value = user_config['rabbitmq']['use_hostnames_in_db']
    except KeyError:
        value = False

    return value


def _get_rabbitmq_use_hostnames_is_external(user_config):
    try:
        value = user_config['rabbitmq']['is_external']
    except KeyError:
        value = False

    return value


def _get_rabbitmq_username(user_config):
    try:
        value = user_config['rabbitmq']['username']
    except KeyError:
        value = None

    return value or 'cloudify'


def _get_rabbitmq_password(user_config):
    try:
        value = user_config['rabbitmq']['password']
    except KeyError:
        value = None

    return value or 'c10udify'


def _get_rabbitmq_cluster_members(user_config):
    try:
        value = user_config['rabbitmq']['cluster_members']
    except KeyError:
        value = {}

    return value or {
            'rabbitmq': {
                'networks': {
                    'default': 'rabbitmq',
                }
            }
        }


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
    admin_password = _get_admin_password(user_config) or 'admin'

    admin_role = models.Role.query.filter_by(name='sys_admin').one()
    admin_user = user_datastore.create_user(
        id=constants.BOOTSTRAP_ADMIN_ID,
        username=admin_username,
        password=hash_password(admin_password),
        roles=[admin_role]
    )

    logging.critical('####################################')
    logging.critical('USERNAME: %s', admin_username)
    logging.critical('PASSWORD: %s', admin_password)
    logging.critical('####################################')
    return admin_user


def _setup_user_tenant_assoc(admin_user, default_tenant):
    user_tenant_association = _get_user_tenant_association(
        admin_user,
        default_tenant,
    )

    if not user_tenant_association:
        user_role = (
            models.Role.query
            .filter_by(name=constants.DEFAULT_TENANT_ROLE)
            .one()
        )
        user_tenant_association = models.UserTenantAssoc(
            user=admin_user,
            tenant=default_tenant,
            role=user_role,
        )
        db.session.add(user_tenant_association)


def _create_provider_context(user_config):
    pc = (
        models.ProviderContext.query
        .filter_by(id='CONTEXT')
        .first()
    )
    if pc is None:
        pc = models.ProviderContext(
            id='CONTEXT',
            name='provider',
        )
    pc.context = user_config.get('provider_context') or {}
    db.session.add(pc)


def _insert_rabbitmq_broker(brokers, ca_cert):
    existing_brokers = {b.name: b for b in models.RabbitMQBroker.query.all()}

    for broker in brokers:
        name = broker['name']
        if name in existing_brokers:
            inst = existing_brokers[name]
            for k, v in broker.items():
                setattr(inst, k, v)
            inst.ca_cert = ca_cert
        else:
            inst = models.RabbitMQBroker(
                ca_cert=ca_cert,
                **broker
            )
        db.session.add(inst)


def _get_rabbitmq_brokers(user_config):
    use_hostnames = _get_rabbitmq_use_hostnames_in_db(user_config)
    is_external = _get_rabbitmq_use_hostnames_is_external(user_config)
    cluster_members = _get_rabbitmq_cluster_members(user_config)

    return [
        {
            'name': name,
            'host': name if use_hostnames else broker['networks']['default'],
            'management_host': (
                name if use_hostnames else broker['networks']['default']
            ),
            'username': _get_rabbitmq_username(user_config),
            'password': _get_rabbitmq_password(user_config),
            'params': None,
            'networks': broker['networks'],
            'is_external': is_external,
        }
        for name, broker in cluster_members.items()
    ]


def _get_rabbitmq_ca_cert(rabbitmq_ca_cert_path):
    if rabbitmq_ca_cert_path:
        try:
            with open(rabbitmq_ca_cert_path) as f:
                return f.read()
        except FileNotFoundError:
            return ''
    return ''


def _insert_rabbitmq_ca_cert(value, name):
    cert = models.Certificate.query.filter_by(name=name).first()
    if cert:
        cert.value = value
    else:
        cert = models.Certificate(
            name=name,
            value=value,
            updated_at=datetime.datetime.now(),
        )
    db.session.add(cert)
    return cert


def _register_rabbitmq_brokers(user_config):
    rabbitmq_brokers = _get_rabbitmq_brokers(user_config)

    if rabbitmq_brokers:
        rabbitmq_ca_path = _get_rabbitmq_ca_path(user_config)
        rabbitmq_ca_cert = _get_rabbitmq_ca_cert(rabbitmq_ca_path)
        rabbitmq_ca = _insert_rabbitmq_ca_cert(
            rabbitmq_ca_cert,
            'rabbitmq-ca',
        )

        _insert_rabbitmq_broker(
            rabbitmq_brokers,
            rabbitmq_ca,
        )

        # reload config after inserting rabbitmqs, so that .amqp_host
        # and others are set
        config.instance.load_from_db(session=db.session)


def _create_roles(user_config):
    default_roles = permissions.ROLES
    roles_to_make = list(user_config.get('roles') or [])  # copy
    seen_roles = {r['name'] for r in roles_to_make}

    for default_role in default_roles:
        if default_role['name'] not in seen_roles:
            roles_to_make.append(default_role)

    for role_spec in roles_to_make:
        role = models.Role.query.filter_by(name=role_spec['name']).first()
        if role is None:
            role = models.Role(name=role_spec['name'])
        role.description = role_spec.get('description')
        role.type = role_spec.get('type', 'system_role')
        db.session.add(role)


def _create_permissions(user_config):
    default_permissions = permissions.PERMISSIONS
    permissions_to_make = dict(user_config.get('permissions') or {})  # copy

    for default_permission in default_permissions:
        if default_permission not in permissions_to_make:
            permissions_to_make[default_permission] = set()

    existing_permissions = {}
    for p in models.Permission.query.all():
        existing_permissions.setdefault(p.name, set()).add(p.role_name)

    roles = {r.name: r for r in models.Role.query.all()}

    for permission_name, role_names in permissions_to_make.items():
        already_assigned = existing_permissions.get(permission_name, set())
        missing_roles = set(role_names) | {'sys_admin'} - already_assigned

        for role_name in missing_roles:
            try:
                role = roles[role_name]
            except KeyError:
                raise ValueError(
                    f'Permission {permission_name} is assigned '
                    f'to non-existent role {role_name}'
                )
            perm = models.Permission(
                name=permission_name,
                role=role,
            )
            db.session.add(perm)


def _update_manager_ca_cert(manager, ca_cert):
    stored_cert = manager.ca_cert
    if ca_cert and stored_cert:
        if stored_cert.value.strip() != ca_cert.strip():
            raise RuntimeError('ca_cert differs from existing manager CA')

    if not stored_cert:
        if not ca_cert:
            with open(_get_manager_ca_path()) as f:
                ca_cert = f.read()
        if not ca_cert:
            raise RuntimeError('No manager certs found, and ca_cert not given')
        ca = models.Certificate(
            name=f'{manager.hostname}-ca',
            value=ca_cert,
            updated_at=datetime.datetime.utcnow(),
        )
        manager.ca_cert = ca
        db.session.add(ca)


def _insert_manager(user_config):
    manager_config = user_config.get('manager') or {}
    hostname = manager_config.get('hostname')
    if not hostname:
        return

    manager = models.Manager.query.filter_by(hostname=hostname).first()
    if not manager:
        manager = models.Manager(hostname=hostname)
        db.session.add(manager)

    private_ip = manager_config.get('private_ip')
    public_ip = manager_config.get('public_ip')
    networks = manager_config.get('networks') or {}
    networks.setdefault('default', private_ip or public_ip)

    manager.networks = networks or manager.networks
    manager.private_ip = private_ip or manager.private_ip or public_ip
    manager.public_ip = public_ip or manager.public_ip or private_ip

    version_data = version.get_version_data()
    manager.version = version_data.get('version')
    manager.edition = version_data.get('edition')
    manager.distribution = version_data.get('distribution')
    manager.distro_release = version_data.get('distro_release')
    manager.last_seen = datetime.datetime.utcnow()

    ca_cert = manager_config.get('ca_cert')
    if ca_cert or not manager.ca_cert:
        _update_manager_ca_cert(manager, ca_cert)


def create_system_filters():
    current_deployment_filters = models.DeploymentsFilter.query.all()
    curr_dep_filters_ids = {dep_filter.id for dep_filter
                            in current_deployment_filters}
    creator = models.User.query.get(constants.BOOTSTRAP_ADMIN_ID)
    tenant = models.Tenant.query.get(constants.DEFAULT_TENANT_ID)
    now = datetime.datetime.utcnow()
    if 'csys-environment-filter' not in curr_dep_filters_ids:
        env_filter = {
            'id': 'csys-environment-filter',
            'value': [
                {
                    'key': 'csys-obj-type',
                    'values': ['environment'],
                    'operator': 'any_of',
                    'type': 'label'
                },
                {
                    'key': 'csys-obj-parent',
                    'values': [],
                    'operator': 'is_null',
                    'type': 'label'
                }
            ]
        }
        _add_deployments_filter(env_filter, creator, tenant, now)
    if 'csys-service-filter' not in curr_dep_filters_ids:
        service_filter = {
            'id': 'csys-service-filter',
            'value': [
                {
                    'key': 'csys-obj-type',
                    'values': ['environment'],
                    'operator': 'is_not',
                    'type': 'label'
                },
                {
                    'key': 'csys-obj-parent',
                    'values': [],
                    'operator': 'is_null',
                    'type': 'label'
                },
            ]
        }
        _add_deployments_filter(service_filter, creator, tenant, now)

    for filter_id, obj_type_value in {
        'csys-k8s-filter': 'k8s',
        'csys-terraform-filter': 'terraform',
        'aws-deployments': 'aws',
        'azure-deployments': 'azure',
        'gcp-deployments': 'gcp',
        'terragrunt-deployments': 'terragrunt',
        'helm-deployments': 'helm',
        'ansible-deployments': 'ansible',
        'starlingx-deployments': 'starlingx',
        'vsphere-deployments': 'vsphere',
        'docker-deployments': 'docker',
        'netconf-deployments': 'netconf',
        'fabric-deployments': 'fabric',
        'libvirt-deployments': 'libvirt',
        'utilities-deployments': 'utilities',
        'host-pool-deployments': 'host-pool',
        'diamond-deployments': 'diamond',
        'openstack-deployments': 'openstack',
        'openstack-v3-deployments': 'openstack-v3',
        'vcloud-deployments': 'vcloud',
    }.items():
        if filter_id in curr_dep_filters_ids:
            continue
        service_filter = {
            'id': filter_id,
            'value': [
                {
                    'key': 'obj-type',
                    'values': [obj_type_value],
                    'operator': 'any_of',
                    'type': 'label',
                }
            ]
        }
        _add_deployments_filter(service_filter, creator, tenant, now)


def _add_deployments_filter(sys_filter_dict, creator, tenant, now):
    sys_filter_dict['created_at'] = now
    sys_filter_dict['updated_at'] = now
    sys_filter_dict['visibility'] = 'global'
    sys_filter_dict['is_system_filter'] = True
    sys_filter_dict['creator'] = creator
    sys_filter_dict['tenant'] = tenant
    db.session.add(models.DeploymentsFilter(**sys_filter_dict))


def _generate_db_config_entries(cfg):
    manager_private_ip = cfg['manager'].get('private_ip', 'localhost')
    default_file_server_url = f'https://{ipv6_url_compat(manager_private_ip)}'\
                              f':{DEFAULT_INTERNAL_REST_PORT}/resources'

    prometheus_cfg = cfg.get('prometheus', {})
    rest_cfg = {
        'rest_service_log_path': REST_LOG_DIR + '/cloudify-rest-service.log',
        'rest_service_log_level': cfg['restservice']['log']['level'],
        'file_server_root': cfg['manager'].get('file_server_root',
                                               DEFAULT_FILE_SERVER_ROOT),
        'file_server_url': cfg['manager'].get('file_server_url',
                                              default_file_server_url),
        'insecure_endpoints_disabled':
            cfg['restservice']['insecure_endpoints_disabled'],
        'maintenance_folder': REST_HOME_DIR + '/maintenance',
        'min_available_memory_mb':
            cfg['restservice']['min_available_memory_mb'],
        'failed_logins_before_account_lock':
            cfg['restservice']['failed_logins_before_account_lock'],
        'account_lock_period': cfg['restservice']['account_lock_period'],
        'public_ip': cfg['manager']['public_ip'],
        'default_page_size': cfg['restservice']['default_page_size'],
        'monitoring_timeout': prometheus_cfg.get('request_timeout', 4),
        'log_fetch_username': prometheus_cfg.get('credentials', {}).get(
            'username'),
        'log_fetch_password': prometheus_cfg.get('credentials', {}).get(
            'password'),
    }
    mgmtworker_cfg = {
        'max_workers': cfg['mgmtworker']['max_workers'],
        'min_workers': cfg['mgmtworker']['min_workers'],
    }
    agent_cfg = {
        'min_workers': cfg['agent']['min_workers'],
        'max_workers': cfg['agent']['max_workers'],
        'broker_port': cfg['agent']['broker_port'],
        'heartbeat': cfg['agent']['heartbeat'],
        'log_level': cfg['agent']['log_level']
    }
    workflow_cfg = cfg['mgmtworker']['workflows']
    return [  # (scope, {name: value})
        ('mgmtworker', mgmtworker_cfg),
        ('workflow', workflow_cfg),
        ('agent', agent_cfg),
        ('rest', rest_cfg)
    ]


def _populate_config_in_db(cfg):
    config_for_db = _generate_db_config_entries(cfg)
    for scope, entries in config_for_db:
        for name, value in entries.items():
            inst = db.session.get(
                models.Config,
                {'name': name, 'scope': scope}
            )
            inst.value = value


def configure(user_config):
    """Configure the manager based on the provided config"""
    _populate_config_in_db(user_config)
    _register_rabbitmq_brokers(user_config)

    default_tenant = _get_default_tenant()
    if not default_tenant:
        default_tenant = _create_default_tenant()

    _create_roles(user_config)
    _create_permissions(user_config)

    admin_user = user_datastore.get_user(constants.BOOTSTRAP_ADMIN_ID)
    if admin_user:
        _update_admin_user(admin_user, user_config)
    else:
        admin_user = _create_admin_user(user_config)

    _setup_user_tenant_assoc(admin_user, default_tenant)

    _create_provider_context(user_config)

    _insert_manager(user_config)

    create_system_filters()

    db.session.commit()


def _load_user_config(paths):
    """Load and merge the config files provided by paths"""
    user_config = {}
    for config_path in paths:
        if not config_path:
            continue
        try:
            with open(config_path) as f:
                config_source = yaml.safe_load(f)
        except FileNotFoundError:
            continue
        dict_merge(user_config, config_source)
    return user_config


def _create_admin_token(target):
    description = 'csys-mgmtworker'
    # Don't leak existing Mgmtworker tokens
    db.session.execute(
        models.Token.__table__
        .delete()
        .filter_by(description=description)
    )
    admin_user = user_datastore.get_user(constants.BOOTSTRAP_ADMIN_ID)
    token = admin_user.create_auth_token(description=description)
    db.session.add(token)
    db.session.commit()
    with open(target, 'w') as f:
        f.write(token.value)


def _wait_for_db(address):
    while True:
        try:
            with socket.create_connection((address, 5432), timeout=5):
                return 0
        except socket.error:
            logging.error('Still waiting for DB: %s', address)
            time.sleep(1)


def _wait_for_rabbitmq(address):
    while True:
        try:
            with socket.create_connection((address, 15671), timeout=5):
                return 0
        except socket.error:
            logging.error('Still waiting for rabbitmq: %s', address)
            time.sleep(1)


if __name__ == '__main__':
    logging.basicConfig()

    parser = argparse.ArgumentParser(description='Create admin user in DB')
    parser.add_argument(
        '-c',
        '--config-file-path',
        help='Path to a config file containing info needed by this script',
        action='append',
        required=False,
    )
    parser.add_argument(
        '--db-wait',
        help='Wait for this DB to be up, and exit',
        required=False
    )
    parser.add_argument(
        '--rabbitmq-wait',
        help='Wait for this RabbitMQ to be up, and exit',
        required=False
    )
    parser.add_argument(
        '--create-admin-token',
        help='Create admin token at this location',
        required=False
    )
    args = parser.parse_args()

    if args.db_wait:
        sys.exit(_wait_for_db(args.db_wait))
    if args.rabbitmq_wait:
        sys.exit(_wait_for_rabbitmq(args.rabbitmq_wait))

    config.instance.load_configuration(from_db=False)
    with setup_flask_app().app_context():
        user_config = _load_user_config(args.config_file_path)
        config.instance.load_from_db(session=db.session)
        configure(user_config)
        if args.create_admin_token:
            _create_admin_token(args.create_admin_token)
