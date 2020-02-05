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
        self.cfy_mock_client.executions.start = REST_CLIENT_EXCEPTION
        error = self.assertRaises(NonRecoverableError,
                                  execute_start,
                                  deployment_id='dep_name',
                                  workflow_id='install')
        self.assertIn('action "start" failed', str(error))

    def test_execute_start_timeout(self):
        error = self.assertRaises(NonRecoverableError,
                                  execute_start,
                                  deployment_id='dep_name',
                                  workflow_id='install',
                                  timeout=MOCK_TIMEOUT)
        self.assertIn('Execution timed out', str(error))

    @mock.patch('cloudify_types.component.'
                'polling.poll_with_timeout',
                return_value=True)
    @mock.patch('cloudify_types.shared_resource.'
                'execute_shared_resource_workflow.CloudifyClient')
    def test_execute_start_succeeds(self, mock_client, _):
        test_capabilities = {'test': 1}
        self.cfy_mock_client.deployments.capabilities.get =\
            mock.MagicMock(return_value={
                'capabilities': test_capabilities})
        output = execute_start(operation='execute_workflow',
                               deployment_id='dep_name',
                               workflow_id='install',
                               timeout=MOCK_TIMEOUT)
        self.assertTrue(output)
        self.assertEqual(
            test_capabilities,
            (self._ctx.instance.runtime_properties[CAPABILITIES]))

    @mock.patch('cloudify_types.component.component.Component.'
                'verify_execution_successful',
                return_value=False)
    def test_execute_start_succeeds_not_finished(self, _):
        self.cfy_mock_client.deployments.capabilities.get = \
            mock.MagicMock(return_value={'capabilities': {}})
        output = execute_start(operation='execute_workflow',
                               deployment_id='dep_name',
                               workflow_id='install',
                               timeout=MOCK_TIMEOUT)
        self.assertTrue(output)
        self.assertEqual(
            {},
            (self._ctx.instance.runtime_properties[CAPABILITIES]))

    @mock.patch('cloudify_types.component.'
                'polling.poll_with_timeout',
                return_value=True)
    def test_execute_failing_to_fetch_capabilities(self, _):
        self.cfy_mock_client.deployments.capabilities.get =\
            mock.MagicMock(side_effect=CloudifyClientError(
                               'Failing to get capabilities'))
        self.assertRaises(NonRecoverableError,
                          execute_start,
                          deployment_id='dep_name',
                          workflow_id='install')
