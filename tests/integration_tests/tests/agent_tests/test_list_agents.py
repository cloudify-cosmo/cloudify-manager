########
# Copyright (c) 2013-2019 Cloudify Platform Ltd. All rights reserved
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

import pytest

from integration_tests import AgentTestCase
from integration_tests.tests.utils import get_resource as resource

pytestmark = pytest.mark.group_agents


class TestListAgents(AgentTestCase):

    def test_list_agents(self):
        deployment1, _ = self.deploy_application(resource(
            "dsl/agent_tests/with_agent.yaml"), deployment_id='d1')
        deployment2, _ = self.deploy_application(resource(
            "dsl/agent_tests/with_agent.yaml"), deployment_id='d2')

        agent_list = self.client.agents.list()
        self.assertEqual(len(agent_list.items), 2)
        self.assertEqual(agent_list.metadata['pagination']['total'], 2)

        self.assertIsNotNone(agent_list.items[0]['id'])
        self.assertIsNotNone(agent_list.items[0]['version'])
        self.assertEqual(agent_list.items[0]['install_method'], 'plugin')
        self.assertEqual(agent_list.items[0]['tenant_name'], 'default_tenant')
        self.assertEqual({agent['deployment']
                         for agent in agent_list.items}, {'d1', 'd2'})

        self.undeploy_application(deployment1.id)
        self.undeploy_application(deployment2.id)

    def test_list_agents_not_started(self):
        deployment1, _ = self.deploy_application(resource(
            "dsl/agent_tests/with_agent.yaml"), deployment_id='ns1')
        deployment2 = self.deploy(resource("dsl/agent_tests/with_agent.yaml"),
                                  deployment_id='ns2')

        agent_list = self.client.agents.list()
        self.assertEqual(len(agent_list.items), 1)
        self.assertEqual(agent_list.metadata['pagination']['total'], 1)
        self.undeploy_application(deployment1.id)
        self.delete_deployment(deployment2.id, validate=True)
