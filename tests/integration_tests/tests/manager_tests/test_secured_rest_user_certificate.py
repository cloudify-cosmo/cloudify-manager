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

import requests.exceptions

from cloudify_cli import constants

from integration_tests import utils
from integration_tests.tests.manager_tests.test_secured_rest_base import (
    TestSSLRestBase)


class SecuredSSLVerifyUserCertificate(TestSSLRestBase):

    def test_secured_manager_verify_user_certificate(self):
        # we need to start a container in advance so we have an ip
        # when we generate ssl certificates
        self.prepare_bootstrappable_container()
        self.manager_ip = utils.get_manager_ip()

        # TODO this call will actually remove the current container
        # and start a new one with mounted user code, so it is possible the
        # container will get a different ip address, which is bad.
        self.bootstrap_secured_manager_on_prepared_container()

        self._test_verify_cert()
        self._test_no_verify_cert()
        self._test_verify_missing_cert()
        self._test_verify_wrong_cert()
        self._test_try_to_connect_to_manager_on_non_secured_port()
        self.test_hello_world()

    def _test_verify_cert(self):
        self._assert_valid_request(ssl=True,
                                   cert_path=self.cert_path,
                                   trust_all=False)

    def _test_no_verify_cert(self):
        self._assert_valid_request(ssl=True,
                                   cert_path=None,
                                   trust_all=True)

    def _test_verify_missing_cert(self):
        self._assert_ssl_error(ssl=True,
                               # False means the rest client creation
                               # will explicitly pass None, otherwise, it
                               # will fallback to what the CLI would have used.
                               cert_path=False,
                               trust_all=False)

    def _test_verify_wrong_cert(self):
        cert_path = os.path.join(self.workdir, 'wrong.cert')
        key_path = os.path.join(self.workdir, 'wrong.key')
        utils.create_self_signed_certificate(cert_path, key_path, 'test')
        self._assert_ssl_error(ssl=True,
                               cert_path=cert_path,
                               trust_all=False)

    def _test_try_to_connect_to_manager_on_non_secured_port(self):
        self._assert_valid_request(ssl=False,
                                   cert_path=self.cert_path,
                                   trust_all=False)

    def _assert_valid_request(self, ssl, cert_path, trust_all):
        client = self._create_rest_client(ssl=ssl, cert_path=cert_path,
                                          trust_all=trust_all)
        client.manager.get_status()

    def _assert_ssl_error(self, ssl, cert_path, trust_all):
        client = self._create_rest_client(ssl=ssl, cert_path=cert_path,
                                          trust_all=trust_all)
        with self.assertRaises(requests.exceptions.SSLError):
            client.manager.get_status()

    def get_manager_blueprint_inputs(self):
        inputs = super(SecuredSSLVerifyUserCertificate,
                       self).get_manager_blueprint_inputs()
        inputs['agent_verify_rest_certificate'] = True
        return inputs

    def set_env_vars(self):
        super(SecuredSSLVerifyUserCertificate, self).set_env_vars()
        os.environ[constants.LOCAL_REST_CERT_FILE] = self.cert_path
        os.environ[constants.CLOUDIFY_SSL_TRUST_ALL] = ''

    def handle_ssl_files(self, manager_blueprint_dir):
        ssl_dir = os.path.join(manager_blueprint_dir, 'resources/ssl')
        if not os.path.isdir(ssl_dir):
            os.mkdir(ssl_dir)
        self.cert_path = os.path.join(ssl_dir, 'external_rest_host.crt')
        self.key_path = os.path.join(ssl_dir, 'external_rest_host.key')
        # create certificate with the ip intended to be used for this manager
        utils.create_self_signed_certificate(
            target_certificate_path=self.cert_path,
            target_key_path=self.key_path,
            common_name=self.manager_ip)
        # TODO: fix bug in current manager blueprint certificate handling
        # where if private and public ips are the same and only a public
        # certificate is provided, then an internal one is generated and
        # is also used as the external certificate
        # correct behaviour should be to use the one provided and not generate
        # any certificate
        internal_cert_path = os.path.join(ssl_dir, 'internal_rest_host.crt')
        internal_key_path = os.path.join(ssl_dir, 'internal_rest_host.key')
        shutil.copy(self.cert_path, internal_cert_path)
        shutil.copy(self.key_path, internal_key_path)

    @staticmethod
    def _create_rest_client(ssl, cert_path, trust_all):
        if ssl:
            port = constants.SECURED_REST_PORT
            protocol = constants.SECURED_REST_PROTOCOL
        else:
            port = constants.DEFAULT_REST_PORT
            protocol = constants.DEFAULT_REST_PROTOCOL
        return utils.create_rest_client(
            rest_port=port,
            rest_protocol=protocol,
            cert_path=cert_path,
            trust_all=trust_all)
