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
import json

import unittest
import tempfile

from mock import MagicMock
from nose.plugins.attrib import attr

from manager_rest import (
    config,
    constants,
    utils
)
from manager_rest.storage import (
    models,
    get_storage_manager,
)

from manager_rest.test.security_utils import get_admin_user

LATEST_API_VERSION = 3  # to be used by max_client_version test attribute


@attr(client_min_version=1, client_max_version=LATEST_API_VERSION)
class ModelsIntegrationTestsBase(unittest.TestCase):
    def setUp(self):
        rest_service_log, tmp_conf_file = self._create_temp_files_and_folders()
        self.server = self._set_config_path_and_get_server_module(rest_service_log, tmp_conf_file)
        self.server_configuration = self._create_config_and_reset_app(rest_service_log)
        self._set_flask_app_context()
        self.sm = get_storage_manager()

    def _create_config_and_reset_app(self, rest_service_log):
        """Create config, and reset Flask app
        :type server: module
        """
        server_configuration = self._create_configuration(rest_service_log)
        self.server.SQL_DIALECT = 'sqlite'
        self.server.reset_app(server_configuration)
        return server_configuration

    @staticmethod
    def _create_configuration(rest_service_log):
        test_config = config.Config()
        test_config.test_mode = True
        test_config.postgresql_db_name = ':memory:'
        test_config.postgresql_host = ''
        test_config.postgresql_username = ''
        test_config.postgresql_password = ''
        test_config.default_tenant_name = constants.DEFAULT_TENANT_NAME
        test_config.rest_service_log_level = 'DEBUG'
        test_config.rest_service_log_path = rest_service_log
        test_config.rest_service_log_file_size_MB = 100,
        test_config.rest_service_log_files_backup_count = 20
        return test_config

    @staticmethod
    def _create_temp_files_and_folders():
        fd, rest_service_log = tempfile.mkstemp(prefix='rest-log-')
        os.close(fd)
        fd, tmp_conf_file = tempfile.mkstemp(prefix='conf-file-')
        os.close(fd)
        return rest_service_log, tmp_conf_file

    @staticmethod
    def _set_config_path_and_get_server_module(rest_service_log, tmp_conf_file):
        """Workaround for setting the rest service log path, since it's
        needed when 'server' module is imported.
        right after the import the log path is set normally like the rest
        of the variables (used in the reset_state)
        """
        with open(tmp_conf_file, 'w') as f:
            json.dump({'rest_service_log_path': rest_service_log,
                       'rest_service_log_file_size_MB': 1,
                       'rest_service_log_files_backup_count': 1,
                       'rest_service_log_level': 'DEBUG'},
                      f)
        os.environ['MANAGER_REST_CONFIG_PATH'] = tmp_conf_file
        try:
            from manager_rest import server
        finally:
            del(os.environ['MANAGER_REST_CONFIG_PATH'])
        return server

    def _set_flask_app_context(self):
        flask_app_context = self.server.app.test_request_context()
        flask_app_context.push()
        self.addCleanup(flask_app_context.pop)

    def _init_default_tenant(self):
        t = models.Tenant(name=constants.DEFAULT_TENANT_NAME)
        self.server.db.session.add(t)
        self.server.db.session.commit()

        self.server.app.config[constants.CURRENT_TENANT_CONFIG] = t
        return t

    def _init_admin_user(self, default_tenant):
        """Add users and roles for the test

        :param user_datastore: SQLAlchemyDataUserstore
        """
        admin_user = get_admin_user()
        utils.create_security_roles_and_admin_user(
            self.server.user_datastore,
            admin_username=admin_user['username'],
            admin_password=admin_user['password'],
            default_tenant=default_tenant
        )
