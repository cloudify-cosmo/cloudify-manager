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
        self._db_address = 'localhost'
        self._db_port = 9200
        self._amqp_address = 'localhost'
        self.amqp_username = 'guest'
        self.amqp_password = 'guest'
        self.amqp_ssl_enabled = False
        self.amqp_ca_path = ''
        self._file_server_root = None
        self._file_server_base_uri = None
        self._file_server_blueprints_folder = None
        self._file_server_uploaded_blueprints_folder = None
        self._file_server_resources_uri = None
        self._rest_service_log_level = None
        self._rest_service_log_path = None
        self._rest_service_log_file_size_MB = None
        self._rest_service_log_files_backup_count = None
        self._test_mode = False
        self._security_enabled = False
        self._security_ssl = {'enabled': False}
        self._security_admin_username = None
        self._security_admin_password = None
        self._security_auth_token_generator = None
        self._security_audit_log_level = None
        self._security_audit_log_file = None
        self._security_audit_log_file_size_MB = None
        self._security_audit_log_files_backup_count = None
        self._security_userstore_driver = None
        self._security_authentication_providers = []
        self._security_authorization_provider = None

    @property
    def db_address(self):
        return self._db_address

    @db_address.setter
    def db_address(self, value):
        self._db_address = value

    @property
    def db_port(self):
        return self._db_port

    @db_port.setter
    def db_port(self, value):
        self._db_port = value

    @property
    def amqp_address(self):
        return self._amqp_address

    @amqp_address.setter
    def amqp_address(self, value):
        self._amqp_address = value

    @property
    def file_server_root(self):
        return self._file_server_root

    @file_server_root.setter
    def file_server_root(self, value):
        self._file_server_root = value

    @property
    def file_server_base_uri(self):
        return self._file_server_base_uri

    @file_server_base_uri.setter
    def file_server_base_uri(self, value):
        self._file_server_base_uri = value

    @property
    def file_server_blueprints_folder(self):
        return self._file_server_blueprints_folder

    @file_server_blueprints_folder.setter
    def file_server_blueprints_folder(self, value):
        self._file_server_blueprints_folder = value

    @property
    def file_server_uploaded_blueprints_folder(self):
        return self._file_server_uploaded_blueprints_folder

    @file_server_uploaded_blueprints_folder.setter
    def file_server_uploaded_blueprints_folder(self, value):
        self._file_server_uploaded_blueprints_folder = value

    @property
    def file_server_resources_uri(self):
        return self._file_server_resources_uri

    @file_server_resources_uri.setter
    def file_server_resources_uri(self, value):
        self._file_server_resources_uri = value

    @property
    def rest_service_log_path(self):
        return self._rest_service_log_path

    @rest_service_log_path.setter
    def rest_service_log_path(self, value):
        self._rest_service_log_path = value

    @property
    def rest_service_log_level(self):
        return self._rest_service_log_level

    @rest_service_log_level.setter
    def rest_service_log_level(self, value):
        self._rest_service_log_level = value

    @property
    def rest_service_log_file_size_MB(self):
        return self._rest_service_log_file_size_MB

    @rest_service_log_file_size_MB.setter
    def rest_service_log_file_size_MB(self, value):
        self._rest_service_log_file_size_MB = value

    @property
    def rest_service_log_files_backup_count(self):
        return self._rest_service_log_files_backup_count

    @rest_service_log_files_backup_count.setter
    def rest_service_log_files_backup_count(self, value):
        self._rest_service_log_files_backup_count = value

    @property
    def test_mode(self):
        return self._test_mode

    @test_mode.setter
    def test_mode(self, value):
        self._test_mode = value

    @property
    def security_enabled(self):
        return self._security_enabled

    @security_enabled.setter
    def security_enabled(self, value):
        self._security_enabled = value

    @property
    def security_ssl(self):
        return self._security_ssl

    @security_ssl.setter
    def security_ssl(self, value):
        self._security_ssl = value

    @property
    def security_admin_username(self):
        return self._security_admin_username

    @security_admin_username.setter
    def security_admin_username(self, value):
        self._security_admin_username = value

    @property
    def security_admin_password(self):
        return self._security_admin_password

    @security_admin_password.setter
    def security_admin_password(self, value):
        self._security_admin_password = value

    @property
    def security_authentication_providers(self):
        return self._security_authentication_providers

    @security_authentication_providers.setter
    def security_authentication_providers(self, value):
        self._security_authentication_providers = value

    @property
    def security_auth_token_generator(self):
        return self._security_auth_token_generator

    @security_auth_token_generator.setter
    def security_auth_token_generator(self, value):
        self._security_auth_token_generator = value

    @property
    def security_audit_log_level(self):
        return self._security_audit_log_level

    @security_audit_log_level.setter
    def security_audit_log_level(self, value):
        self._security_audit_log_level = value

    @property
    def file_server_uploaded_plugins_folder(self):
        if not self._file_server_root:
            return None
        return os.path.join(self._file_server_root, 'plugins')

    @property
    def security_audit_log_file(self):
        return self._security_audit_log_file

    @security_audit_log_file.setter
    def security_audit_log_file(self, value):
        self._security_audit_log_file = value

    @property
    def security_audit_log_file_size_MB(self):
        return self._security_audit_log_file_size_MB

    @security_audit_log_file_size_MB.setter
    def security_audit_log_file_size_MB(self, value):
        self._security_audit_log_file_size_MB = value

    @property
    def security_audit_log_files_backup_count(self):
        return self._security_audit_log_files_backup_count

    @security_audit_log_files_backup_count.setter
    def security_audit_log_files_backup_count(self, value):
        self._security_audit_log_files_backup_count = value

    @property
    def security_userstore_driver(self):
        return self._security_userstore_driver

    @security_userstore_driver.setter
    def security_userstore_driver(self, value):
        self._security_userstore_driver = value

    @property
    def security_authorization_provider(self):
        return self._security_authorization_provider

    @security_authorization_provider.setter
    def security_authorization_provider(self, value):
        self._security_authorization_provider = value


_instance = Config()


def reset(configuration=None):
    global _instance
    if configuration is not None:
        _instance = configuration
    else:
        _instance = Config()


def instance():
    return _instance
