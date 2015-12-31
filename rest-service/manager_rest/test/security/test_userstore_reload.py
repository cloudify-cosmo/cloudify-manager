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
import tempfile
import yaml
import time

from cloudify_rest_client.exceptions import UserUnauthorizedError
from nose.plugins.attrib import attr

from manager_rest.test import base_test
from manager_rest.test.security.security_test_base import SecurityTestBase

_, USERSTORE_FILE = tempfile.mkstemp(prefix='userstore')
USERSTORE_LOADED_SUCCESSFULLY = 'Loading of userstore ended successfully'
USERSTORE_MISSING_USERS = 'Users not found in'
USERSTORE_FILE_INVALID_DICT = 'yaml is not a valid dict'
USERSTORE_INVALID_YAML = 'Failed parsing'


@attr(client_min_version=2, client_max_version=base_test.LATEST_API_VERSION)
class TestUserstoreReloadFile(SecurityTestBase):

    def setUp(self):
        self.modify_userstore_file(self.get_users(), self.get_groups())
        super(TestUserstoreReloadFile, self).setUp()

    def create_configuration(self):
        test_config = super(TestUserstoreReloadFile, self).\
            create_configuration()
        self.security_log_path = test_config.security_audit_log_file
        return test_config

    def _init_test(self):
        self.clear_log_file()
        self.modify_userstore_file(self.get_users(),
                                   self.get_groups(),
                                   USERSTORE_LOADED_SUCCESSFULLY)
        auth_header = SecurityTestBase. \
            create_auth_header(username='alice',
                               password='alice_password')
        client = self.create_client(headers=auth_header)
        return client

    def test_reload_userstore(self):
        client = self._init_test()
        # alice should be able to do everything
        client.deployments.list()

        # modify the userstore file. Change alice's password
        new_file_users = [
            {
                'user': 'alice',
                'password': 'non_existing_password'
            }
        ]
        self.modify_userstore_file(new_file_users,
                                   [],
                                   USERSTORE_LOADED_SUCCESSFULLY)

        # assert alice's old credentials are no longer valid
        self.assertRaises(UserUnauthorizedError, client.deployments.list)

    def test_reload_invalid_userstore_dict(self):
        self._test_invalid_userstore('invalid_userstore',
                                     USERSTORE_FILE_INVALID_DICT)

    def test_reload_invalid_userstore_no_users(self):
        self._test_invalid_userstore('{\'groups\': []}',
                                     USERSTORE_MISSING_USERS)

    def test_reload_invalid_userstore_invalid_yaml(self):
        self._test_invalid_userstore('{invalid_yaml}}', USERSTORE_INVALID_YAML)

    def _test_invalid_userstore(self, userstore_file_text, error_msg):
        client = self._init_test()
        # alice should be able to do everything
        client.deployments.list()

        # Corrupt userstore file
        self.corrupt_userstore_file(userstore_file_text,
                                    wait_for_message=error_msg)

        # Userstore changes should not have been applied
        client.deployments.list()

    def modify_userstore_file(self, users, groups, message=None):
        userstore_settings = {
            'users': users,
            'groups': groups
        }
        with open(USERSTORE_FILE, 'w') as outfile:
            outfile.write(yaml.dump(userstore_settings,
                                    default_flow_style=True))

        # wait for changes to take effect
        if message:
            self.wait_for_log_message(message)

    def corrupt_userstore_file(self, text, wait_for_message=None):
        with open(USERSTORE_FILE, 'w') as outfile:
            outfile.write(yaml.dump(text,
                                    default_flow_style=True))
        # wait for changes to take effect
        if wait_for_message:
            self.wait_for_log_message(USERSTORE_FILE_INVALID_DICT)

    def clear_log_file(self):
        with open(self.security_log_path, "w"):
            pass

    def wait_for_log_message(self, message):
        timeout = time.time() + 60
        while time.time() < timeout:
            time.sleep(1)
            if self.log_contains(message):
                return
        self.fail('Expected message: \'{0}\' was not found in log.'
                  .format(message))

    def log_contains(self, expected_text):
        with open(self.security_log_path) as f:
            logged_text = f.read()
        return expected_text in logged_text

    ###########################
    # test security settings
    ###########################
    def get_userstore_configuration(self):
        return {
            'implementation': 'flask_securest.userstores.file_userstore:'
                              'FileUserstore',
            'properties': {
                'userstore_file_path': USERSTORE_FILE
            }
        }
