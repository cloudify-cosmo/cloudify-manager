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
from ..polling import (
    blueprint_id_exists,
    deployment_id_exists,
    poll_with_timeout,
    redirect_logs,
    is_component_execution_at_state,
    is_all_executions_finished)


class TestPolling(ComponentTestBase):

    def test_blueprint_id_exists_no_blueprint(self):
        output = blueprint_id_exists(self.cfy_mock_client, 'blu_name')
        self.assertFalse(output)

    def test_blueprint_id_exists_with_existing_blueprint(self):
        blueprint_name = 'blu_name'
        self.cfy_mock_client.blueprints.set_existing_objects([1])

        output = blueprint_id_exists(self.cfy_mock_client, blueprint_name)
        self.assertTrue(output)

    def test_deployment_id_exists_no_deployment(self):
        output = deployment_id_exists(self.cfy_mock_client, 'dep_name')
        self.assertFalse(output)

    def test_deployment_id_exists_with_existing_deployment(self):
        self.cfy_mock_client.deployments.set_existing_objects([1])
        self.assertTrue(deployment_id_exists(self.cfy_mock_client, 'test'))

    def test_find_blueprint_handle_client_error(self):

        def mock_return(*_, **__):
            raise CloudifyClientError('Mistake')

        self.cfy_mock_client.blueprints.list = mock_return
        output = self.assertRaises(
            NonRecoverableError,
            blueprint_id_exists,
            self.cfy_mock_client,
            'blu_name')
        self.assertIn('Blueprint search failed', str(output))

    def test_find_deployment_handle_client_error(self):

        def mock_return(*_, **__):
            raise CloudifyClientError('Mistake')

        self.cfy_mock_client.deployments.list = mock_return
        output = self.assertRaises(
            NonRecoverableError,
            deployment_id_exists,
            self.cfy_mock_client,
            'dep_name')
        self.assertIn('Deployment search failed', str(output))

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
        self.cfy_mock_client.executions.set_existing_objects([{
            'id': 'blu_name',
            'is_system_workflow': True,
            'status': 'started'
        }])

        self.assertFalse(is_all_executions_finished(
            self.cfy_mock_client))

    def test_dep_system_workflows_finished_matching_executions(self):
        self.cfy_mock_client.blueprints.set_existing_objects([
            {'id': 'blu_name',
             'is_system_workflow': True,
             'status': 'terminated'}])
        self.assertTrue(is_all_executions_finished(self.cfy_mock_client))

    def test_dep_system_workflows_finished_raises(self):

        def mock_return(*_, **__):
            raise CloudifyClientError('Mistake')

        self.cfy_mock_client.executions.list = mock_return

        output = self.assertRaises(NonRecoverableError,
                                   is_all_executions_finished,
                                   self.cfy_mock_client)
        self.assertIn('failed', output.message)

    def test_dep_workflow_in_state_pollster_no_executions(self):
        self.assertFalse(is_component_execution_at_state(self.cfy_mock_client,
                                                         'test',
                                                         'terminated'))

    def test_dep_workflow_in_state_pollster_matching_executions(self):
        deployment_id = 'dep_name'
        response = self.cfy_mock_client.executions.get()
        response['id'] = deployment_id
        response['status'] = 'terminated'

        def mock_return(*_, **__):
            return response

        self.cfy_mock_client.executions.get = mock_return
        output = is_component_execution_at_state(self.cfy_mock_client,
                                                 deployment_id,
                                                 'terminated',
                                                 execution_id='_exec_id')
        self.assertTrue(output)

    def test_dep_workflow_in_state_pollster_matching_executions_logs(self):
        deployment_id = 'dep_name'

        def mock_return(*_, **__):
            response = dict()
            response['id'] = deployment_id
            response['status'] = 'terminated'
            return response

        self.cfy_mock_client.executions.get = mock_return
        output = is_component_execution_at_state(self.cfy_mock_client,
                                                 deployment_id,
                                                 'terminated',
                                                 True)
        self.assertTrue(output)

    def test_dep_workflow_in_state_pollster_matching_state(self):

        def mock_return(*_, **__):
            response = dict()
            response['status'] = 'terminated'
            response['workflow_id'] = 'workflow_id1'
            return response

        self.cfy_mock_client.executions.get = mock_return
        output = is_component_execution_at_state(self.cfy_mock_client,
                                                 'dep_name',
                                                 state='terminated',
                                                 execution_id='_exec_id')
        self.assertTrue(output)

    def test_dep_workflow_in_state_pollster_raises(self):

        def mock_return(*_, **__):
            raise CloudifyClientError('Mistake')

        self.cfy_mock_client.executions.get = mock_return
        output = self.assertRaises(NonRecoverableError,
                                   is_component_execution_at_state,
                                   self.cfy_mock_client,
                                   'dep_name',
                                   'terminated')
        self.assertIn('failed', output.message)

    def test_component_logs_redirect_predefined_level(self):
        self.cfy_mock_client.events.set_existing_objects([{
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

        redirect_logs(self.cfy_mock_client, 'some_execution_id')
        self._ctx.logger.log.assert_called_with(
            40,
            '2017-03-22T11:41:59.169Z [vm_ke9e2d.create] Successfully '
            'configured cfy-agent')

    def test_component_logs_redirect_unknown_level(self):
        self.cfy_mock_client.events.set_existing_objects([{
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

        redirect_logs(self.cfy_mock_client, 'some_execution_id')
        self._ctx.logger.log.assert_called_with(
            20,
            "2017-03-22T11:42:00.083Z [vm_ke9e2d.create] Task succeeded "
            "'cloudify_agent.installer.operations.create'")

    def test_component_logs_empty_infinity(self):
        redirect_logs(self.cfy_mock_client, 'some_execution_id')
        self._ctx.logger.log.assert_called_with(
            20,
            "Returned nothing, let's get logs next time.")
