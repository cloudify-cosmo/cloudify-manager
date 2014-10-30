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
from testenv.utils import get_resource as resource
from testenv.utils import deploy_application as deploy
from testenv.utils import undeploy_application as undeploy
from riemann_controller.config_constants import Constants

import time


NUM_OF_INITIAL_WORKFLOWS = 2


class PoliciesTestsBase(TestCase):
    def launch_deployment(self, yaml_file, expectedNumOfNodeInstances=1):
        deployment, _ = deploy(resource(yaml_file))
        self.deployment = deployment
        self.node_instances = self.client.node_instances.list(deployment.id)
        self.assertEqual(expectedNumOfNodeInstances, len(self.node_instances))
        self.wait_for_executions(NUM_OF_INITIAL_WORKFLOWS)

    def getNodeInstanceByName(self, name):
        for nodeInstance in self.node_instances:
            if nodeInstance.node_id == name:
                return nodeInstance

    def wait_for_executions(self, expected_count):
        def assertion():
            executions = self.client.executions.list(
                deployment_id=self.deployment.id)
            self.assertEqual(expected_count, len(executions))
        self.do_assertions(assertion)

    def wait_for_invocations(self, deployment_id, expected_count):
        def assertion():
            _invocations = self.get_plugin_data(
                plugin_name='testmockoperations',
                deployment_id=deployment_id
            )['mock_operation_invocation']
            self.assertEqual(expected_count, len(_invocations))
        self.do_assertions(assertion)
        invocations = self.get_plugin_data(
            plugin_name='testmockoperations',
            deployment_id=deployment_id
        )['mock_operation_invocation']
        return invocations

    def publish(self, metric, ttl=60, node_name='node', service='service'):
        self.publish_riemann_event(
            self.deployment.id,
            node_name=node_name,
            node_id=self.getNodeInstanceByName(node_name).id,
            metric=metric,
            service=service,
            ttl=ttl
        )


class TestPolicies(PoliciesTestsBase):

    def test_policies_flow(self):
        self.launch_deployment('dsl/with_policies1.yaml')

        metric_value = 123

        self.publish(metric=metric_value)

        self.wait_for_executions(NUM_OF_INITIAL_WORKFLOWS + 1)
        invocations = self.wait_for_invocations(self.deployment.id, 2)
        self.assertEqual(
            self.getNodeInstanceByName('node').id,
            invocations[0]['node_id']
        )
        self.assertEqual(123, invocations[1]['metric'])

    def test_policies_flow_with_diamond(self):
        try:
            self.launch_deployment('dsl/with_policies_and_diamond.yaml')
            expected_metric_value = 42
            self.wait_for_executions(NUM_OF_INITIAL_WORKFLOWS + 1)
            invocations = self.wait_for_invocations(self.deployment.id, 1)
            self.assertEqual(expected_metric_value, invocations[0]['metric'])
        finally:
            try:
                if self.deployment:
                    undeploy(self.deployment.id)
            except BaseException as e:
                if e.message:
                    self.logger.warning(e.message)

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

        for _ in range(2):
            tester.publish_above_threshold(self.deployment.id, do_assert=True)
            tester.publish_above_threshold(self.deployment.id, do_assert=False)
            tester.publish_below_threshold(self.deployment.id, do_assert=True)
            tester.publish_below_threshold(self.deployment.id, do_assert=False)


class TestAutohealPolicies(PoliciesTestsBase):
    HEART_BEAT_METRIC = 'heart-beat'
    EVENTS_TTL = 3  # in seconds
    # in seconds, a kind of time buffer for messages to get delivered for sure
    OPERATIONAL_TIME_BUFFER = 1
    SIMPLE_AUTOHEAL_POLICY_YAML = 'dsl/simple_auto_heal_policy.yaml'

    def test_autoheal_policy_triggering(self):
        self.launch_deployment(self.SIMPLE_AUTOHEAL_POLICY_YAML)
        self._publish_heart_beat_event()
        self.wait_for_executions(NUM_OF_INITIAL_WORKFLOWS)
        self._wait_for_event_expiration()
        self.wait_for_executions(NUM_OF_INITIAL_WORKFLOWS + 1)

        invocation = self.wait_for_invocations(self.deployment.id, 1)[0]

        self.assertEqual('heart-beat-failure', invocation['diagnose'])
        self.assertEqual(
            self.getNodeInstanceByName('node').id,
            invocation['failing_node']
        )

    def test_autoheal_policy_triggering_for_two_nodes(self):
        self.launch_deployment('dsl/simple_auto_heal_policy_two_nodes.yaml', 2)

        self._publish_heart_beat_event(
            'node_about_to_fail',
            'service_on_failing_node'
        )
        for _ in range(5):
            time.sleep(self.EVENTS_TTL - self.OPERATIONAL_TIME_BUFFER)
            self._publish_heart_beat_event('ok_node')

        self.wait_for_executions(NUM_OF_INITIAL_WORKFLOWS + 1)
        invocation = self.wait_for_invocations(self.deployment.id, 1)[0]

        self.assertEqual('heart-beat-failure', invocation['diagnose'])
        self.assertEqual(
            self.getNodeInstanceByName('node_about_to_fail').id,
            invocation['failing_node']
        )

    def test_autoheal_policy_doesnt_get_triggered_unnecessarily(self):
        self.launch_deployment(self.SIMPLE_AUTOHEAL_POLICY_YAML)

        for _ in range(5):
            self._publish_heart_beat_event()
            time.sleep(self.EVENTS_TTL - self.OPERATIONAL_TIME_BUFFER)

        self.wait_for_executions(NUM_OF_INITIAL_WORKFLOWS)

    def test_autoheal_workflow(self):
        self.launch_deployment('dsl/customized_auto_heal_policy.yaml')
        self._publish_event_and_wait_for_its_expiration()
        self.wait_for_executions(NUM_OF_INITIAL_WORKFLOWS + 1)

        # One start invocation occurs during the test env deployment creation
        invocations = self.wait_for_invocations(self.deployment.id, 3)
        invocation_stop = invocations[1]
        invocation_start = invocations[2]

        self.assertEqual('start', invocation_start['operation'])
        self.assertEqual('stop', invocation_stop['operation'])
        self.assertEqual(20, invocation_stop['const_arg_stop'])

    def _publish_heart_beat_event(self, node_name='node', service='service'):
        self.publish(
            self.HEART_BEAT_METRIC,
            self.EVENTS_TTL,
            node_name,
            service
        )

    def _wait_for_event_expiration(self):
        time.sleep(
            self.EVENTS_TTL +
            Constants.PERIODICAL_EXPIRATION_INTERVAL +
            self.OPERATIONAL_TIME_BUFFER
        )

    def _publish_event_and_wait_for_its_expiration(self, node_name='node'):
        self._publish_heart_beat_event(node_name)
        self._wait_for_event_expiration()
