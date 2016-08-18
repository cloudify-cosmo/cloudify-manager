########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

from testenv import TestCase
from testenv.utils import get_resource as resource
from testenv.utils import deploy_application as deploy
from testenv.utils import undeploy_application as undeploy


class TestInstallWorkflowBackwards(TestCase):

    def test_deploy_with_agent_worker_3_2(self):
        dsl_path = resource('dsl/with_agent_worker_3_2.yaml')
        deployment, _ = deploy(dsl_path, timeout_seconds=500)
        deployment_nodes = self.client.node_instances.list(
            deployment_id=deployment.id
        )

        webserver_nodes = filter(lambda node: 'host' not in node.node_id,
                                 deployment_nodes)
        self.assertEquals(1, len(webserver_nodes))
        webserver_node = webserver_nodes[0]
        invocations = self.get_plugin_data(
            plugin_name='mock_agent_plugin',
            deployment_id=deployment.id
        )[webserver_node.id]

        agent_installer_data = self.get_plugin_data(
            plugin_name='agent_installer',
            deployment_id=deployment.id
        )

        self.assertEqual(
            agent_installer_data[webserver_node.host_id]['states'],
            ['created', 'configured', 'started'])

        plugin_installer_data = self.get_plugin_data(
            plugin_name='plugin_installer',
            deployment_id=deployment.id
        )

        self.assertEqual(
            plugin_installer_data[
                webserver_node.host_id
            ]['mock_agent_plugin'],
            ['installed'])

        expected_invocations = ['create', 'start']
        self.assertListEqual(invocations, expected_invocations)

        undeploy(deployment_id=deployment.id)
        invocations = self.get_plugin_data(
            plugin_name='mock_agent_plugin',
            deployment_id=deployment.id
        )[webserver_node.id]

        expected_invocations = ['create', 'start', 'stop', 'delete']
        self.assertListEqual(invocations, expected_invocations)

        # agent on host should have also
        # been stopped and uninstalled
        agent_installer_data = self.get_plugin_data(
            plugin_name='agent_installer',
            deployment_id=deployment.id
        )
        self.assertEqual(
            agent_installer_data[webserver_node.host_id]['states'],
            ['created', 'configured', 'started',
             'stopped', 'deleted'])

    def test_deploy_with_agent_worker_windows_3_2(self):
        dsl_path = resource('dsl/with_agent_worker_windows_3_2.yaml')
        deployment, _ = deploy(dsl_path, timeout_seconds=500)
        deployment_nodes = self.client.node_instances.list(
            deployment_id=deployment.id
        )

        webserver_nodes = filter(lambda node: 'host' not in node.node_id,
                                 deployment_nodes)
        self.assertEquals(1, len(webserver_nodes))
        webserver_node = webserver_nodes[0]
        invocations = self.get_plugin_data(
            plugin_name='mock_agent_plugin',
            deployment_id=deployment.id
        )[webserver_node.id]

        agent_installer_data = self.get_plugin_data(
            plugin_name='windows_agent_installer',
            deployment_id=deployment.id
        )

        self.assertEqual(
            agent_installer_data[webserver_node.host_id]['states'],
            ['created', 'configured', 'started'])

        plugin_installer_data = self.get_plugin_data(
            plugin_name='windows_plugin_installer',
            deployment_id=deployment.id
        )

        self.assertEqual(
            plugin_installer_data[
                webserver_node.host_id
            ]['mock_agent_plugin'],
            ['installed'])

        expected_invocations = ['create', 'start']
        self.assertListEqual(invocations, expected_invocations)

        undeploy(deployment_id=deployment.id)
        invocations = self.get_plugin_data(
            plugin_name='mock_agent_plugin',
            deployment_id=deployment.id
        )[webserver_node.id]

        expected_invocations = ['create', 'start', 'stop', 'delete']
        self.assertListEqual(invocations, expected_invocations)

        # agent on host should have also
        # been stopped and uninstalled
        agent_installer_data = self.get_plugin_data(
            plugin_name='windows_agent_installer',
            deployment_id=deployment.id
        )
        self.assertEqual(
            agent_installer_data[webserver_node.host_id]['states'],
            ['created', 'configured', 'started',
             'stopped', 'deleted'])
