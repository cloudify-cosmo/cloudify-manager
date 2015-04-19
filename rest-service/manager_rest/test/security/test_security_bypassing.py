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

from cloudify_rest_client.exceptions import CloudifyClientError

from manager_rest.test.security.security_test_base import SecurityTestBase


class SecurityBypassTest(SecurityTestBase):

    BYPASS_PORT = 56789
    NOT_BYPASS_PORT = 56790

    def create_configuration(self):
        test_config = super(SecurityBypassTest, self).create_configuration()
        test_config.security_bypass_port = self.BYPASS_PORT
        return test_config

    def test_bypass_and_correct_credentials(self):
        client = self.create_client(SecurityTestBase.create_auth_header(self,
                                                                        username='user1', password='pass1'))
        self._modify_client_to_pass_bypass_header(client, self.BYPASS_PORT)

        client.blueprints.list()

    def test_bypass_and_incorrect_password(self):
        client = self.create_client(SecurityTestBase.create_auth_header(self,
                                                                        username='user1', password='wrong_pass'))
        self._modify_client_to_pass_bypass_header(client, self.BYPASS_PORT)

        client.blueprints.list()

    def test_bypass_and_nonexisting_user(self):
        client = self.create_client(SecurityTestBase.create_auth_header(self,
                                                                        username='nonexisting-user',
                                                                        password='pass1'))
        self._modify_client_to_pass_bypass_header(client, self.BYPASS_PORT)
        client.blueprints.list()

    def test_bypass_and_no_credentials(self):
        client = self.create_client()
        self._modify_client_to_pass_bypass_header(client, self.BYPASS_PORT)
        client.blueprints.list()

    def test_bypass_not_bypass_port_and_correct_credentials(self):
        client = self.create_client(SecurityTestBase.create_auth_header(self,
                                                                        username='user1', password='pass1'))
        self._modify_client_to_pass_bypass_header(client,
                                                  self.NOT_BYPASS_PORT)
        client.blueprints.list()

    def test_bypass_not_bypass_port_and_incorrect_password(self):
        client = self.create_client(SecurityTestBase.create_auth_header(self,
                                                                        username='user1', password='wrong-pass'))
        self._modify_client_to_pass_bypass_header(client,
                                                  self.NOT_BYPASS_PORT)
        try:
            client.blueprints.list()
            self.fail('Call to blueprints list was successful despite using'
                      'incorrect password and not using the bypass port')
        except CloudifyClientError, e:
            self.assertEquals(401, e.status_code)

    def test_bypass_not_bypass_port_and_nonexisting_user(self):
        client = self.create_client(SecurityTestBase.create_auth_header(self,
                                                                        username='nonexisting-user',
                                                                        password='pass1'))
        self._modify_client_to_pass_bypass_header(client,
                                                  self.NOT_BYPASS_PORT)
        try:
            client.blueprints.list()
            self.fail('Call to blueprints list was successful despite using'
                      'nonexisting user and not using the bypass port')
        except CloudifyClientError, e:
            self.assertEquals(401, e.status_code)

    def test_bypass_not_bypass_port_and_no_credentials(self):
        client = self.create_client()
        self._modify_client_to_pass_bypass_header(client,
                                                  self.NOT_BYPASS_PORT)
        try:
            client.blueprints.list()
            self.fail('Call to blueprints list was successful despite using'
                      'no credentials and not using the bypass port')
        except CloudifyClientError, e:
            self.assertEquals(401, e.status_code)

    def _modify_client_to_pass_bypass_header(self, client, bypass_port):
        # making the given client use the bypass header on all requests
        orig_func = client._client._do_request

        def new_func(*args, **kwargs):
            headers = kwargs.get('headers', {})
            headers['X-Server-Port'] = bypass_port
            kwargs['headers'] = headers
            return orig_func(*args, **kwargs)

        client._client._do_request = new_func

    def setUp(self):
        print '***** starting test {0}, in SecurityBypassTest setUp, ' \
              'calling super setUp'.format(self._testMethodName)
        super(SecurityBypassTest, self).setUp()

    def tearDown(self):
        print '***** ending test {0}, in SecurityBypassTest tearDown, ' \
              'calling super tearDown'.format(self._testMethodName)
        super(SecurityBypassTest, self).tearDown()
