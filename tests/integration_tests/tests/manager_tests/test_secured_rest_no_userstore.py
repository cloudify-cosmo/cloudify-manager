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
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import os
import shutil

from cloudify_rest_client import exceptions

from integration_tests import utils
from integration_tests.utils import get_resource as resource
from integration_tests.tests.manager_tests.test_secured_rest_base import (
    TestSecuredRestBase)

CUSTOM_AUTH_PROVIDER_PLUGIN = 'mock-auth-provider-with-no-userstore'


class NoUserstoreTests(TestSecuredRestBase):

    def test_authentication_without_userstore(self):
        self.bootstrap_secured_manager()
        self._assert_unauthorized_user_fails()

    def _assert_unauthorized_user_fails(self):
        good_client = self.client
        bad_client = utils.create_rest_client(username='wrong_username',
                                              password=self.get_password())
        good_client.manager.get_status()
        with self.assertRaises(exceptions.UserUnauthorizedError):
            bad_client.manager.get_status()

    def _update_manager_blueprint(self, patcher, blueprint_dir):
        super(NoUserstoreTests, self)._update_manager_blueprint(
            patcher, blueprint_dir)
        src_plugin_dir = resource(
            'plugins/{0}'.format(CUSTOM_AUTH_PROVIDER_PLUGIN))
        dst_plugin_dir = os.path.join(
            blueprint_dir, CUSTOM_AUTH_PROVIDER_PLUGIN)
        shutil.copytree(src_plugin_dir, dst_plugin_dir)

    def get_username(self):
        return 'not_the_default_username'

    def get_password(self):
        return 'something'

    def get_rest_plugins(self):
        return {
            'user_custom_auth_provider': {
                'source': CUSTOM_AUTH_PROVIDER_PLUGIN
            }
        }

    def get_authentication_providers(self):
        return [
            {
                'implementation': 'mock_auth_provider_with_no_userstore'
                                  '.auth_without_userstore:'
                                  'AuthorizeUserByUsername',
                'name': 'Authorize_By_Username',
                'properties': {}
            }
        ]

    def get_userstore_driver(self):
        return ''

    def get_authorization_provider(self):
        return ''

    def get_auth_token_generator(self):
        return {}
