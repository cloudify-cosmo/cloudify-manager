########
# Copyright (c) 2020 Cloudify Platform Ltd. All rights reserved
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

import os
import time
import pytest

from cloudify.models_states import PluginInstallationState

from integration_tests import AgentTestCase
from integration_tests.tests.utils import get_resource as resource

pytestmark = pytest.mark.group_plugins


@pytest.mark.usefixtures('dockercompute_plugin')
@pytest.mark.usefixtures('cloudmock_plugin')
class PluginInstallationTest(AgentTestCase):
    def _wait_for(self, for_what, how_long):
        for _ in range(how_long):
            if for_what():
                return True
            time.sleep(1)
        else:
            return False

    def _mgmtworker_plugin_dir(self, plugin):
        return os.path.join(
            '/opt/mgmtworker/env/plugins',
            plugin.tenant_name,
            plugin.package_name,
            plugin.package_version
        )

    def _agent_plugin_dir(self, agent_id, plugin):
        return os.path.join(
            self.env.execute_on_manager([
                'bash', '-c', 'echo ~cfyuser'
            ]).strip(),
            agent_id,
            'plugins',
            plugin.tenant_name,
            plugin.package_name,
            plugin.package_version
        )

    def test_plugin_from_source(self):
        dsl_path = resource('dsl/agent_tests/with_agent_source_plugin.yaml')
        deployment, _ = self.deploy_application(dsl_path)
        mgmtworker_plugin_dir = os.path.join(
            '/opt/mgmtworker/env/source_plugins',
            'default_tenant',
            deployment.id,
            'sourceplugin',
            '0.0.0'
        )
        # the plugin sets the 'ok' runtime property, let's check that it
        # did run on both the mgmtworker and the agent
        node1 = self.client.node_instances.list(
            deployment_id=deployment.id,
            node_id='node1'
        )[0]
        node2 = self.client.node_instances.list(
            deployment_id=deployment.id,
            node_id='node2'
        )[0]
        assert node1.runtime_properties.get('ok')
        assert node2.runtime_properties.get('ok')
        assert self.directory_exists(mgmtworker_plugin_dir)
        self.undeploy_application(deployment.id, is_delete_deployment=True)
        assert not self.directory_exists(mgmtworker_plugin_dir)

    def test_plugin_installation_state(self):
        """Installing/deleting plugins creates/deletes directories.

        Also, the installation state in the db is updated.
        """
        dsl_path = resource('dsl/agent_tests/with_agent.yaml')
        deployment, _ = self.deploy_application(dsl_path)
        cloudmock = self.client.plugins.list(package_name='cloudmock')[0]
        mgmtworker_plugin_dir = self._mgmtworker_plugin_dir(cloudmock)
        agent = self.client.agents.list()[0].id
        agent_plugin_dir = self._agent_plugin_dir(agent, cloudmock)

        assert not self.directory_exists(mgmtworker_plugin_dir)
        assert not self.directory_exists(agent_plugin_dir)

        def plugin_installed():
            states = self.client.plugins.get(cloudmock.id).installation_state
            all_installed = all(
                state['state'] == PluginInstallationState.INSTALLED
                for state in states)
            return states and all_installed

        self.client.plugins.install(
            cloudmock.id,
            agents=[agent],
            managers=[m.hostname for m in self.client.manager.get_managers()])
        if not self._wait_for(plugin_installed, 30):
            pytest.fail('Plugins not installed after 30 seconds')
        assert self.directory_exists(mgmtworker_plugin_dir)
        assert self.directory_exists(agent_plugin_dir)

        def plugin_deleted():
            agent_plugin_gone = not self.directory_exists(agent_plugin_dir)
            mgmt_plugin_gone = not self.directory_exists(mgmtworker_plugin_dir)
            return agent_plugin_gone and mgmt_plugin_gone
        self.client.plugins.delete(cloudmock.id)
        if not self._wait_for(plugin_deleted, 30):
            pytest.fail('Plugins not deleted after 30 seconds')

        self.undeploy_application(deployment.id, is_delete_deployment=True)
