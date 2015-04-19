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

import logging
import tempfile

from cloudify_rest_client.exceptions import CloudifyClientError

from manager_rest.test.security.security_test_base import SecurityTestBase


class TestSecurityAuditLog(SecurityTestBase):

    def setUp(self):
        print '***** starting test {0}, in TestSecurityAuditLog setUp, ' \
              'calling super setUp'.format(self._testMethodName)
        super(TestSecurityAuditLog, self).setUp()

    def create_configuration(self):
        test_config = super(TestSecurityAuditLog, self).create_configuration()
        test_config.securest_log_level = 'DEBUG'
        test_config.securest_log_file = tempfile.mkstemp()[1]
        test_config.securest_log_file_size_MB = 0.1
        test_config.securest_log_files_backup_count = 1
        self.security_log_path = test_config.securest_log_file
        return test_config

    def test_password_auth_success_log(self):
        client = self.create_client(SecurityTestBase.create_auth_header(self,
                                                                        username='user1', password='pass1'))
        client.deployments.list()
        expected_text = '[INFO] [flask-securest] user "user1" authenticated' \
                        ' successfully, authentication provider: password'
        self.assert_log_contains(expected_text)

    def test_password_auth_failure_log(self):
        client = self.create_client(SecurityTestBase.create_auth_header(self,
                                                                        username='wrong_user', password='pass1'))
        self.assertRaises(CloudifyClientError, client.deployments.list)
        expected_text = '[ERROR] [flask-securest] User unauthorized, ' \
                        'all authentication methods failed: \n' \
                        'password authentication failed: user not found\n' \
                        'token authentication failed: token is missing or ' \
                        'empty'
        self.assert_log_contains(expected_text)

    def test_token_auth_success_log(self):
        client = self.create_client(SecurityTestBase.create_auth_header(self,
                                                                        username='user1', password='pass1'))
        token_value = client.tokens.get().value
        expected_text = '[INFO] [flask-securest] user "user1" authenticated' \
                        ' successfully, authentication provider: password'
        self.assert_log_contains(expected_text)

        client = self.create_client(SecurityTestBase.create_auth_header(self,
                                                                        token=token_value))
        client.deployments.list()
        expected_text = '[INFO] [flask-securest] user "user1" authenticated' \
                        ' successfully, authentication provider: token'
        self.assert_log_contains(expected_text)

    def test_token_auth_failure_log(self):
        client = self.create_client(SecurityTestBase.create_auth_header(self,
                                                                        token='wrong_token'))
        self.assertRaises(CloudifyClientError, client.deployments.list)
        expected_text = '[ERROR] [flask-securest] User unauthorized, all ' \
                        'authentication methods failed: \n' \
                        'password authentication failed: username or password' \
                        ' not found on request\n' \
                        'token authentication failed: invalid token'
        self.assert_log_contains(expected_text)

    def assert_log_contains(self, expected_text):
        with open(self.security_log_path) as f:
            logged_text = f.read()
        self.assertIn(expected_text, logged_text)

    def tearDown(self):
        logger = logging.getLogger('flask-securest')
        # using a copy of the logger handlers list to overcome concurrent
        # modification while remove handlers
        handlers_copy = logger.handlers[:]
        for handler in handlers_copy:
            logger.removeHandler(handler)

        print '***** ending test {0}, in TestSecurityAuditLog tearDown, ' \
              'calling super tearDown'.format(self._testMethodName)
        super(TestSecurityAuditLog, self).tearDown()
