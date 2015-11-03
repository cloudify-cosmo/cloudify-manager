#########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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
from itsdangerous import base64_encode

from manager_rest.test.base_test import BaseServerTestCase


CLOUDIFY_AUTH_HEADER = 'Authorization'
CLOUDIFY_AUTH_TOKEN_HEADER = 'Authentication-Token'
BASIC_AUTH_PREFIX = 'Basic '


class SecurityTestBase(BaseServerTestCase):

    def setUp(self):
        super(SecurityTestBase, self).setUp()

    def cleanup(self):
        super(SecurityTestBase, self).cleanup()

    def initialize_provider_context(self):
        client = self.create_client(
            headers=SecurityTestBase.create_auth_header(username='admin',
                                                        password='admin'))
        super(SecurityTestBase, self).initialize_provider_context(
            client=client)

    @staticmethod
    def create_auth_header(username=None, password=None, token=None):
        header = None
        # using or to allow testing of username without password and vice-versa
        if username or password:
            credentials = '{0}:{1}'.format(username, password)
            header = {CLOUDIFY_AUTH_HEADER:
                      BASIC_AUTH_PREFIX + base64_encode(credentials)}
        elif token:
            header = {CLOUDIFY_AUTH_TOKEN_HEADER: token}

        return header

    def create_configuration(self):
        test_config = super(SecurityTestBase, self).create_configuration()
        test_config.security_enabled = True

        test_config.security_userstore_driver = \
            self.get_userstore_configuration()

        test_config.security_auth_token_generator = \
            self.get_auth_token_generator_configuration()

        test_config.security_authentication_providers = \
            self.get_authentication_providers_configuration()

        test_config.security_authorization_provider = \
            self.get_authorization_provider_configuration()

        return test_config

    @staticmethod
    def get_authentication_providers_configuration():
        return [
            {
                'name': 'password',
                'implementation':
                    'flask_securest.authentication_providers.password'
                    ':PasswordAuthenticator',
                'properties': {
                    'password_hash': 'plaintext'
                }
            },
            {
                'name': 'token',
                'implementation': 'flask_securest.authentication_providers.'
                                  'token:TokenAuthenticator',
                'properties': {
                    'secret_key': 'my_secret'
                }
            }
        ]

    @staticmethod
    def get_userstore_configuration():
        return {
            'implementation':
                'flask_securest.userstores.simple:SimpleUserstore',
            'properties': {
                'userstore': {
                    'users': [
                        {
                            'username': 'admin',
                            'password': 'admin',
                            'groups': ['cfy_admins']
                        },
                        {
                            'username': 'deployment_manager',
                            'password': 'deployment_manager',
                            'groups': ['managers', 'users']
                        },
                        {
                            'username': 'deployment_viewer',
                            'password': 'deployment_viewer',
                            'groups': ['users'],
                            'roles': ['viewer']
                        },
                        {
                            'username': 'user',
                            'password': 'user',
                            'groups': ['users']
                        }
                    ],
                    'groups': [
                        {
                            'name': 'cfy_admins',
                            'roles': ['administrator']
                        },
                        {
                            'name': 'managers',
                            'roles': ['deployer', 'viewer']
                        },
                        {
                            'name': 'users',
                            'roles': []
                        }
                    ]
                }
            }
        }

    @staticmethod
    def get_authorization_provider_configuration():
        abs_path = os.path.dirname(os.path.abspath(__file__))
        roles_config_file_path = os.path.join(abs_path,
                                              '../resources/roles_config.yaml')
        return {
            'implementation': 'flask_securest.authorization_providers.'
                              'role_based_authorization_provider:'
                              'RoleBasedAuthorizationProvider',
            'properties': {
                'roles_config_file_path': roles_config_file_path,
                'role_loader': {
                    'implementation':
                        'flask_securest.authorization_providers.role_loaders.'
                        'simple_role_loader:SimpleRoleLoader'
                }
            }
        }

    @staticmethod
    def get_auth_token_generator_configuration():
        return {
            'implementation': 'flask_securest.authentication_providers.token:'
                              'TokenAuthenticator',
            'properties': {
                'secret_key': 'my_secret',
                'expires_in_seconds': 600
            }
        }
