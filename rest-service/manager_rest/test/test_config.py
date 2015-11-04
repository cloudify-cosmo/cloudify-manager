########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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
############

import unittest

import manager_rest.config


class TestConfig(unittest.TestCase):

    def test_config_default_amqp_credentials(self):
        config = manager_rest.config.Config()

        self.assertEqual(
            'guest',
            config.amqp_username,
        )
        self.assertEqual(
            'guest',
            config.amqp_password,
        )

    def test_config_default_amqp_ssl_settings(self):
        config = manager_rest.config.Config()

        self.assertEqual(
            False,
            config.amqp_ssl_enabled,
        )
        self.assertEqual(
            '',
            config.amqp_ca_path,
        )

    def test_config_overridden_amqp_credentials(self):
        config = manager_rest.config.Config()

        username = 'newuser'
        password = 'changeme123'

        config.amqp_username = username
        config.amqp_password = password

        self.assertEqual(
            username,
            config.amqp_username,
        )
        self.assertEqual(
            password,
            config.amqp_password,
        )

    def test_config_overridden_amqp_ssl_settings(self):
        config = manager_rest.config.Config()

        cert_path = '/not/a/real/cert.pem'

        config.amqp_ssl_enabled = True
        config.amqp_ca_path = cert_path

        self.assertEqual(
            True,
            config.amqp_ssl_enabled,
        )
        self.assertEqual(
            cert_path,
            config.amqp_ca_path,
        )
