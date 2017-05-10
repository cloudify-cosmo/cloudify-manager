########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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

from integration_tests.tests.test_cases import BaseTestCase
from integration_tests.framework import riemann
from integration_tests.tests.utils import do_retries
from integration_tests.tests.utils import get_resource as resource


class PoliciesTestsBase(BaseTestCase):
    NUM_OF_INITIAL_WORKFLOWS = 2

    def tearDown(self):
        super(PoliciesTestsBase, self).tearDown()
        riemann.reset_data_and_restart()

    def launch_deployment(self, yaml_file, expected_num_of_node_instances=1):
        deployment, _ = self.deploy_application(resource(yaml_file))
        self.deployment = deployment
        self.node_instances = self.client.node_instances.list(deployment.id)
        self.assertEqual(
                expected_num_of_node_instances,
                len(self.node_instances)
        )
        self.wait_for_executions(self.NUM_OF_INITIAL_WORKFLOWS,
                                 expect_exact_count=False)

    def get_node_instance_by_name(self, name):
        for nodeInstance in self.node_instances:
            if nodeInstance.node_id == name:
                return nodeInstance

    def wait_for_executions(self, expected_count, expect_exact_count=True):
        def assertion():
            executions = self.client.executions.list(
                    deployment_id=self.deployment.id)
            if expect_exact_count:
                self.assertEqual(len(executions), expected_count)
            else:
                self.assertGreaterEqual(len(executions), expected_count)
        self.do_assertions(assertion)

    def wait_for_invocations(self, deployment_id, expected_count):
        def assertion():
            invocations = self.get_plugin_data(
                    plugin_name='testmockoperations',
                    deployment_id=deployment_id
            )['mock_operation_invocation']
            self.assertEqual(expected_count, len(invocations))
            return invocations
        return do_retries(assertion)

    def publish(self, metric, ttl=60, node_name='node',
                service='service', node_id=''):
        if node_id == '':
            node_id = self.get_node_instance_by_name(node_name).id
        deployment_id = self.deployment.id
        self.publish_riemann_event(
                deployment_id,
                node_name=node_name,
                node_id=node_id,
                metric=metric,
                service='{}.{}.{}.{}'.format(
                        deployment_id,
                        service,
                        node_name,
                        node_id
                ),
                ttl=ttl
        )
