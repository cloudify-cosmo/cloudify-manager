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

import ssl
import unittest

from mock import patch, PropertyMock

import riemann_controller


class TestSecurity(unittest.TestCase):

    @patch('riemann_controller.tasks.ctx')
    @patch('riemann_controller.tasks.json')
    @patch('riemann_controller.tasks.pika')
    @patch('riemann_controller.tasks.broker_config')
    @patch('riemann_controller.tasks.get_manager_ip')
    def test_publish_config_event_uses_specified_credentials(self,
                                                             mock_get_ip,
                                                             mock_config,
                                                             mock_pika,
                                                             mock_json,
                                                             mock_ctx):
        username = 'someuser'
        password = 'somepassword'
        type(mock_config).broker_username = PropertyMock(
            return_value=username,
        )
        type(mock_config).broker_password = PropertyMock(
            return_value=password,
        )
        type(mock_config).broker_ssl_enabled = PropertyMock(
            return_value=False,
        )
        type(mock_config).broker_cert_path = PropertyMock(
            return_value='',
        )

        riemann_controller.tasks._publish_configuration_event(
            None,
            None,
        )

        mock_pika.credentials.PlainCredentials.assert_called_once_with(
            username=username,
            password=password,
        )

    @patch('riemann_controller.tasks.ctx')
    @patch('riemann_controller.tasks.json')
    @patch('riemann_controller.tasks.pika')
    @patch('riemann_controller.tasks.broker_config')
    @patch('riemann_controller.tasks.get_manager_ip')
    def test_publish_config_event_can_use_non_ssl(self,
                                                  mock_get_ip,
                                                  mock_config,
                                                  mock_pika,
                                                  mock_json,
                                                  mock_ctx):
        username = 'someuser'
        password = 'somepassword'
        type(mock_config).broker_username = PropertyMock(
            return_value=username,
        )
        type(mock_config).broker_password = PropertyMock(
            return_value=password,
        )
        type(mock_config).broker_ssl_enabled = PropertyMock(
            return_value=False,
        )
        type(mock_config).broker_cert_path = PropertyMock(
            return_value='',
        )

        riemann_controller.tasks._publish_configuration_event(
            None,
            None,
        )

        mock_pika.ConnectionParameters.assert_called_once_with(
            host=mock_get_ip.return_value,
            port=5672,
            credentials=mock_pika.credentials.PlainCredentials.return_value,
            ssl=False,
            ssl_options={},
        )

    @patch('riemann_controller.tasks.ctx')
    @patch('riemann_controller.tasks.json')
    @patch('riemann_controller.tasks.pika')
    @patch('riemann_controller.tasks.broker_config')
    @patch('riemann_controller.tasks.get_manager_ip')
    def test_publish_config_event_can_use_ssl(self,
                                              mock_get_ip,
                                              mock_config,
                                              mock_pika,
                                              mock_json,
                                              mock_ctx):
        username = 'someuser'
        password = 'somepassword'
        cert = '/not/a/real/cert.pem'
        type(mock_config).broker_username = PropertyMock(
            return_value=username,
        )
        type(mock_config).broker_password = PropertyMock(
            return_value=password,
        )
        type(mock_config).broker_ssl_enabled = PropertyMock(
            return_value=True,
        )
        type(mock_config).broker_cert_path = PropertyMock(
            return_value=cert,
        )

        riemann_controller.tasks._publish_configuration_event(
            None,
            None,
        )

        mock_pika.ConnectionParameters.assert_called_once_with(
            host=mock_get_ip.return_value,
            port=5671,
            credentials=mock_pika.credentials.PlainCredentials.return_value,
            ssl=True,
            ssl_options={
                'cert_reqs': ssl.CERT_REQUIRED,
                'ca_certs': cert,
            },
        )
