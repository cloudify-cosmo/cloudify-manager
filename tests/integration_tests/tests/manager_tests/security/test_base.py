########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
from contextlib import contextmanager

from cloudify_cli import constants as cli_constants
from cloudify_rest_client.exceptions import UserUnauthorizedError

from manager_rest.test.security_utils import get_test_users, get_test_roles

from integration_tests import ManagerTestCase
from integration_tests import constants
from integration_tests import utils

SECURITY_PROP_PATH = ('node_types.cloudify\.nodes\.MyCloudifyManager.'
                      'properties.security.default')
REST_PLUGIN_PATH = 'node_templates.rest_service.properties.plugins'
USERDATA_PATH = 'node_templates.manager_host.properties.parameters.user_data'


class TestSecuredRestBase(ManagerTestCase):

    def bootstrap_secured_manager(self):
        self.bootstrap(inputs=self.get_manager_blueprint_inputs(),
                       modify_blueprint_func=self._update_manager_blueprint)

    def _update_manager_blueprint(self, patcher, manager_blueprint_dir):
        for key, value in self.get_manager_blueprint_override().items():
            patcher.set_value(key, value)
        self.handle_ssl_files(manager_blueprint_dir)
        security_settings = self.get_security_settings()
        test_manager_types_path = os.path.join(manager_blueprint_dir,
                                               'types/manager-types.yaml')
        with utils.YamlPatcher(test_manager_types_path) as patch:
            for key, value in security_settings.items():
                patch.set_value(key, value)
        self.set_env_vars()

    def handle_ssl_files(self, manager_blueprint_dir):
        pass

    def set_env_vars(self):
        os.environ[cli_constants.CLOUDIFY_USERNAME_ENV] = utils.ADMIN_USERNAME
        os.environ[cli_constants.CLOUDIFY_PASSWORD_ENV] = utils.ADMIN_PASSWORD
        os.environ[cli_constants.CLOUDIFY_SSL_TRUST_ALL] = 'true'
        self.addCleanup(self.unset_env_vars)

    @staticmethod
    def unset_env_vars():
        os.environ.pop(cli_constants.CLOUDIFY_USERNAME_ENV, None)
        os.environ.pop(cli_constants.CLOUDIFY_PASSWORD_ENV, None)
        os.environ.pop(cli_constants.CLOUDIFY_SSL_TRUST_ALL, None)
        os.environ.pop(cli_constants.LOCAL_REST_CERT_FILE, None)
        os.environ.pop(constants.CLOUDIFY_REST_PORT, None)

    @staticmethod
    def get_security_settings():
        userstore = {
            'users': get_test_users(),
            'roles': get_test_roles()
        }
        settings = {'{0}.userstore'.format(SECURITY_PROP_PATH): userstore}
        return settings

    def get_manager_blueprint_inputs(self):
        username = utils.ADMIN_USERNAME
        password = utils.ADMIN_PASSWORD
        return {
            'ssl_enabled': self.is_ssl_enabled(),
            'admin_username': username,
            'admin_password': password,
            'agent_rest_username': username,
            'agent_rest_password': password
        }

    def get_manager_blueprint_override(self):
        rest_plugins = self.get_rest_plugins()
        overrides = {}
        if rest_plugins:
            overrides[REST_PLUGIN_PATH] = rest_plugins
        return overrides

    def is_ssl_enabled(self):
        return False

    def get_rest_plugins(self):
        return None


class TestSSLRestBase(TestSecuredRestBase):

    def is_ssl_enabled(self):
        import requests.packages.urllib3
        requests.packages.urllib3.disable_warnings()
        return True

    def set_env_vars(self):
        super(TestSSLRestBase, self).set_env_vars()
        os.environ[constants.CLOUDIFY_REST_PORT] = '443'


class TestAuthenticationBase(TestSecuredRestBase):
    test_client = None

    @contextmanager
    def _login_client(self, **kwargs):
        self.logger.info('performing login to test client with {0}'.format(
            str(kwargs))
        )
        try:
            self.test_client = utils.create_rest_client(**kwargs)
            yield
        finally:
            self.test_client = None

    def _assert_unauthorized(self, **kwargs):
        with self._login_client(**kwargs):
            self.assertRaises(
                UserUnauthorizedError,
                self.test_client.manager.get_status
            )

    def _assert_authorized(self, **kwargs):
        with self._login_client(**kwargs):
            self.test_client.manager.get_status()
