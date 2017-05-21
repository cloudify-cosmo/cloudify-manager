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
import ssl

import pika
import pika.exceptions

from integration_tests import ManagerTestCase
from integration_tests.tests import utils as test_utils


class SecuredBrokerManagerTests(ManagerTestCase):

    def test_secured_manager_with_certificate(self):
        # we need to start a container in advance so we have an ip
        # when we generate ssl certificates
        self.prepare_bootstrappable_container()
        self.manager_ip = self.get_manager_ip()
        self.rabbitmq_username = 'cloudify'
        self.rabbitmq_password = 'c10udify'

        # setup and bootstrap manager with broker security enabled
        self._handle_ssl_files()
        self._bootstrap_with_secured_broker()

        # send request and verify certificate
        self._test_verify_cert()
        # send request that is missing a certificate
        self._test_verify_missing_cert_fails()
        # send request with wrong certificate
        self._test_verify_wrong_cert_fails()
        # Check we can connect to the non secure port still
        # This is required until Riemann, Logstash, and the manager's diamond
        # can be made to work with tlsv1.2 and with a cert verification using
        # the pinned certificate
        self._test_non_secured_port_still_usable()

        # test hello world deployment
        self.test_hello_world()

    def _test_verify_cert(self):
        conn = self._can_get_broker_connection(
            port=5671,
            cert_path=self.cert_path,
        )
        # If we got a connection we can close it
        conn.close()

    def _test_verify_missing_cert_fails(self):
        try:
            self._can_get_broker_connection(
                port=5671,
                cert_path='',
            )
            self.fail('SSL connection should fail without cert')
        except pika.exceptions.AMQPConnectionError as err:
            self.assertIn('certificate verify failed', str(err))

    def _test_verify_wrong_cert_fails(self):
        try:
            self._can_get_broker_connection(
                port=5671,
                cert_path=self.wrong_cert_path,
            )
            self.fail('SSL connection should fail with wrong cert')
        except pika.exceptions.AMQPConnectionError as err:
            self.assertIn('certificate verify failed', str(err))

    def _test_non_secured_port_still_usable(self):
        conn = self._can_get_broker_connection(
            port=5672,
            ssl_enabled=False,
            cert_path='',
        )
        # If we got a connection we can close it
        conn.close()

    def _can_get_broker_connection(self,
                                   port=5672,
                                   cert_path='',
                                   ssl_enabled=False):
        host = self.manager_ip
        username = self.rabbitmq_username
        password = self.rabbitmq_password
        conn_params = {
            'host': host,
            'port': port,
            'credentials': pika.credentials.PlainCredentials(
                username=username,
                password=password,
            ),
        }
        if ssl_enabled:
            ssl_params = {
                'ssl': ssl_enabled,
                'ssl_options': {
                    'ca_certs': cert_path,
                    'cert_reqs': ssl.CERT_REQUIRED,
                },
            }
            conn_params.update(ssl_params)
        return pika.BlockingConnection(pika.ConnectionParameters(
            **conn_params))

    def _bootstrap_with_secured_broker(self):
        with open(self.cert_path) as cert_handle:
            public_cert = cert_handle.read()
        with open(self.key_path) as key_handle:
            private_key = key_handle.read()
        # TODO this call will actually remove the current container
        # and start a new one with mounted user code, so it is possible the
        # container will get a different ip address, which is bad.
        self.bootstrap_prepared_container(inputs={
            'rabbitmq_cert_public': public_cert,
            'rabbitmq_cert_private': private_key,
            'rabbitmq_username': self.rabbitmq_username,
            'rabbitmq_password': self.rabbitmq_password,
        })

    def _handle_ssl_files(self):
        ssl_dir = os.path.join(self.workdir, 'broker_ssl_test')
        if not os.path.isdir(ssl_dir):
            os.mkdir(ssl_dir)
        self.cert_path = os.path.join(ssl_dir, 'broker.crt')
        self.key_path = os.path.join(ssl_dir, 'broker.key')
        self.wrong_cert_path = os.path.join(ssl_dir, 'invalid.crt')
        self.wrong_key_path = os.path.join(ssl_dir, 'invalid.key')
        # create certificate with the ip intended to be used for this manager
        test_utils.create_self_signed_certificate(
            target_certificate_path=self.cert_path,
            target_key_path=self.key_path,
            common_name=self.manager_ip,
        )
        # create invalid certificate to test that invalid certs aren't allowed
        test_utils.create_self_signed_certificate(
            target_certificate_path=self.wrong_cert_path,
            target_key_path=self.wrong_key_path,
            common_name='invalid',
        )
