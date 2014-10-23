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
SAFETY_MARGIN = 2

# Autoheal constant
AUTOHEAL_EVENTS_MSG = "heart-beat"


class TestPolicies(TestCase):

    def test_policies_flow(self):
        dsl_path = resource('dsl/with_policies1.yaml')
        deployment, _ = deploy(dsl_path)
        self.deployment_id = deployment.id
        self.instance_id = self.wait_for_node_instance().id

        metric_value = 123

        self.publish(metric=metric_value)

        self.wait_for_executions(NUM_OF_INITIAL_WORKFLOWS + 1)
        invocations = self.wait_for_invocations(deployment.id, 2)
        self.assertEqual(self.instance_id, invocations[0]['node_id'])
        self.assertEqual(123, invocations[1]['metric'])

    def test_policies_flow_with_diamond(self):
        deployment = None
        try:
            dsl_path = resource("dsl/with_policies_and_diamond.yaml")
            deployment, _ = deploy(dsl_path)
            self.deployment_id = deployment.id
            self.instance_id = self.wait_for_node_instance().id
            expected_metric_value = 42
            self.wait_for_executions(NUM_OF_INITIAL_WORKFLOWS + 1)
            invocations = self.wait_for_invocations(deployment.id, 1)
            self.assertEqual(expected_metric_value, invocations[0]['metric'])
        finally:
            try:
                if deployment:
                    undeploy(deployment.id)
            except BaseException as e:
                if e.message:
                    self.logger.warning(e.message)

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
            tester.publish_above_threshold(deployment.id, do_assert=True)
            tester.publish_above_threshold(deployment.id, do_assert=False)
            tester.publish_below_threshold(deployment.id, do_assert=True)
            tester.publish_below_threshold(deployment.id, do_assert=False)

    def test_autoheal_policy_triggering(self):
        EVENTS_TTL = 3
        AUTOHEAL_YAML = 'dsl/simple_auto_heal_policy.yaml'

        dsl_path = resource(AUTOHEAL_YAML)
        deployment, _ = deploy(dsl_path)
        self.deployment_id = deployment.id
        self.instance_id = self.wait_for_node_instance().id

        self.wait_for_executions(NUM_OF_INITIAL_WORKFLOWS)

        self.publish(AUTOHEAL_EVENTS_MSG, EVENTS_TTL)
        time.sleep(
            EVENTS_TTL +
            Constants.PERIODICAL_EXPIRATION_INTERVAL +
            SAFETY_MARGIN
        )

        self.wait_for_executions(NUM_OF_INITIAL_WORKFLOWS + 1)
        invocation = self.wait_for_invocations(deployment.id, 1)[0]

        self.assertEqual("heart-beat-failure", invocation['diagnose'])
        self.assertEqual(self.instance_id, invocation['failing_node'])

    def test_autoheal_policy_stability(self):
        EVENTS_TTL = 3
        EVENTS_NO = 10
        AUTOHEAL_YAML = 'dsl/simple_auto_heal_policy.yaml'

        dsl_path = resource(AUTOHEAL_YAML)
        deployment, _ = deploy(dsl_path)
        self.deployment_id = deployment.id
        self.instance_id = self.wait_for_node_instance().id

        self.wait_for_executions(NUM_OF_INITIAL_WORKFLOWS)

        for _ in range(EVENTS_NO):
            self.publish(AUTOHEAL_EVENTS_MSG, EVENTS_TTL)
            time.sleep(EVENTS_TTL - SAFETY_MARGIN)

        self.wait_for_executions(NUM_OF_INITIAL_WORKFLOWS)

    def wait_for_executions(self, expected_count):
        def assertion():
            executions = self.client.executions.list(
                deployment_id=self.deployment_id)
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

    def wait_for_node_instance(self):
        def assertion():
            instances = self.client.node_instances.list(self.deployment_id)
            self.assertEqual(1, len(instances))
        self.do_assertions(assertion)
        return self.client.node_instances.list(self.deployment_id)[0]

    def publish(self, metric, ttl=60):
        self.publish_riemann_event(
            self.deployment_id,
            node_name='node',
            node_id=self.instance_id,
            metric=metric,
            service='service',
            ttl=ttl
        )
