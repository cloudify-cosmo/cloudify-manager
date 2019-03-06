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

from .base_test_suite import ComponentTestBase
from .client_mock import MockCloudifyRestClient
from ..polling import (
    any_bp_by_id,
    any_dep_by_id,
    resource_by_id,
    poll_with_timeout,
    redirect_logs,
    is_component_workflow_at_state,
    is_system_workflows_finished,
    poll_workflow_after_execute)


class TestPolling(ComponentTestBase):

    def test_any_bp_by_id_no_blueprint(self):
        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            cfy_mock_client = MockCloudifyRestClient()
            mock_client.return_value = cfy_mock_client
            output = any_bp_by_id(mock_client, 'blu_name')
            self.assertFalse(output)

    def test_any_bp_by_id_with_blueprint(self):
        blueprint_name = 'blu_name'
        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            cfy_mock_client = MockCloudifyRestClient()
            list_response = cfy_mock_client.blueprints.list()
            list_response[0]['id'] = blueprint_name

            def mock_return(*args, **kwargs):
                del args, kwargs
                return list_response

            cfy_mock_client.blueprints.list = mock_return
            mock_client.return_value = cfy_mock_client
            output = any_bp_by_id(cfy_mock_client, blueprint_name)
            self.assertTrue(output)

    def test_any_dep_by_id_no_deployment(self):
        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            cfy_mock_client = MockCloudifyRestClient()
            mock_client.return_value = cfy_mock_client
            output = any_dep_by_id(mock_client, 'dep_name')
            self.assertFalse(output)

    def test_any_dep_by_id_with_deployment(self):
        blueprint_name = 'test'
        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            cfy_mock_client = MockCloudifyRestClient()
            list_response = cfy_mock_client.deployments.list()
            list_response[0]['id'] = blueprint_name

            def mock_return(*args, **kwargs):
                del args, kwargs
                return list_response

            cfy_mock_client.deployments.list = mock_return
            mock_client.return_value = cfy_mock_client
            output = any_dep_by_id(cfy_mock_client, blueprint_name)
            self.assertTrue(output)

    def test_resource_by_id_client_error(self):

        def mock_return(*args, **kwargs):
            del args, kwargs
            raise CloudifyClientError('Mistake')

        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            cfy_mock_client = MockCloudifyRestClient()
            cfy_mock_client.deployments.list = mock_return
            mock_client.return_value = mock_return
            output = self.assertRaises(
                NonRecoverableError,
                resource_by_id,
                cfy_mock_client,
                'dep_name',
                'deployments')
            self.assertIn('failed', output.message)

    def test_poll_with_timeout_timeout(self):
        mock_timeout = .0001
        mock_interval = .0001

        mock_pollster = mock.MagicMock
        output = poll_with_timeout(mock_pollster,
                                   mock_timeout,
                                   mock_interval)
        self.assertFalse(output)

    def test_poll_with_timeout_expected(self):
        mock_timeout = .0001
        mock_interval = .0001

        def mock_return(*args, **kwargs):
            del args, kwargs
            return True

        output = poll_with_timeout(
            lambda: mock_return(),
            mock_timeout,
            mock_interval,
            True)
        self.assertTrue(output)

    def test_dep_system_workflows_finished_no_executions(self):
        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            cfy_mock_client = MockCloudifyRestClient()
            list_response = cfy_mock_client.deployments.list()
            list_response[0]['id'] = 'blu_name'
            list_response[0]['is_system_workflow'] = True
            list_response[0]['status'] = 'started'

            def mock_return(*args, **kwargs):
                del args, kwargs
                return list_response

            cfy_mock_client.executions.list = mock_return
            mock_client.return_value = cfy_mock_client
            output = is_system_workflows_finished(
                cfy_mock_client)
            self.assertFalse(output)

    def test_dep_system_workflows_finished_matching_executions(self):
        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            cfy_mock_client = MockCloudifyRestClient()
            list_response = cfy_mock_client.blueprints.list()
            list_response[0]['id'] = 'blu_name'
            list_response[0]['is_system_workflow'] = True
            list_response[0]['status'] = 'terminated'

            def mock_return(*args, **kwargs):
                del args, kwargs
                return list_response

            cfy_mock_client.executions.list = mock_return
            mock_client.return_value = cfy_mock_client
            output = is_system_workflows_finished(cfy_mock_client)
            self.assertTrue(output)

    def test_dep_system_workflows_finished_raises(self):
        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            cfy_mock_client = MockCloudifyRestClient()
            list_response = cfy_mock_client.blueprints.list()
            list_response[0]['id'] = 'blu_name'

            def mock_return(*args, **kwargs):
                del args, kwargs
                raise CloudifyClientError('Mistake')

            cfy_mock_client.executions.list = mock_return
            mock_client.return_value = cfy_mock_client
            output = self.assertRaises(NonRecoverableError,
                                       is_system_workflows_finished,
                                       cfy_mock_client)
            self.assertIn('failed', output.message)

    def test_dep_workflow_in_state_pollster_no_executions(self):
        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            cfy_mock_client = MockCloudifyRestClient()
            list_response = cfy_mock_client.deployments.list()
            list_response[0]['id'] = 'test'

            mock_client.return_value = cfy_mock_client
            output = is_component_workflow_at_state(cfy_mock_client,
                                                    'test',
                                                    'terminated')
            self.assertFalse(output)

    def test_dep_workflow_in_state_pollster_matching_executions(self):
        deployment_id = 'dep_name'
        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            cfy_mock_client = MockCloudifyRestClient()
            response = cfy_mock_client.executions.get()
            response['id'] = deployment_id
            response['status'] = 'terminated'

            def mock_return(*args, **kwargs):
                del args, kwargs
                return response

            cfy_mock_client.executions.get = mock_return
            mock_client.return_value = cfy_mock_client
            output = is_component_workflow_at_state(cfy_mock_client,
                                                    deployment_id,
                                                    'terminated',
                                                    execution_id='_exec_id')
            self.assertTrue(output)

    def test_dep_workflow_in_state_pollster_matching_executions_logs(self):
        deployment_id = 'dep_name'
        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            cfy_mock_client = MockCloudifyRestClient()
            response = cfy_mock_client.executions.get()

            cfy_mock_client.events._set([])

            response['id'] = deployment_id
            response['status'] = 'terminated'

            def mock_return(*args, **kwargs):
                del args, kwargs
                return response

            cfy_mock_client.executions.get = mock_return
            mock_client.return_value = cfy_mock_client
            output = is_component_workflow_at_state(cfy_mock_client,
                                                    deployment_id,
                                                    'terminated',
                                                    True)
            self.assertTrue(output)

    def test_dep_workflow_in_state_pollster_matching_state(self):
        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            cfy_mock_client = MockCloudifyRestClient()
            response = cfy_mock_client.executions.get()
            response['status'] = 'terminated'
            response['workflow_id'] = 'workflow_id1'

            def mock_return(*args, **kwargs):
                del args, kwargs
                return response

            cfy_mock_client.executions.get = mock_return
            mock_client.return_value = cfy_mock_client
            output = is_component_workflow_at_state(cfy_mock_client,
                                                    'dep_name',
                                                    state='terminated',
                                                    execution_id='_exec_id')
            self.assertTrue(output)

    def test_dep_workflow_in_state_pollster_raises(self):
        deployment_id = 'dep_name'
        with mock.patch('cloudify.manager.get_rest_client') as mock_client:
            cfy_mock_client = MockCloudifyRestClient()
            response = cfy_mock_client.executions.get()
            response['id'] = deployment_id

            def mock_return(*args, **kwargs):
                del args, kwargs
                raise CloudifyClientError('Mistake')

            cfy_mock_client.executions.get = mock_return
            mock_client.return_value = cfy_mock_client
            output = self.assertRaises(NonRecoverableError,
                                       is_component_workflow_at_state,
                                       cfy_mock_client,
                                       deployment_id,
                                       'terminated')
            self.assertIn('failed', output.message)

    def test_poll_workflow_after_execute_failed(self):
        with mock.patch(
                'cloudify_types.component.polling.poll_with_timeout') \
                as mocked_fn:
            mocked_fn.return_value = False
            output = self.assertRaises(NonRecoverableError,
                                       poll_workflow_after_execute,
                                       None, None, None, None, None, None)
            self.assertIn('Execution timeout', output.message)

    def test_poll_workflow_after_execute_success(self):
        with mock.patch(
                'cloudify_types.component.polling.poll_with_timeout') \
                as mocked_fn:
            mocked_fn.return_value = True
            output = poll_workflow_after_execute(
                None, None, None, None, None, None)
            self.assertTrue(output)

    def test_dep_logs_redirect_predefined_level(self):
        cfy_mock_client = MockCloudifyRestClient()

        cfy_mock_client.events._set([{
            "node_instance_id": "vm_ke9e2d",
            "operation": "cloudify.interfaces.cloudify_agent.create",
            "blueprint_id": "linuxbp1",
            "timestamp": "2017-03-22T11:42:00.484Z",
            "message": "Successfully configured cfy-agent",
            "level": "error",
            "node_name": "vm",
            "workflow_id": "install",
            "reported_timestamp": "2017-03-22T11:41:59.169Z",
            "deployment_id": "linuxdp1",
            "type": "cloudify_log",
            "execution_id": "19ce78d6-babc-4a18-ba8e-74b853f2b387",
            "logger": "22e710c6-18b8-4e96-b8a3-2104b81c5bfc"
        }])

        redirect_logs(cfy_mock_client, 'some_execution_id')
        self._ctx.logger.log.assert_called_with(
            40,
            '2017-03-22T11:41:59.169Z [vm_ke9e2d.create] Successfully '
            'configured cfy-agent')

    def test_dep_logs_redirect_unknown_level(self):
        cfy_mock_client = MockCloudifyRestClient()

        cfy_mock_client.events._set([{
            "node_instance_id": "vm_ke9e2d",
            "event_type": "task_succeeded",
            "operation": "cloudify.interfaces.cloudify_agent.create",
            "blueprint_id": "linuxbp1",
            "timestamp": "2017-03-22T11:42:00.788Z",
            "message": (
                "Task succeeded 'cloudify_agent.installer.operations.create'"
            ),
            "node_name": "vm",
            "workflow_id": "install",
            "error_causes": None,
            "reported_timestamp": "2017-03-22T11:42:00.083Z",
            "deployment_id": "linuxdp1",
            "type": "cloudify_event",
            "execution_id": "19ce78d6-babc-4a18-ba8e-74b853f2b387"
        }])

        redirect_logs(cfy_mock_client, 'some_execution_id')
        self._ctx.logger.log.assert_called_with(
            20,
            "2017-03-22T11:42:00.083Z [vm_ke9e2d.create] Task succeeded "
            "'cloudify_agent.installer.operations.create'")

    def test_dep_logs_empty_infinity(self):
        cfy_mock_client = MockCloudifyRestClient()

        cfy_mock_client.events._set([], False)

        redirect_logs(cfy_mock_client, 'some_execution_id')
        self._ctx.logger.log.assert_called_with(
            20,
            "Returned nothing, let's get logs next time.")
