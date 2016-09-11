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
from .test_base import TestSSLRestBase


class SecuredSSLVerifyUserCertificate(TestSSLRestBase):

    def test_secured_manager_verify_user_certificate(self):
        self.bootstrap_secured_manager()
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
        self._assert_valid_request(ssl=True, trust_all=True)

    def _test_verify_missing_cert(self):
        self._assert_ssl_error(ssl=True, cert_path=None, trust_all=False)

    def _test_verify_wrong_cert(self):
        cert_path = os.path.join(self.workdir, 'wrong.cert')
        key_path = os.path.join(self.workdir, 'wrong.key')
        utils.create_self_signed_certificate(cert_path, key_path, 'test')
        self._assert_ssl_error(ssl=True, cert_path=cert_path, trust_all=False)

    def _test_try_to_connect_to_manager_on_non_secured_port(self):
        self._assert_valid_request(ssl=False,
                                   cert_path=self.cert_path,
                                   trust_all=False)

    def _assert_valid_request(self, **kwargs):
        client = self._create_rest_client(**kwargs)
        client.manager.get_status()

    def _assert_ssl_error(self, **kwargs):
        client = self._create_rest_client(**kwargs)
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
        # create certificate with the IP intended to be used for this manager
        # The IP we use here may actually change because after bootstrap is
        # done we save an image and run a new container from that image with
        # user mounted code. The IP of the new container may change if there
        # are parallel tests running on the same machine.
        utils.create_self_signed_certificate(
            target_certificate_path=self.cert_path,
            target_key_path=self.key_path,
            common_name=utils.get_manager_ip())
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
    def _create_rest_client(**kwargs):
        if kwargs.get('ssl'):
            kwargs['port'] = constants.SECURED_REST_PORT
            kwargs['protocol'] = constants.SECURED_REST_PROTOCOL
        else:
            kwargs['port'] = constants.DEFAULT_REST_PORT
            kwargs['protocol'] = constants.DEFAULT_REST_PROTOCOL
        return utils.create_rest_client(**kwargs)
