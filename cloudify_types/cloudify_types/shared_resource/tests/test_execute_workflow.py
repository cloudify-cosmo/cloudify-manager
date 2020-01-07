# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
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
import copy

from cloudify.state import current_ctx
from cloudify.mocks import MockCloudifyContext
from cloudify.exceptions import NonRecoverableError

from cloudify_types.component.constants import CAPABILITIES

from ..operations import execute_workflow
from ..constants import SHARED_RESOURCE_TYPE
from .base_test_suite import TestSharedResourceBase, NODE_PROPS


class TestExecuteWorkflow(TestSharedResourceBase):

    @staticmethod
    def get_mock_ctx(test_name,
                     mock_node_type,
                     retry_number=0,
                     node_props=NODE_PROPS):
        def mock_retry(_):
            return 'RETRIED'

        operation = {
            'retry_number': retry_number
        }

        target_node_ctx = MockCloudifyContext(
            node_id=test_name,
            node_name=test_name,
            node_type=mock_node_type,
            deployment_id=test_name,
            operation=operation,
            properties=node_props
        )
        ctx = MockCloudifyContext(
            target=target_node_ctx
        )
        ctx.operation._operation_context = {'name': 'some.test'}
        ctx.operation.retry = lambda msg: mock_retry(msg)

        return ctx

    def setUp(self):
        super(TestExecuteWorkflow, self).setUp()
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
        super(TestExecuteWorkflow, self).tearDown()

    def test_basic_run(self):
        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            self.cfy_mock_client.deployments.capabilities.get = \
                mock.MagicMock(return_value={'capabilities': {}})
            mock_client.return_value = self.cfy_mock_client
            poll_with_timeout_test = \
                'cloudify_types.component.polling.poll_with_timeout'
            with mock.patch(poll_with_timeout_test) as poll:
                poll.return_value = True
                execute_workflow('test',
                                 parameters={})

    def test_failed_run_on_non_shared_resource_node(self):
        self._ctx = self.get_mock_ctx('test', 'not_shared_resource')
        current_ctx.set(self._ctx)

        self.assertRaises(NonRecoverableError, execute_workflow,
                          'test',
                          parameters={})

    def test_failure_after_execution_failed(self):
        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            mock_client.return_value = self.cfy_mock_client
            poll_with_timeout_test = \
                'cloudify_types.component.polling.poll_with_timeout'
            with mock.patch(poll_with_timeout_test) as poll:
                poll.return_value = True
                verify_execution_state_patch = (
                    'cloudify_types.shared_resource.'
                    'execute_shared_resource_workflow.verify_execution_state')
                with mock.patch(verify_execution_state_patch) as verify:
                    verify.return_value = False
                    self.assertRaises(NonRecoverableError, execute_workflow,
                                      'test',
                                      parameters={}
                                      )

    def test_retrying_after_waiting_all_executions_timed_out(self):
        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            mock_client.return_value = self.cfy_mock_client
            poll_with_timeout_test = (
                'cloudify_types.shared_resource.'
                'execute_shared_resource_workflow.poll_with_timeout')
            with mock.patch(poll_with_timeout_test) as poll:
                poll.return_value = False
                result = execute_workflow('test',
                                          parameters={})
                self.assertEqual(result, 'RETRIED')

    def test_cloudify_configuration_used(self):
        shared_resources_with_client = copy.deepcopy(NODE_PROPS)
        shared_resources_with_client['client'] = {'test': 1}
        self._ctx = self.get_mock_ctx('test',
                                      SHARED_RESOURCE_TYPE,
                                      node_props=shared_resources_with_client)
        current_ctx.set(self._ctx)

        with mock.patch('cloudify_types.shared_resource.'
                        'execute_shared_resource_workflow.'
                        'CloudifyClient') as mock_client:
            self.cfy_mock_client.deployments.capabilities.get = \
                mock.MagicMock(return_value={
                    CAPABILITIES:
                        {'test': 1}
                })
            mock_client.return_value = self.cfy_mock_client
            poll_with_timeout_test = (
                'cloudify_types.shared_resource.'
                'execute_shared_resource_workflow.poll_with_timeout')
            with mock.patch(poll_with_timeout_test) as poll:
                poll.return_value = True
                verify_execution_state_patch = (
                    'cloudify_types.shared_resource.'
                    'execute_shared_resource_workflow.verify_execution_state')
                with mock.patch(verify_execution_state_patch) as verify:
                    verify.return_value = True
                    execute_workflow('test',
                                     parameters={})
                    self.assertEqual(mock_client.called, True)
                    self.assertEqual(
                        {'test': 1},
                        (self._ctx.target.instance.runtime_properties
                            [CAPABILITIES]))
