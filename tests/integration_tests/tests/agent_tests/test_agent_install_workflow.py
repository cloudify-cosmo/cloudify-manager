########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import uuid
from integration_tests import AgentTestWithPlugins, BaseTestCase
from integration_tests.tests.utils import get_resource as resource


class TestWorkflow(AgentTestWithPlugins):
    def test_deploy_with_agent_worker(self):
        # In 4.2, the default (remote) agent installation path only requires
        # the "create" operation
        install_events = [
            "Task succeeded 'cloudify_agent.installer.operations.create'"
        ]
        uninstall_events = [
            "Task succeeded 'cloudify_agent.installer.operations.stop'",
            "Task succeeded 'cloudify_agent.installer.operations.delete'"
        ]
        self._test_deploy_with_agent_worker(
            'dsl/agent_tests/with_agent.yaml',
            install_events,
            uninstall_events
        )

    def test_deploy_with_agent_worker_3_2(self):
        install_events = [
            "Task succeeded 'worker_installer.tasks.install'",
            "Task succeeded 'worker_installer.tasks.start'"
        ]
        uninstall_events = [
            "Task succeeded 'worker_installer.tasks.stop'",
            "Task succeeded 'worker_installer.tasks.uninstall'"
        ]
        self._test_deploy_with_agent_worker(
            'dsl/agent_tests/with_agent_3_2.yaml',
            install_events,
            uninstall_events
        )

    def _test_deploy_with_agent_worker(self,
                                       blueprint,
                                       install_events,
                                       uninstall_events):
        deployment_id = 'd{0}'.format(uuid.uuid4())
        dsl_path = resource(blueprint)
        _, execution_id = self.deploy_application(
            dsl_path,
            deployment_id=deployment_id,
            timeout_seconds=120)

        events = self.client.events.list(execution_id=execution_id,
                                         sort='timestamp')
        filtered_events = [event['message'] for event in events if
                           event['message'] in install_events]

        # Make sure the install events were called (in the correct order)
        self.assertListEqual(install_events, filtered_events)

        execution_id = self.undeploy_application(deployment_id)

        events = self.client.events.list(execution_id=execution_id,
                                         sort='timestamp')
        filtered_events = [event['message'] for event in events if
                           event['message'] in uninstall_events]

        # Make sure the uninstall events were called (in the correct order)
        self.assertListEqual(uninstall_events, filtered_events)

    def test_deploy_with_operation_executor_override(self):
        self.upload_mock_plugin('target-aware-mock')

        self.setup_deployment_id = 'd{0}'.format(uuid.uuid4())
        self.setup_node_id = 'webserver_host'
        dsl_path = resource('dsl/agent_tests/operation_executor_override.yaml')
        _, execution_id = self.deploy_application(
            dsl_path,
            deployment_id=self.setup_deployment_id,
            timeout_seconds=120
        )

        deployment_nodes = self.client.node_instances.list(
            deployment_id=self.setup_deployment_id
        )

        webserver_nodes = [
            node for node in deployment_nodes
            if 'host' not in node.node_id
        ]
        self.assertEquals(1, len(webserver_nodes))
        webserver_node = webserver_nodes[0]
        webserver_host_node = self.client.node_instances.list(
            deployment_id=self.setup_deployment_id,
            node_id='webserver_host'
        )[0]
        create_invocation = self.get_plugin_data(
            plugin_name='target_aware_mock',
            deployment_id=self.setup_deployment_id
        )[webserver_node.id]['create']
        expected_create_invocation = {'target': webserver_host_node.id}
        self.assertEqual(expected_create_invocation, create_invocation)

        # Calling like this because "start" would be written on the manager
        # as opposed to the host (hence the "override")
        start_invocation = BaseTestCase.get_plugin_data(
            self,
            plugin_name='target_aware_mock',
            deployment_id=self.setup_deployment_id
        )[webserver_node.id]['start']
        expected_start_invocation = {'target': 'cloudify.management'}
        self.assertEqual(expected_start_invocation, start_invocation)
