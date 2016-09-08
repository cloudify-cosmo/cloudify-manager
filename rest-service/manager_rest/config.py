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
        self.file_server_root = None
        self.file_server_base_uri = None
        self.file_server_blueprints_folder = None
        self.file_server_deployments_folder = None
        self.file_server_uploaded_blueprints_folder = None
        self.file_server_snapshots_folder = None
        self.file_server_resources_uri = None
        self.maintenance_folder = None
        self.rest_service_log_level = None
        self.rest_service_log_path = None
        self.rest_service_log_file_size_MB = None
        self.rest_service_log_files_backup_count = None
        self.test_mode = False
        self.security_enabled = False
        self.security_ssl = {'enabled': False}
        self.security_auth_token_generator = None
        self.security_audit_log_level = None
        self.security_audit_log_file = None
        self.security_audit_log_file_size_MB = None
        self.security_audit_log_files_backup_count = None
        self.security_userstore_driver = None
        self.security_authentication_providers = []
        self.security_authorization_provider = None
        self.insecure_endpoints_disabled = False
        self.security_rest_username = None
        self.security_rest_password = None

    @property
    def file_server_uploaded_plugins_folder(self):
        if not self.file_server_root:
            return None
        return os.path.join(self.file_server_root, 'plugins')

_instance = Config()


def reset(configuration=None):
    global _instance
    if configuration is not None:
        _instance = configuration
    else:
        _instance = Config()


def instance():
    return _instance
