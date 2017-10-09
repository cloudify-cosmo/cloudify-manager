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

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource


class TestConcurrentUpdate(AgentlessTestCase):

    def test_update_runtime_properties(self):
        dsl_path = resource("dsl/concurrent_update.yaml")

        # testing set property
        deployment, _ = self.deploy_application(dsl_path)
        self.execute_workflow(
            workflow_name='increment_counter_workflow',
            deployment_id=deployment.id,
            wait_for_execution=False
        )
        execution = self.execute_workflow(
            workflow_name='increment_counter_workflow',
            deployment_id=deployment.id,
            wait_for_execution=True,
            force=True
        )
        node_id = self.client.node_instances.list(
            deployment_id=deployment.id)[0].id
        node_runtime_props = self.client.node_instances.get(
            node_id).runtime_properties
        self.assertEqual(2, node_runtime_props['counter'])
        self._assert_operation_retried(execution)

    def _assert_operation_retried(self, execution):
        found = False
        events, _ = self.client.events.get(
            execution_id=execution.id,
            include_logs=True
        )
        for message in [e['message'] for e in events]:
            if '[try number 2]' in message:
                found = True
                break

        self.assertTrue(found, 'Expecting to see multiple retries, '
                               'but only one found')
