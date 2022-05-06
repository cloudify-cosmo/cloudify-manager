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

import pytest

from integration_tests import AgentTestWithPlugins
from integration_tests.tests.utils import get_resource as resource

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
