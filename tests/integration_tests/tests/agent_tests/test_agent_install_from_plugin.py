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

import pytest

from integration_tests import AgentTestWithPlugins

pytestmark = pytest.mark.group_agents


@pytest.mark.usefixtures('dockercompute_plugin')
class TestWorkflow(AgentTestWithPlugins):
    def test_agent_install_from_plugin(self):
        dsl_path = self.make_yaml_file("""
tosca_definitions_version: cloudify_dsl_1_4

imports:
    - cloudify/types/types.yaml
    - plugin:dockercompute

node_templates:
  setup_host:
    type: cloudify.nodes.docker.Compute
""")
        deployment, _ = self.deploy_application(dsl_path)
        self.undeploy_application(deployment.id)

    def test_install_exec_temp_path(self):
        # like test_agent_install_from_plugin, but check that we can still
        # install/uninstall the agent when executable_temp_path is set
        dsl_path = self.make_yaml_file("""
tosca_definitions_version: cloudify_dsl_1_4

imports:
    - cloudify/types/types.yaml
    - plugin:dockercompute

node_templates:
  setup_host:
    type: cloudify.nodes.docker.Compute
    properties:
        agent_config:
            install_method: plugin
            process_management:
                name: detach
            executable_temp_path: /tmp/somethingelse
""")
        deployment, _ = self.deploy_application(dsl_path)
        self.undeploy_application(deployment.id)
