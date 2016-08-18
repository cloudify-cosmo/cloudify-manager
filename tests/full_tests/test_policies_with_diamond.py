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


from testenv import AgentTestCase
from workflow_tests.test_policies import PoliciesTestsBase
from testenv.utils import get_resource as resource
from testenv.utils import deploy_application as deploy


class TestPoliciesWithDiamond(AgentTestCase, PoliciesTestsBase):

    def test_policies_flow_with_diamond(self):
        dsl_path = resource('dsl/with_policies_and_diamond.yaml')
        self.deployment, _ = deploy(dsl_path)
        expected_metric_value = 42
        self.wait_for_executions(3)
        invocations = self.wait_for_invocations(self.deployment.id, 1)
        self.assertEqual(expected_metric_value, invocations[0]['metric'])
