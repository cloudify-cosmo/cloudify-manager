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

from cloudify.exceptions import NonRecoverableError
from cloudify_rest_client.exceptions import CloudifyClientError

from ..constants import CAPABILITIES
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
        self.total_patch = \
            mock.patch('cloudify_rest_client.responses.Pagination.total',
                       new_callable=mock.PropertyMock)
        self.total_patch = self.total_patch.start()
        self.total_patch.return_value = 1

        self.offset_patch = \
            mock.patch('cloudify_rest_client.responses.Pagination.offset',
                       new_callable=mock.PropertyMock)
        self.offset_patch = self.offset_patch.start()
        self.offset_patch.return_value = 1

    def tearDown(self):
        self.offset_patch.stop()
        self.total_patch.stop()
        super(TestExecute, self).tearDown()

    @classmethod
    def tearDownClass(cls):
        cls.sleep_mock.stop()
        super(TestExecute, cls).tearDownClass()

    def test_execute_start_rest_client_error(self):
        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            self.cfy_mock_client.executions.start = REST_CLIENT_EXCEPTION
            mock_client.return_value = self.cfy_mock_client
            with self.assertRaisesRegexp(
                    NonRecoverableError, 'action "start" failed'):
                execute_start(deployment_id='dep_name', workflow_id='install')

    def test_execute_start_timeout(self):
        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            mock_client.return_value = self.cfy_mock_client
            with self.assertRaisesRegexp(
                    NonRecoverableError, 'Execution timed out'):
                execute_start(
                    deployment_id='dep_name',
                    workflow_id='install',
                    timeout=MOCK_TIMEOUT)

    def test_execute_start_succeeds(self):
        test_capabilities = {'test': 1}
        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            mock_client.return_value = self.cfy_mock_client
            self.cfy_mock_client.deployments.capabilities.get =\
                mock.MagicMock(return_value={
                    'capabilities': test_capabilities})
            poll_with_timeout_test = \
                'cloudify_types.component.polling.poll_with_timeout'
            with mock.patch(poll_with_timeout_test) as poll:
                poll.return_value = True
                output = execute_start(operation='execute_workflow',
                                       deployment_id='dep_name',
                                       workflow_id='install',
                                       timeout=MOCK_TIMEOUT)
                self.assertTrue(output)
                self.assertEqual(
                    test_capabilities,
                    (self._ctx.instance.runtime_properties[CAPABILITIES]))

    def test_execute_start_succeeds_not_finished(self):
        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            mock_client.return_value = self.cfy_mock_client
            self.cfy_mock_client.deployments.capabilities.get = \
                mock.MagicMock(return_value={'capabilities': {}})
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
                self.assertEqual(
                    {},
                    (self._ctx.instance.runtime_properties[CAPABILITIES]))

    def test_execute_failing_to_fetch_capabilities(self):
        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            mock_client.return_value = self.cfy_mock_client
            self.cfy_mock_client.deployments.capabilities.get =\
                mock.MagicMock(side_effect=CloudifyClientError(
                               'Failing to get capabilities'))
            poll_with_timeout_test = \
                'cloudify_types.component.polling.poll_with_timeout'
            with mock.patch(poll_with_timeout_test) as poll:
                poll.return_value = True
                self.assertRaises(NonRecoverableError,
                                  execute_start,
                                  deployment_id='dep_name',
                                  workflow_id='install')
