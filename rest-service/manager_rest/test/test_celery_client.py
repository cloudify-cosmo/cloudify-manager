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

from mock import patch

import manager_rest
import manager_rest.config


class TestCeleryClient(unittest.TestCase):

    @patch('manager_rest.celery_client.config')
    @patch('manager_rest.celery_client.Celery')
    def test_celery_client_uses_specified_credentials(self,
                                                      mock_celery,
                                                      mock_config):
        username = 'thisuser'
        password = 'thatsecurepassword'
        expected_url = 'amqp://{username}:{password}@localhost:5672'.format(
            username=username,
            password=password,
        )

        fake_config = manager_rest.config.Config()
        fake_config.amqp_username = username
        fake_config.amqp_password = password
        fake_config.amqp_address = 'localhost:5672'
        mock_config.instance.return_value = fake_config

        manager_rest.celery_client.CeleryClient()

        mock_celery.assert_called_once_with(
            broker=expected_url,
            backend=expected_url,
        )

    @patch('manager_rest.celery_client.config')
    @patch('manager_rest.celery_client.Celery')
    def test_celery_client_does_can_use_non_ssl(self,
                                                mock_celery,
                                                mock_config):
        fake_config = manager_rest.config.Config()
        fake_config.amqp_ssl_enabled = False
        fake_config.amqp_ca_path = ''
        mock_config.instance.return_value = fake_config

        manager_rest.celery_client.CeleryClient()

        # Celery conf update is expected to be called more than once
        celery_conf_args = mock_celery.conf.update.call_args_list

        for _, kwargs in celery_conf_args:
            self.assertNotIn(
                'BROKER_USE_SSL',
                kwargs.keys(),
            )

    @patch('manager_rest.celery_client.config')
    @patch('manager_rest.celery_client.Celery')
    def test_celery_client_can_use_ssl(self,
                                       mock_celery,
                                       mock_config):
        fake_config = manager_rest.config.Config()
        fake_config.amqp_ssl_enabled = True
        fake_config.amqp_ca_path = '/not/real/cert.pem'
        mock_config.instance.return_value = fake_config

        expected_ssl_settings = {
            'ca_certs': fake_config.amqp_ca_path,
            'cert_reqs': ssl.CERT_REQUIRED,
        }

        client = manager_rest.celery_client.CeleryClient()

        # Celery conf update is expected to be called more than once
        celery_conf_args = client.celery.conf.update.call_args_list

        broker_ssl_settings = {}
        for _, kwargs in celery_conf_args:
            if 'BROKER_USE_SSL' in kwargs.keys():
                broker_ssl_settings = kwargs['BROKER_USE_SSL']
                break

        self.assertEqual(
            expected_ssl_settings,
            broker_ssl_settings,
        )

    @patch('manager_rest.celery_client.config')
    @patch('manager_rest.celery_client.Celery')
    def test_celery_client_ssl_with_no_cert_fails(self,
                                                  mock_celery,
                                                  mock_config):
        fake_config = manager_rest.config.Config()
        fake_config.amqp_ssl_enabled = True
        fake_config.amqp_ca_path = ''
        mock_config.instance.return_value = fake_config

        try:
            manager_rest.celery_client.CeleryClient()
            # An exception should've been raised
            self.assertFail()
        except ValueError as err:
            self.assertIn(
                'no SSL cert was provided',
                err.message,
            )
