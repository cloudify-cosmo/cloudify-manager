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


class Config(object):

    def __init__(self):
        self.db_address = 'localhost'
        self.db_port = 9200
        self.postgresql_db_name = None
        self.postgresql_host = None
        self.postgresql_username = None
        self.postgresql_password = None
        self.postgresql_bin_path = None
        self.amqp_address = 'localhost'
        self.amqp_username = 'guest'
        self.amqp_password = 'guest'
        self.amqp_ssl_enabled = False
        self.amqp_ca_path = ''
        self.ldap_server = None
        self.ldap_username = None
        self.ldap_password = None
        self.ldap_domain = None
        self.ldap_is_active_directory = True
        self.ldap_dn_extra = {}
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
        self.min_available_memory_mb = 256

        self.security_hash_salt = None
        self.security_secret_key = None
        self.security_encoding_alphabet = None
        self.security_encoding_block_size = None
        self.security_encoding_min_length = None

        self.warnings = []

    def load_configuration(self):
        self._load_config('MANAGER_REST_CONFIG_PATH')
        self._load_config('MANAGER_REST_SECURITY_CONFIG_PATH', 'security')

    def _load_config(self, env_var_name, namespace=''):
        if env_var_name in os.environ:
            with open(os.environ[env_var_name]) as f:
                yaml_conf = yaml.safe_load(f.read())
            for key, value in yaml_conf.iteritems():
                config_key = '{0}_{1}'.format(namespace, key) if namespace \
                    else key
                if hasattr(self, config_key):
                    setattr(self, config_key, value)
                else:
                    self.warnings.append(
                        "Ignoring unknown key '{0}' in configuration file "
                        "'{1}'".format(key, os.environ[env_var_name]))


instance = Config()


def reset(configuration=None, write=False):
    global instance
    instance = configuration
    if write:
        with open(os.environ['MANAGER_REST_CONFIG_PATH'], 'w') as f:
            if instance:
                yaml.safe_dump(instance.__dict__, f, default_flow_style=False)
            else:
                yaml.safe_dump({}, f)
