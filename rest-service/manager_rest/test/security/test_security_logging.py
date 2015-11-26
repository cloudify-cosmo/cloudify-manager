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

from nose.plugins.attrib import attr

from manager_rest.test import base_test
from manager_rest.test.security.security_test_base import SecurityTestBase
from cloudify_rest_client.exceptions import CloudifyClientError


@attr(client_min_version=1, client_max_version=base_test.LATEST_API_VERSION)
class TestSecurityAuditLog(SecurityTestBase):

    def create_configuration(self):
        test_config = super(TestSecurityAuditLog, self).create_configuration()
        test_config.security_audit_log_level = 'DEBUG'
        test_config.security_audit_log_file = tempfile.mkstemp()[1]
        test_config.security_audit_log_file_size_MB = 0.1
        test_config.security_audit_log_files_backup_count = 1
        self.security_log_path = test_config.security_audit_log_file
        return test_config

    def test_password_auth_success_log(self):
        client = self.create_client(
            headers=SecurityTestBase.create_auth_header(
                username='alice', password='alice_password'))
        client.deployments.list()
        expected_text = '[INFO] [flask-securest] user "alice" authenticated ' \
                        'successfully'
        self.assert_log_contains(expected_text)
        expected_text = 'authentication provider: password'
        self.assert_log_contains(expected_text)

    def test_wrong_user_auth_failure_log(self):
        client = self.create_client(
            headers=SecurityTestBase.create_auth_header(
                username='wrong_user', password='alice_password'))
        self.assertRaises(CloudifyClientError, client.deployments.list)
        self.assert_log_contains('[ERROR] [flask-securest] User unauthorized')
        expected_text = 'all authentication methods failed:' \
                        '\npassword authenticator: authentication of' \
                        ' user "wrong_user" failed' \
                        '\ntoken authenticator: Request authentication' \
                        ' header "Authentication-Token" is empty or missing'
        self.assert_log_contains(expected_text)

    def test_wrong_password_auth_failure_log(self):
        client = self.create_client(
            headers=SecurityTestBase.create_auth_header(
                username='alice', password='wrong_password'))
        self.assertRaises(CloudifyClientError, client.deployments.list)
        self.assert_log_contains('[ERROR] [flask-securest] User unauthorized')
        expected_text = 'all authentication methods failed:' \
                        '\npassword authenticator: authentication of user' \
                        ' "alice" failed' \
                        '\ntoken authenticator: Request authentication ' \
                        'header "Authentication-Token" is empty or missing'
        self.assert_log_contains(expected_text)

    def test_token_auth_success_log(self):
        client = self.create_client(
            headers=SecurityTestBase.create_auth_header(
                username='alice', password='alice_password'))
        token_value = client.tokens.get().value
        client = self.create_client(headers=SecurityTestBase.
                                    create_auth_header(token=token_value))
        client.deployments.list()
        expected_text = '[INFO] [flask-securest] user "alice" authenticated ' \
                        'successfully'
        self.assert_log_contains(expected_text)
        expected_text = 'authentication provider: token'
        self.assert_log_contains(expected_text)

    def test_token_auth_failure_log(self):
        client = self.create_client(headers=SecurityTestBase.
                                    create_auth_header(token='wrong_token'))
        self.assertRaises(CloudifyClientError, client.deployments.list)
        self.assert_log_contains('[ERROR] [flask-securest] User unauthorized')
        expected_text = 'all authentication methods failed:' \
                        '\npassword authenticator: ' \
                        'Request authentication header "Authorization" ' \
                        'is empty or missing' \
                        '\ntoken authenticator: invalid token'
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

        super(TestSecurityAuditLog, self).tearDown()
