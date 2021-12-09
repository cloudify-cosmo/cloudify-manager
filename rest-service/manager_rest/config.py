import atexit
import itertools
import jsonschema
import os
import requests
import tempfile
import time
import yaml

from json import dump
from datetime import datetime
from flask_security import current_user
from flask import current_app
from sqlalchemy import create_engine, orm

from cloudify._compat import text_type
from cloudify.utils import ipv6_url_compat

from manager_rest.manager_exceptions import (
    ConflictError,
    AmbiguousName,
    NotFoundError
)

CONFIG_TYPES = [
    ('MANAGER_REST_CONFIG_PATH', ''),
    ('MANAGER_REST_SECURITY_CONFIG_PATH', 'security'),
]
SKIP_RESET_WRITE = ['authorization']
NOT_SET = object()
SQL_DIALECT = 'postgresql'
SQL_ASYNC_DIALECT = 'postgresql+asyncpg'
LDAP_CA_NAME = '_auth-ldap-ca'


class Setting(object):
    def __init__(self, name, default=NOT_SET, from_db=True):
        self._name = name
        self._value = default
        self._from_db = from_db

    def __get__(self, instance, owner):
        if self._value is NOT_SET:
            if self._from_db and instance.can_load_from_db:
                instance.load_from_db()
            else:
                self._value = None
        return self._value

    def __set__(self, instance, value):
        self._value = value

    def __delete__(self, instance):
        self._value = NOT_SET


class Config(object):
    # whether or not the config can be implicitly loaded from db on first use
    can_load_from_db = True

    # when was the config last changed? it will be reloaded when this increases
    last_updated = None

    service_management = Setting('service_management', default='systemd')

    public_ip = Setting('public_ip')
    manager_hostname = Setting('manager_hostname', from_db=False)

    # database settings
    postgresql_db_name = Setting('postgresql_db_name', from_db=False)
    postgresql_host = Setting('postgresql_host', from_db=False)
    postgresql_username = Setting('postgresql_username', from_db=False)
    postgresql_password = Setting('postgresql_password', from_db=False)
    postgresql_bin_path = Setting('postgresql_bin_path', default=None,
                                  from_db=False)
    postgresql_ssl_enabled = Setting('postgresql_ssl_enabled',
                                     default=False, from_db=False)
    postgresql_ssl_client_verification = \
        Setting('postgresql_ssl_client_verification', default=False,
                from_db=False)
    postgresql_ssl_cert_path = Setting('postgresql_ssl_cert_path',
                                       from_db=False)
    postgresql_ssl_key_path = Setting('postgresql_ssl_key_path', from_db=False)
    postgresql_ca_cert_path = Setting('postgresql_ca_cert_path', from_db=False)
    postgresql_connection_options = Setting('postgresql_connection_options',
                                            default={'connect_timeout': 10},
                                            from_db=False)

    ca_cert_path = Setting('ca_cert_path', from_db=False)

    # rabbitmq settings
    amqp_host = Setting('amqp_host', from_db=False)
    amqp_management_host = Setting('amqp_management_host', from_db=False)
    amqp_username = Setting('amqp_username', from_db=False)
    amqp_password = Setting('amqp_password', from_db=False)
    amqp_ca_path = Setting('amqp_ca_path', from_db=False)

    # LDAP settings
    ldap_server = Setting('ldap_server')
    ldap_username = Setting('ldap_username')
    ldap_password = Setting('ldap_password')
    ldap_domain = Setting('ldap_domain')
    ldap_is_active_directory = Setting('ldap_is_active_directory')
    ldap_timeout = Setting('ldap_timeout')
    ldap_ca_cert = Setting('ldap_ca_cert')
    ldap_bind_format = Setting('ldap_bind_format')
    ldap_nested_levels = Setting('ldap_nested_levels', default=1)
    # LDAP search filter and similar settings
    ldap_dn_extra = Setting('ldap_dn_extra')
    ldap_group_dn = Setting('ldap_group_dn')
    ldap_base_dn = Setting('ldap_base_dn')
    ldap_group_member_filter = Setting('ldap_group_member_filter')
    ldap_user_filter = Setting('ldap_user_filter')
    # Attributes on user objects
    ldap_attribute_email = Setting('ldap_attribute_email')
    ldap_attribute_first_name = Setting('ldap_attribute_first_name')
    ldap_attribute_last_name = Setting('ldap_attribute_last_name')
    ldap_attribute_uid = Setting('ldap_attribute_uid')
    ldap_attribute_group_membership = Setting(
        'ldap_attribute_group_membership')

    file_server_root = Setting('file_server_root', default=None)
    file_server_url = Setting('file_server_url', default=None)

    maintenance_folder = Setting('maintenance_folder')
    rest_service_log_level = Setting('rest_service_log_level')
    rest_service_log_path = Setting('rest_service_log_path')
    api_service_log_level = Setting('api_service_log_level')
    api_service_log_path = Setting('api_service_log_path')

    rest_service_log_file_size_MB = Setting('rest_service_log_file_size_MB')
    rest_service_log_files_backup_count = Setting(
        'rest_service_log_files_backup_count')

    monitoring_timeout = Setting('monitoring_timeout')

    test_mode = Setting('test_mode', default=False)

    insecure_endpoints_disabled = Setting('insecure_endpoints_disabled')
    default_page_size = Setting('default_page_size', default=1000)
    min_available_memory_mb = Setting('min_available_memory_mb', default=0)

    # security settings
    security_hash_salt = Setting('security_hash_salt', from_db=False)
    security_secret_key = Setting('security_secret_key', from_db=False)
    security_encoding_alphabet = Setting('security_encoding_alphabet',
                                         from_db=False)
    security_encoding_block_size = Setting('security_encoding_block_size',
                                           from_db=False)
    security_encoding_min_length = Setting('security_encoding_min_length',
                                           from_db=False)
    security_encryption_key = Setting('security_encryption_key', from_db=False)

    authorization_roles = Setting('authorization_roles',
                                  from_db=False, default=None)
    authorization_permissions = Setting('authorization_permissions',
                                        from_db=False, default=None)

    failed_logins_before_account_lock = Setting(
        'failed_logins_before_account_lock', default=4)
    account_lock_period = Setting('account_lock_period')

    # max number of threads that will be used in a `restore snapshot` wf
    snapshot_restore_threads = Setting('snapshot_restore_threads', default=15)
    max_concurrent_workflows = Setting('max_concurrent_workflows', default=20)
    warnings = Setting('warnings', default=[])

    _logger = None

    def load_configuration(self, from_db=True):
        for env_var_name, namespace in CONFIG_TYPES:
            if env_var_name in os.environ:
                self.load_from_file(os.environ[env_var_name], namespace)
        if from_db:
            self.load_from_db()

    def load_from_file(self, filename, namespace=''):
        with open(filename) as f:
            yaml_conf = yaml.safe_load(f.read())
        for key, value in yaml_conf.items():
            config_key = '{0}_{1}'.format(namespace, key) if namespace \
                else key
            if hasattr(self, config_key):
                setattr(self, config_key, value)
            else:
                self.warnings.append(
                    "Ignoring unknown key '{0}' in configuration file "
                    "'{1}'".format(key, filename))

    @property
    def logger(self):
        if not self._logger:
            self._logger = current_app.logger
        return self._logger

    @logger.setter
    def logger(self, logger):
        self._logger = logger

    def load_from_db(self):
        from manager_rest.storage import models
        last_changed = {self.last_updated}
        engine = create_engine(self.db_url)
        session = orm.Session(bind=engine)
        stored_config = (
            session.query(models.Config)
            .all()
        )
        for conf_value in stored_config:
            last_changed.add(conf_value.updated_at)
            if conf_value.scope != 'rest':
                continue
            setattr(self, conf_value.name, conf_value.value)

        stored_brokers = session.query(
            models.RabbitMQBroker.host,
            models.RabbitMQBroker.management_host,
            models.RabbitMQBroker.username,
            models.RabbitMQBroker.password,
            models.Certificate.value.label('ca_cert_value')
        ).join(models.Certificate).all()

        self.amqp_host = [b.host for b in stored_brokers]
        self.amqp_management_host = [b.management_host for b in stored_brokers]

        # all brokers will use the same credentials and ca cert
        # (rabbitmq replicates users)
        for broker in stored_brokers:
            self.amqp_username = broker.username
            self.amqp_password = broker.password
        if stored_brokers:
            with tempfile.NamedTemporaryFile(delete=False, mode='w') as f:
                f.write(stored_brokers[0].ca_cert_value)
            self.amqp_ca_path = f.name
            atexit.register(os.unlink, self.amqp_ca_path)

        stored_roles = session.query(
            models.Role.id,
            models.Role.name,
            models.Role.type,
            models.Role.description,
            models.Role.updated_at
        ).all()
        role_names = {r.id: r.name for r in stored_roles}
        last_changed |= {r.updated_at for r in stored_roles}
        stored_permissions = session.query(
            models.Permission.id,
            models.Permission.role_id,
            models.Permission.name
        ).all()
        self.authorization_roles = [
            {'id': r.id, 'name': r.name, 'type': r.type,
             'description': r.description}
            for r in stored_roles
        ]
        self.authorization_permissions = {}
        for perm in stored_permissions:
            if perm.name not in self.authorization_permissions:
                self.authorization_permissions[perm.name] = []
            self.authorization_permissions[perm.name].append(
                role_names[perm.role_id])

        self.ldap_ca_cert = session.query(
            models.Certificate.value
        ).filter_by(name=LDAP_CA_NAME).scalar()

        session.close()
        engine.dispose()

        self.last_updated = max((dt for dt in last_changed if dt),
                                default=None)
        # disallow implicit loading
        self.can_load_from_db = False

    def update_db(self, config_dict, force=False):
        """
        Update the config table in the DB with values passed in the
        config dictionary parameter
        """
        from manager_rest.storage import models

        engine = create_engine(self.db_url)
        session = orm.Session(bind=engine)
        stored_configs = session.query(models.Config).all()

        config_mappings = []
        for name, value in config_dict.items():
            if name == 'ldap_ca_cert':
                cert = session.query(models.Certificate).filter_by(
                    name=LDAP_CA_NAME,
                ).one_or_none() or models.Certificate()
                cert.name = LDAP_CA_NAME
                cert.value = value
                session.add(cert)
                continue
            entry = self._find_entry(stored_configs, name)
            if not entry.is_editable and not force:
                raise ConflictError('{0} is not editable'.format(entry.name))
            if entry.schema:
                if entry.schema['type'] == 'number':
                    try:
                        value = float(value)
                    except ValueError:
                        raise ConflictError(
                            f'Error validating {name}: {value} is not '
                            f'a number')
                elif entry.schema['type'] == 'integer':
                    try:
                        value = int(value)
                    except ValueError:
                        raise ConflictError(
                            f'Error validating {name}: {value} is not '
                            f'an integer')
                elif entry.schema['type'] == 'boolean'\
                        and isinstance(value, text_type):
                    if value.lower() == 'true':
                        value = True
                    elif value.lower() == 'false':
                        value = False
                    else:
                        raise ConflictError(
                            f'Error validating {name}: must be <true/false>, '
                            f'got {value}')
                try:
                    jsonschema.validate(value, entry.schema)
                except jsonschema.ValidationError as e:
                    raise ConflictError(
                        f'Error validating {name}: {e.args[0]}')
            config_mappings.append({
                'name': entry.name,
                'scope': entry.scope,
                'value': value,
                'updated_at': datetime.utcnow(),
                '_updater_id': current_user.id,
            })
        session.bulk_update_mappings(models.Config, config_mappings)
        session.commit()
        session.close()
        engine.dispose()

        for name, value in config_dict.items():
            setattr(self, name, value)

    def _find_entry(self, entries, name):
        """In entries, find one that matches the name.

        Name can be prefixed with scope, in the format of "scope.name".
        There must be only one matching entry.
        """
        scope, _, name = name.rpartition('.')
        matching_entries = [
            entry for entry in entries
            if entry.name == name and
            (not scope or entry.scope == scope)]
        if not matching_entries:
            raise NotFoundError(name)
        if len(matching_entries) != 1:
            raise AmbiguousName(
                'Expected 1 value, but found {0}'
                .format(len(matching_entries)))
        return matching_entries[0]

    @property
    def db_url(self):
        host = self._find_db_host(self.postgresql_host)
        params = {}
        params.update(self.postgresql_connection_options)
        if self.postgresql_ssl_enabled:
            ssl_mode = 'verify-full'
            if self.postgresql_ssl_client_verification:
                params.update({
                    'sslcert': self.postgresql_ssl_cert_path,
                    'sslkey': self.postgresql_ssl_key_path,
                })
            params.update({
                'sslmode': ssl_mode,
                'sslrootcert': self.postgresql_ca_cert_path
            })

        db_url = '{dialect}://{username}:{password}@{host}/{db_name}'.format(
            dialect=SQL_DIALECT,
            username=self.postgresql_username,
            password=self.postgresql_password,
            host=ipv6_url_compat(host),
            db_name=self.postgresql_db_name
        )
        if any(params.values()):
            query = '&'.join('{0}={1}'.format(key, value)
                             for key, value in params.items()
                             if value)
            db_url = '{0}?{1}'.format(db_url, query)
        return db_url

    @property
    def sqlalchemy_async_dsn(self):
        dsn = self.asyncpg_dsn
        if not dsn.startswith(SQL_DIALECT):
            return dsn
        _, _, dsn = dsn.partition(SQL_DIALECT)
        return f'{SQL_ASYNC_DIALECT}{dsn}'

    @property
    def asyncpg_dsn(self):
        host = ipv6_url_compat(self._find_db_host(self.postgresql_host))
        dsn = f'{SQL_DIALECT}://'\
              f'{self.postgresql_username}:'\
              f'{self.postgresql_password}@'\
              f'{host}/'\
              f'{self.postgresql_db_name}'
        params = {}
        if self.postgresql_ssl_enabled:
            if self.postgresql_ssl_client_verification:
                params.update({
                    'sslcert': self.postgresql_ssl_cert_path,
                    'sslkey': self.postgresql_ssl_key_path,
                })
            params.update({
                'sslmode': 'vefify-full',
                'sslrootcert': self.postgresql_ca_cert_path,
            })
        if any(params.values()):
            query_string = '&'.join(f'{k}={v}' for k, v in params.items() if v)
            dsn = f'{dsn}?{query_string}'
        return dsn

    @property
    def db_host(self):
        # This is only to make cluster snapshots work
        # Don't use it for anything else, it wants removing once snapshots
        # improve.
        return self._find_db_host(self.postgresql_host)

    def _find_db_host(self, postgresql_host):
        if not isinstance(postgresql_host, list):
            return postgresql_host

        for i, candidate in enumerate(itertools.cycle(postgresql_host)):
            try:
                result = requests.get(
                    'https://{}:8008'.format(ipv6_url_compat(candidate)),
                    verify=self.postgresql_ca_cert_path,
                    timeout=5,
                )
            except Exception as err:
                self.logger.error(
                    'Error trying to get state of DB %s: %s', candidate, err)
                continue

            self.logger.debug(
                'Checking DB for leader selection. %s has status %s',
                candidate,
                result.status_code,
            )
            if result.status_code == 200:
                self.logger.debug('Selected %s as DB leader', candidate)
                return candidate

            if i and i % len(postgresql_host) == 0:
                # No DB found after trying all once, wait before trying again
                time.sleep(1)

    def to_dict(self):
        config_dict = vars(self)
        insecure_keys = {
            'security_hash_salt',
            'security_secret_key',
            'security_encoding_alphabet',
            'security_encoding_block_size',
            'security_encoding_min_length',
            'security_encryption_key',
            'authorization_roles',
            'authorization_permissions',
            'failed_logins_before_account_lock',
            'account_lock_period',
            'warnings'
        }
        return {key: config_dict[key] for key in config_dict
                if key not in insecure_keys}


instance = Config()


def reset(configuration=None, write=False):
    global instance
    instance = configuration
    if not write:
        return

    configs = {}
    config = vars(instance)
    for key in config:
        conf_type = ''
        for env_var_name, namespace in CONFIG_TYPES:
            if key.startswith(namespace) and len(namespace) >= len(conf_type):
                conf_type = namespace
        file_key = key[len(conf_type) + 1:] if conf_type else key
        configs.setdefault(conf_type, {})[file_key] = config[key]

    for config_file_env_var, namespace in CONFIG_TYPES:
        if namespace in SKIP_RESET_WRITE:
            continue
        with open(os.environ[config_file_env_var], 'w') as f:
            if namespace in configs and configs[namespace]:
                dump(configs[namespace], f, indent=4)
            else:
                dump({}, f)
