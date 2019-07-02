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

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource
from integration_tests.tests.usage_collector_base import TestUsageCollectorBase


class TestUsageCollector(AgentlessTestCase, TestUsageCollectorBase):

    def test_collector_scripts(self):
        messages = [
            "Uptime script finished running",
            "Usage script finished running",
            "'customer_id': 'mock_customer'",
            "'node_instances_count': 1L",
            "'compute_count': 1L",
            "'agents_count': 0L",
            "'premium_edition': True"
        ]
        self.run_scripts_with_deployment("dsl/basic.yaml", messages)

    def test_multi_instance(self):
        messages = [
            "'node_instances_count': 4L",
            "'compute_count': 2L",
        ]
        self.run_scripts_with_deployment("dsl/multi_instance.yaml", messages)

    def test_scaled(self):
        messages = [
            "'node_instances_count': 6L",
            "'compute_count': 2L",
        ]
        self.run_scripts_with_deployment("dsl/scale5.yaml", messages)

    def test_compute_not_started(self):
        deployment = self.deploy(resource("dsl/multi_instance.yaml"))
        messages = [
            "'node_instances_count': 4L",
            "'compute_count': 0L",
        ]
        self.run_collector_scripts_and_assert(messages)
        self.delete_deployment(deployment.id, validate=True)
