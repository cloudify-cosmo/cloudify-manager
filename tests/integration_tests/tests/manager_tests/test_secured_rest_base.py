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

from cloudify_cli import constants as cli_constants

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

    def bootstrap_secured_manager_on_prepared_container(self):
        self.bootstrap_prepared_container(
            inputs=self.get_manager_blueprint_inputs(),
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
        os.environ[cli_constants.CLOUDIFY_USERNAME_ENV] = self.get_username()
        os.environ[cli_constants.CLOUDIFY_PASSWORD_ENV] = self.get_password()
        os.environ[cli_constants.CLOUDIFY_SSL_TRUST_ALL] = 'true'
        self.addCleanup(self.unset_env_vars)

    def unset_env_vars(self):
        os.environ.pop(cli_constants.CLOUDIFY_USERNAME_ENV, None)
        os.environ.pop(cli_constants.CLOUDIFY_PASSWORD_ENV, None)
        os.environ.pop(cli_constants.CLOUDIFY_SSL_TRUST_ALL, None)
        os.environ.pop(cli_constants.LOCAL_REST_CERT_FILE, None)
        os.environ.pop(constants.CLOUDIFY_REST_PORT, None)

    def get_security_settings(self):
        authentication_providers = self.get_authentication_providers()
        authorization_provider = self.get_authorization_provider()
        userstore_drive = self.get_userstore_driver()
        auth_token_generator = self.get_auth_token_generator()
        settings = {}
        if authentication_providers is not None:
            prop = '{0}.authentication_providers'.format(SECURITY_PROP_PATH)
            settings[prop] = authentication_providers
        if authorization_provider is not None:
            prop = '{0}.authorization_provider'.format(SECURITY_PROP_PATH)
            settings[prop] = authorization_provider
        if userstore_drive is not None:
            prop = '{0}.userstore_driver'.format(SECURITY_PROP_PATH)
            settings[prop] = userstore_drive
        if auth_token_generator is not None:
            prop = '{0}.auth_token_generator'.format(SECURITY_PROP_PATH)
            settings[prop] = auth_token_generator
        return settings

    def get_manager_blueprint_inputs(self):
        username = self.get_username()
        password = self.get_password()
        return {
            'security_enabled': True,
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

    def get_username(self):
        return 'john_doe'

    def get_password(self):
        return 'some_password'

    def get_userstore_driver(self):
        return None

    def get_authentication_providers(self):
        return None

    def get_authorization_provider(self):
        return None

    def get_auth_token_generator(self):
        return None

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
