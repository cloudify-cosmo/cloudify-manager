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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import uuid

from integration_tests import AgentTestWithPlugins
from integration_tests.tests.agentless_tests.policies import PoliciesTestsBase
from integration_tests.tests.utils import get_resource as resource


class TestPoliciesWithDiamond(AgentTestWithPlugins, PoliciesTestsBase):

    def setUp(self):
        super(TestPoliciesWithDiamond, self).setUp()
        self.setup_deployment_id = 'd{0}'.format(uuid.uuid4())
        self.setup_node_id = 'node'

    def test_policies_flow_with_diamond(self):
        dsl_path = resource("dsl/with_policies_and_diamond.yaml")
        self.deployment, _ = self.deploy_application(
            dsl_path,
            deployment_id=self.setup_deployment_id
        )
        expected_metric_value = 42
        self.wait_for_executions(3)
        invocations = self.wait_for_invocations(self.deployment.id, 1)
        self.assertEqual(expected_metric_value, invocations[0]['metric'])
