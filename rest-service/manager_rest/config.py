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

import os
import yaml

from json import dump


CONFIG_TYPES = [
    ('MANAGER_REST_CONFIG_PATH', ''),
    ('MANAGER_REST_SECURITY_CONFIG_PATH', 'security'),
    ('MANAGER_REST_AUTHORIZATION_CONFIG_PATH', 'authorization')
]
SKIP_RESET_WRITE = ['authorization']
NOT_SET = object()


class Setting(object):
    def __init__(self, name, default=NOT_SET, from_db=True):
        self._name = name
        self._value = default
        self._from_db = from_db

    def __get__(self, instance, owner):
        if self._value is NOT_SET:
            if self._from_db:
                instance.load_from_db()
            else:
                raise AttributeError('Setting {0} is not set'
                                     .format(self._name))
        return self._value

    def __set__(self, instance, value):
        self._value = value

    def __delete__(self, instance):
        self._value = NOT_SET


class Config(object):
    public_ip = Setting('public_ip')

    # database settings
    postgresql_db_name = Setting('postgresql_db_name', from_db=False)
    postgresql_host = Setting('postgresql_host', from_db=False)
    postgresql_username = Setting('postgresql_username', from_db=False)
    postgresql_password = Setting('postgresql_password', from_db=False)
    postgresql_bin_path = Setting('postgresql_bin_path', from_db=False)
    postgresql_ssl_enabled = Setting('postgresql_ssl_enabled',
                                     default=False, from_db=False)
    postgresql_ssl_cert_path = Setting('postgresql_ssl_cert_path',
                                       from_db=False)
    postgresql_ssl_key_path = Setting('postgresql_ssl_key_path', from_db=False)
    postgresql_connection_options = Setting('postgresql_connection_options',
                                            default={'connect_timeout': 10},
                                            from_db=False)

    ca_cert_path = Setting('ca_cert_path')

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
    ldap_dn_extra = Setting('ldap_dn_extra')
    ldap_timeout = Setting('ldap_timeout')

    file_server_root = Setting('file_server_root')
    file_server_url = Setting('file_server_url')

    maintenance_folder = Setting('maintenance_folder')
    rest_service_log_level = Setting('rest_service_log_level')
    rest_service_log_path = Setting('rest_service_log_path')

    rest_service_log_file_size_MB = Setting('rest_service_log_file_size_MB')
    rest_service_log_files_backup_count = Setting(
        'rest_service_log_files_backup_count')

    test_mode = Setting('test_mode', default=False)

    insecure_endpoints_disabled = Setting('insecure_endpoints_disabled')
    default_page_size = Setting('default_page_size', default=1000)
    min_available_memory_mb = Setting('min_available_memory_mb')

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
        'failed_logins_before_account_lock')
    account_lock_period = Setting('account_lock_period')

    # max number of threads that will be used in a `restore snapshot` wf
    snapshot_restore_threads = Setting('snapshot_restore_threads', default=15)

    warnings = Setting('warnings', default=[])

    def load_configuration(self):
        for env_var_name, namespace in CONFIG_TYPES:
            if env_var_name in os.environ:
                self.load_from_file(os.environ[env_var_name], namespace)

    def load_from_file(self, filename, namespace=''):
        with open(filename) as f:
            yaml_conf = yaml.safe_load(f.read())
        for key, value in yaml_conf.iteritems():
            config_key = '{0}_{1}'.format(namespace, key) if namespace \
                else key
            if hasattr(self, config_key):
                setattr(self, config_key, value)
            else:
                self.warnings.append(
                    "Ignoring unknown key '{0}' in configuration file "
                    "'{1}'".format(key, filename))

    def load_from_db(self):
        from manager_rest.storage import models, get_storage_manager
        self.min_available_memory_mb = 0
        sm = get_storage_manager()
        stored_config = sm.list(models.Config, filters={
            'scope': lambda column: column.contains(['rest'])
        })
        for conf_value in stored_config:
            setattr(self, conf_value.name, conf_value.value)

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
