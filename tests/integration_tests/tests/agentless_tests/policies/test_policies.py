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

import time

from integration_tests import AgentlessTestCase

from . import PoliciesTestsBase


class TestPolicies(AgentlessTestCase, PoliciesTestsBase):

    def test_policies_flow(self):
        self._test_policies_flow('dsl/with_policies1.yaml')

    def test_group_with_no_policies(self):
        # this test is identical to the previous with the addition
        # of a groups with no policies defined on it.
        self._test_policies_flow('dsl/group_with_no_policies.yaml')

    def _test_policies_flow(self, blueprint_path):
        self.launch_deployment(blueprint_path)

        metric_value = 123

        self.publish(metric=metric_value)

        self.wait_for_executions(self.NUM_OF_INITIAL_WORKFLOWS + 1)
        invocations = self.wait_for_invocations(self.deployment.id, 2)

        def value(key):
            return [i for i in invocations if key in i][0][key]
        self.assertEqual(self.get_node_instance_by_name('node').id,
                         value('node_id'))
        self.assertEqual(metric_value, value('metric'))

    def test_threshold_policy(self):
        self.launch_deployment('dsl/with_policies2.yaml')

        class Tester(object):

            def __init__(self, test_case, threshold, current_executions,
                         current_invocations):
                self.test_case = test_case
                self.current_invocations = current_invocations
                self.current_executions = current_executions
                self.threshold = threshold

            def publish_above_threshold(self, deployment_id, do_assert):
                self.test_case.logger.info('Publish above threshold')
                self.test_case.publish(self.threshold + 1)
                if do_assert:
                    self.inc()
                    self.assertion(deployment_id, upper=True)

            def publish_below_threshold(self, deployment_id, do_assert):
                self.test_case.logger.info('Publish below threshold')
                self.test_case.publish(self.threshold - 1)
                if do_assert:
                    self.inc()
                    self.assertion(deployment_id, upper=False)

            def inc(self):
                self.current_executions += 1
                self.current_invocations += 1

            def assertion(self, deployment_id, upper):
                self.test_case.logger.info('waiting for {} executions'
                                           .format(self.current_executions))
                self.test_case.wait_for_executions(self.current_executions)
                self.test_case.logger.info('waiting for {} invocations'
                                           .format(self.current_invocations))
                invocations = self.test_case.wait_for_invocations(
                    deployment_id,
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

        # In test's blueprint set this value decreased by 1
        # (1s safety time buffer)
        min_interval_between_workflows = 4

        for _ in range(2):
            tester.publish_above_threshold(self.deployment.id, do_assert=True)
            tester.publish_above_threshold(self.deployment.id, do_assert=False)
            time.sleep(min_interval_between_workflows)
            tester.publish_below_threshold(self.deployment.id, do_assert=True)
            tester.publish_below_threshold(self.deployment.id, do_assert=False)
            time.sleep(min_interval_between_workflows)
