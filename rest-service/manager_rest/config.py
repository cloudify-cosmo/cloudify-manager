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


class Config(object):

    def __init__(self):
        self.db_address = 'localhost'
        self.db_port = 9200
        self.postgresql_db_name = None
        self.postgresql_host = None
        self.postgresql_username = None
        self.postgresql_password = None
        self.postgresql_bin_path = None
        self.amqp_host = 'localhost'
        self.amqp_management_host = 'localhost'
        self.amqp_username = 'guest'
        self.amqp_password = 'guest'
        self.amqp_ca_path = ''
        self.ldap_server = None
        self.ldap_username = None
        self.ldap_password = None
        self.ldap_domain = None
        self.ldap_is_active_directory = True
        self.ldap_dn_extra = {}
        self.ldap_timeout = 5.0
        self.file_server_root = None
        self.file_server_url = None
        self.maintenance_folder = None
        self.rest_service_log_level = None
        self.rest_service_log_path = None
        self.rest_service_log_file_size_MB = None
        self.rest_service_log_files_backup_count = None
        self.test_mode = False
        self.insecure_endpoints_disabled = True
        self.max_results = 1000
        self.min_available_memory_mb = None

        self.security_hash_salt = None
        self.security_secret_key = None
        self.security_encoding_alphabet = None
        self.security_encoding_block_size = None
        self.security_encoding_min_length = None
        self.security_encryption_key = None

        self.authorization_roles = None
        self.authorization_permissions = None

        self.failed_logins_before_account_lock = 4
        self.account_lock_period = -1

        # max number of threads that will be used in a `restore snapshot` wf
        self.snapshot_restore_threads = 15

        self.warnings = []

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
