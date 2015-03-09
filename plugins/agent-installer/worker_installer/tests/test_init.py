#########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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

import unittest

from mock import patch
from mock import MagicMock

from worker_installer import init_worker_installer
from cloudify.mocks import MockCloudifyContext
from cloudify.exceptions import NonRecoverableError


# for tests purposes. need a path to a file which always exists
KEY_FILE_PATH = '/bin/sh'


@init_worker_installer
def init_cloudify_agent_configuration(*args, **kwargs):
    if 'cloudify_agent' in kwargs:
        return kwargs['cloudify_agent']
    elif 'agent_config' in kwargs:
        return kwargs['agent_config']
    else:
        raise ValueError("'cloudify_agent' not set by init_worker_installer")


@patch('worker_installer._run_py_cmd_with_output', MagicMock(return_value=""))
@patch('worker_installer.utils.FabricRunner', MagicMock())
class InitTest(unittest.TestCase):

    def test_cloudify_agent_config_duplication(self):
        ctx = MockCloudifyContext(node_id='node_id',
                                  properties={'cloudify_agent':
                                              {'user': 'prop_user',
                                               'distro': 'Ubuntu',
                                               'distro_codename': 'trusty',
                                               'key': KEY_FILE_PATH},
                                              'ip': 'localhost'},
                                  operation={'name': 'create'})
        expected_message = "'cloudify_agent' is configured both as a node " \
                           "property and as an invocation input parameter" \
                           " for operation 'create'"
        self.assertRaisesRegexp(NonRecoverableError, expected_message,
                                init_cloudify_agent_configuration, ctx,
                                cloudify_agent={'user': 'input_user',
                                                'key': KEY_FILE_PATH})

    def test_cloudify_agent_set_as_property(self):
        ctx = MockCloudifyContext(
            node_id='node_id',
            properties={'cloudify_agent':
                        {'user': 'prop_user',
                         'distro': 'Ubuntu',
                         'distro_codename': 'trusty',
                         'key': KEY_FILE_PATH},
                        'ip': 'localhost'})
        cloudify_agent = init_cloudify_agent_configuration(ctx)

        self.assertEqual(cloudify_agent['user'], 'prop_user')
        self.assertEqual(cloudify_agent['key'], KEY_FILE_PATH)

    def test_cloudify_agent_set_as_property_with_password(self):
        ctx = MockCloudifyContext(
            node_id='node_id',
            properties={'cloudify_agent':
                        {'user': 'prop_user',
                         'distro': 'Ubuntu',
                         'distro_codename': 'trusty',
                         'password': 'prop_password'},
                        'ip': 'localhost'})
        cloudify_agent = init_cloudify_agent_configuration(ctx)

        self.assertEqual(cloudify_agent['user'], 'prop_user')
        self.assertEqual(cloudify_agent['password'], 'prop_password')

    def test_cloudify_agent_set_as_input(self):

        ctx = MockCloudifyContext(node_id='node_id',
                                  properties={'ip': 'localhost'})
        cloudify_agent = \
            init_cloudify_agent_configuration(
                ctx,
                cloudify_agent={'user': 'input_user',
                                'distro': 'Ubuntu',
                                'distro_codename': 'trusty',
                                'key': KEY_FILE_PATH})

        self.assertEqual(cloudify_agent['user'], 'input_user')
        self.assertEqual(cloudify_agent['key'], KEY_FILE_PATH)

    def test_cloudify_agent_set_as_input_with_password(self):

        ctx = MockCloudifyContext(node_id='node_id',
                                  properties={'ip': 'localhost'})
        cloudify_agent = \
            init_cloudify_agent_configuration(
                ctx,
                cloudify_agent={'user': 'input_user',
                                'distro': 'Ubuntu',
                                'distro_codename': 'trusty',
                                'password': 'input_password'})

        self.assertEqual(cloudify_agent['user'], 'input_user')
        self.assertEqual(cloudify_agent['password'], 'input_password')

    def test_cloudify_agent_not_set(self):
        ctx = MockCloudifyContext(node_id='node_id',
                                  properties={'ip': 'localhost'})
        expected_message = "Missing password or ssh key path " \
                           "in worker configuration"
        self.assertRaisesRegexp(NonRecoverableError, expected_message,
                                init_cloudify_agent_configuration, ctx)

    def test_cloudify_agent_no_auth(self):
        ctx = MockCloudifyContext(node_id='node_id',
                                  properties={'ip': 'localhost'})
        expected_message = "Missing password or ssh key path " \
                           "in worker configuration"
        self.assertRaisesRegexp(NonRecoverableError, expected_message,
                                init_cloudify_agent_configuration, ctx)
