# Copyright (c) 2017-2019 Cloudify Platform Ltd. All rights reserved
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

import mock

from cloudify.state import current_ctx
from cloudify.exceptions import NonRecoverableError
from cloudify_rest_client.exceptions import CloudifyClientError

from .client_mock import MockCloudifyRestClient
from ..operations import execute_start
from .base_test_suite import (ComponentTestBase,
                              REST_CLIENT_EXCEPTION,
                              MOCK_TIMEOUT)


class TestExecute(ComponentTestBase):

    @classmethod
    def setUpClass(cls):
        super(TestExecute, cls).setUpClass()
        mock_sleep = mock.MagicMock()
        cls.sleep_mock = mock.patch('time.sleep', mock_sleep)
        cls.sleep_mock.start()

    def setUp(self):
        super(TestExecute, self).setUp()
        self._ctx.instance.runtime_properties['deployment'] = {}

    @classmethod
    def tearDownClass(cls):
        cls.sleep_mock.stop()
        super(TestExecute, cls).tearDownClass()

    def test_execute_start_rest_client_error(self):
        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            cfy_mock_client = MockCloudifyRestClient()
            cfy_mock_client.executions.start = REST_CLIENT_EXCEPTION
            mock_client.return_value = cfy_mock_client
            error = self.assertRaises(NonRecoverableError,
                                      execute_start,
                                      deployment_id='dep_name',
                                      workflow_id='install')
            self.assertIn('action "start" failed',
                          error.message)

    def test_execute_start_timeout(self):
        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            mock_client.return_value = MockCloudifyRestClient()
            poll_with_timeout_test = \
                'cloudify_types.component.polling.poll_with_timeout'
            with mock.patch(poll_with_timeout_test) as poll:
                poll.return_value = False
                error = self.assertRaises(NonRecoverableError,
                                          execute_start,
                                          deployment_id='dep_name',
                                          workflow_id='install',
                                          timeout=MOCK_TIMEOUT)
                self.assertIn(
                    'Execution timeout',
                    error.message)

    def test_execute_start_succeeds(self):
        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            mock_client.return_value = MockCloudifyRestClient()
            poll_with_timeout_test = \
                'cloudify_types.component.polling.poll_with_timeout'
            with mock.patch(poll_with_timeout_test) as poll:
                poll.return_value = True
                output = execute_start(operation='execute_workflow',
                                       deployment_id='dep_name',
                                       workflow_id='install',
                                       timeout=MOCK_TIMEOUT)
                self.assertTrue(output)

    def test_execute_start_succeeds_not_finished(self):
        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            mock_client.return_value = MockCloudifyRestClient()
            poll_with_timeout_test = \
                'cloudify_types.component.component.Component.' \
                'verify_execution_successful'
            with mock.patch(poll_with_timeout_test) as poll:
                poll.return_value = False
                output = execute_start(operation='execute_workflow',
                                       deployment_id='dep_name',
                                       workflow_id='install',
                                       timeout=MOCK_TIMEOUT)
                self.assertTrue(output)

    def test_execute_start_succeeds_not_existing_node_type(self):
        self._ctx = self.get_mock_ctx('test', node_type='node.weird')
        current_ctx.set(self._ctx)

        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            mock_client.return_value = MockCloudifyRestClient()
            poll_with_timeout_test = \
                'cloudify_types.component.polling.poll_with_timeout'
            with mock.patch(poll_with_timeout_test) as poll:
                poll.return_value = True

                self.assertRaises(NonRecoverableError,
                                  execute_start,
                                  operation='execute_workflow',
                                  deployment_id='dep_name',
                                  workflow_id='install',
                                  timeout=MOCK_TIMEOUT)

    def test_post_execute_client_error(self):
        cfy_mock_client = MockCloudifyRestClient()
        cfy_mock_client.deployments.outputs.get = mock.MagicMock(
            side_effect=CloudifyClientError('Mistake'))

        poll_with_timeout_test = ('cloudify_types.component.component.'
                                  'Component.verify_execution_successful')

        with mock.patch(
            'cloudify_types.component.component.CloudifyClient'
        ) as mock_local_client:
            mock_local_client.return_value = cfy_mock_client

            with mock.patch(poll_with_timeout_test) as poll:
                poll.return_value = False
                self.assertRaises(NonRecoverableError,
                                  execute_start,
                                  operation='execute_workflow',
                                  deployment_id='dep_name',
                                  workflow_id='install',
                                  client={'host': 'localhost'},
                                  timeout=MOCK_TIMEOUT)
