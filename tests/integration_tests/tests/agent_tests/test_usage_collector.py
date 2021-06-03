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
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.
import pytest

from integration_tests import AgentTestCase
from integration_tests.tests.usage_collector_base import TestUsageCollectorBase

pytestmark = pytest.mark.group_usage_collector


class TestUsageCollectorWithAgent(AgentTestCase, TestUsageCollectorBase):
    def setUp(self):
        super(AgentTestCase, self).setUp()
        self.clean_timestamps()

    def tearDown(self):
        super(AgentTestCase, self).tearDown()
        self.clean_usage_collector_log()

    def test_collector_scripts_with_agent(self):
        messages = [
            "Uptime script finished running",
            "Usage script finished running",
            "'customer_id': 'MockCustomer'",
            "'node_instances_count': 1",
            "'compute_count': 1",
            "'agents_count': 1",
            "'premium_edition': True"
        ]
        self.run_scripts_with_deployment("dsl/agent_tests/with_agent.yaml",
                                         messages)
