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


from testenv import TestCase
from testenv import get_resource as resource
from testenv import deploy_application as deploy
from testenv import send_task

from plugins.testmockoperations.tasks import \
    get_mock_operation_invocations as testmock_get_invocations


class TestPolicies(TestCase):

    def test_policies_flow(self):
        """
        Tests policy/trigger/group creation and processing flow
        """
        dsl_path = resource("dsl/with_policies1.yaml")
        deployment, _ = deploy(dsl_path)
        self.deployment_id = deployment.id
        self.instance_id = self.wait_for_node_instance().id

        metric_value = 123

        self.publish(metric=metric_value)

        self.wait_for_executions(3)
        invocations = self.wait_for_invocations(2)
        self.assertEqual(self.instance_id, invocations[0]['node_id'])
        self.assertEqual(123, invocations[1]['metric'])

    def test_policies_flow2(self):
        """
        Tests policy/trigger/group creation and processing flow
        """
        dsl_path = resource("dsl/with_policies3.yaml")
        deployment, _ = deploy(dsl_path)
        self.deployment_id = deployment.id
        self.instance_id = self.wait_for_node_instance().id
        #
        # metric_value = 123
        #
        # self.publish(metric=metric_value)
        #
        # self.wait_for_executions(3)
        # invocations = self.wait_for_invocations(2)
        # self.assertEqual(self.instance_id, invocations[0]['node_id'])
        # self.assertEqual(123, invocations[1]['metric'])

    def test_threshold_policy(self):
        dsl_path = resource("dsl/with_policies2.yaml")
        deployment, _ = deploy(dsl_path)
        self.deployment_id = deployment.id
        self.instance_id = self.wait_for_node_instance().id

        class Tester(object):

            def __init__(self, test_case, threshold, current_executions,
                         current_invocations):
                self.test_case = test_case
                self.current_invocations = current_invocations
                self.current_executions = current_executions
                self.threshold = threshold

            def publish_above_threshold(self, do_assert):
                self.test_case.logger.info('Publish above threshold')
                self.test_case.publish(self.threshold + 1)
                if do_assert:
                    self.inc()
                    self.assertion(upper=True)

            def publish_below_threshold(self, do_assert):
                self.test_case.logger.info('Publish below threshold')
                self.test_case.publish(self.threshold - 1)
                if do_assert:
                    self.inc()
                    self.assertion(upper=False)

            def inc(self):
                self.current_executions += 1
                self.current_invocations += 1

            def assertion(self, upper):
                self.test_case.logger.info('waiting for {} executions'
                                           .format(self.current_executions))
                self.test_case.wait_for_executions(self.current_executions)
                self.test_case.logger.info('waiting for {} invocations'
                                           .format(self.current_invocations))
                invocations = self.test_case.wait_for_invocations(
                    self.current_invocations)
                if upper:
                    key = 'upper'
                    value = self.threshold + 1
                else:
                    key = 'lower'
                    value = self.threshold - 1
                self.test_case.assertEqual(invocations[-1][key], value,
                                           'key: {}, expected: {}'
                                           .format(key, value))

        tester = Tester(test_case=self,
                        threshold=100,
                        current_executions=2,
                        current_invocations=0)

        for _ in range(2):
            tester.publish_above_threshold(do_assert=True)
            tester.publish_above_threshold(do_assert=False)
            tester.publish_below_threshold(do_assert=True)
            tester.publish_below_threshold(do_assert=False)

    def wait_for_executions(self, expected_count):
        def assertion():
            executions = self.client.executions.list(self.deployment_id)
            self.assertEqual(expected_count, len(executions))
        self.do_assertions(assertion)

    def wait_for_invocations(self, expected_count):
        def assertion():
            invocations = send_task(testmock_get_invocations).get(timeout=10)
            self.assertEqual(expected_count, len(invocations))
        self.do_assertions(assertion)
        return send_task(testmock_get_invocations).get(timeout=10)

    def wait_for_node_instance(self):
        def assertion():
            instances = self.client.node_instances.list(self.deployment_id)
            self.assertEqual(1, len(instances))
        self.do_assertions(assertion)
        return self.client.node_instances.list(self.deployment_id)[0]

    def publish(self, metric):
        self.publish_riemann_event(
            self.deployment_id,
            node_name='node',
            node_id=self.instance_id,
            metric=metric,
            service='service')
