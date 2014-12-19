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


from collections import namedtuple

import time

from testenv import TestCase
from testenv import utils
from testenv.utils import get_resource as resource
from testenv.utils import deploy_application as deploy
from testenv.utils import undeploy_application as undeploy
from riemann_controller.config_constants import Constants


class PoliciesTestsBase(TestCase):
    NUM_OF_INITIAL_WORKFLOWS = 2

    def launch_deployment(self, yaml_file, expected_num_of_node_instances=1):
        deployment, _ = deploy(resource(yaml_file))
        self.deployment = deployment
        self.node_instances = self.client.node_instances.list(deployment.id)
        self.assertEqual(
            expected_num_of_node_instances,
            len(self.node_instances)
        )
        self.wait_for_executions(self.NUM_OF_INITIAL_WORKFLOWS)

    def get_node_instance_by_name(self, name):
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
        utils.do_retries(assertion)
        invocations = self.get_plugin_data(
            plugin_name='testmockoperations',
            deployment_id=deployment_id
        )['mock_operation_invocation']
        return invocations

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


class TestPolicies(PoliciesTestsBase):
    def test_policies_flow(self):
        self.launch_deployment('dsl/with_policies1.yaml')

        metric_value = 123

        self.publish(metric=metric_value)

        self.wait_for_executions(self.NUM_OF_INITIAL_WORKFLOWS + 1)
        invocations = self.wait_for_invocations(self.deployment.id, 2)
        self.assertEqual(
            self.get_node_instance_by_name('node').id,
            invocations[0]['node_id']
        )
        self.assertEqual(metric_value, invocations[1]['metric'])

    def test_policies_flow_with_diamond(self):
        try:
            self.launch_deployment('dsl/with_policies_and_diamond.yaml')
            expected_metric_value = 42
            self.wait_for_executions(self.NUM_OF_INITIAL_WORKFLOWS + 1)
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
    EVENTS_TTL = 4  # in seconds
    # in seconds, a kind of time buffer for messages to get delivered for sure
    OPERATIONAL_TIME_BUFFER = 1
    SIMPLE_AUTOHEAL_POLICY_YAML = 'dsl/simple_auto_heal_policy.yaml'

    operation = namedtuple('Operation', ['nodes', 'name', 'positions'])

    DB_HOST = 'db_host'
    DB = 'db'
    DB_STATISTICS = 'db_statistics'
    WEBSERVER = 'webserver'
    WEBSERVER_CONSOLE = 'webserver_console'

    # create, configure, start
    NUM_OF_INITIAL_LIFECYCLE_OP = 3
    # also stop and delete
    NUM_OF_LIFECYCLE_OP = 5
    # preconfigure, postconfigure, establish
    NUM_OF_INITIAL_RELATIONSHIP_OP = 3
    # also unlink
    NUM_OF_RELATIONSHIP_OP = 4
    # only unlink and establish
    NUM_OF_RESTART_RELATIONSHIP_OP = 2

    class Threshold(object):
        VALID_METRIC = 10
        RISKY_METRIC = 100
        LONG_TIME = 3
        MAIN_NODE = 'node'
        SECOND_NODE = 'node2'
        THRESHOLD_YAML = 'dsl/stabilized_monitoring.yaml'

        def __init__(self, test_case, yaml=THRESHOLD_YAML):
            self.test_case = test_case
            self.yaml = yaml

        def _publish_and_wait(self, metric, node=MAIN_NODE, t=1):
            self.test_case.publish(metric=metric, node_name=node)
            time.sleep(t)

        def significantly_breach_threshold(self):
            self.test_case.launch_deployment(self.yaml)
            for _ in range(self.LONG_TIME):
                self._publish_and_wait(self.VALID_METRIC)
            for _ in range(self.LONG_TIME):
                self._publish_and_wait(self.RISKY_METRIC)

        def breach_threshold_once(self):
            self.test_case.launch_deployment(self.yaml)
            for _ in range(self.LONG_TIME):
                self._publish_and_wait(self.VALID_METRIC)
            self._publish_and_wait(self.RISKY_METRIC)
            for _ in range(self.LONG_TIME):
                self._publish_and_wait(self.VALID_METRIC)

        def breach_threshold_on_one_node_from_two(self):
            self.test_case.launch_deployment(self.yaml, 2)
            for _ in range(self.LONG_TIME):
                self._publish_and_wait(self.VALID_METRIC, t=0)
                self._publish_and_wait(self.VALID_METRIC, self.SECOND_NODE)
            for _ in range(self.LONG_TIME):
                self._publish_and_wait(metric=self.RISKY_METRIC, node=self.SECOND_NODE, t=0)
                self._publish_and_wait(metric=self.VALID_METRIC)
            self._publish_and_wait(self.VALID_METRIC, self.SECOND_NODE)

    class EwmaTimeless(object):
        VALID_METRIC = 50
        RISKY_METRIC = 150
        LONG_TIME = 4
        EWMA_YAML = 'dsl/ewma_stabilized.yaml'

        def __init__(self, test_case):
            self.test_case = test_case

        def swinging_threshold_breach(self):
            self.test_case.launch_deployment(self.EWMA_YAML)
            for _ in range(self.LONG_TIME):
                self.test_case.publish(self.VALID_METRIC)
                self.test_case.publish(self.RISKY_METRIC)

        def breach_threshold_once(self):
            self.test_case.launch_deployment(self.EWMA_YAML)
            for _ in range(self.LONG_TIME):
                self.test_case.publish(self.VALID_METRIC)
            self.test_case.publish(self.RISKY_METRIC)
            for _ in range(self.LONG_TIME):
                self.test_case.publish(self.VALID_METRIC)

        def slowly_rise_metric(self):
            self.test_case.launch_deployment(self.EWMA_YAML)
            metric = self.VALID_METRIC
            while metric < self.RISKY_METRIC:
                self.test_case.publish(metric)
                metric += 10

    def _get_non_rel_operation_num(self, node, op):
        op_nums = []
        for invocation in self.invocations:
            if (node == invocation.get('node') and
                    op == invocation['operation']):
                op_nums.append(invocation['num'])
        return op_nums

    def _get_rel_operation_num(self, source, target, op):
        op_nums = []
        for invocation in self.invocations:
            if (source == invocation.get('source') and
                    target == invocation.get('target') and
                    op == invocation['operation']):
                op_nums.append(invocation['num'])
        return op_nums

    def _get_operation_num(self, op):
        if len(op.nodes) == 2:
            return self._get_rel_operation_num(*op.nodes, op=op.name)
        elif len(op.nodes) == 1:
            return self._get_non_rel_operation_num(op.nodes[0], op.name)

    def _assert_op_order(self, op1, op2):
        for pos1 in op1.positions:
            for pos2 in op2.positions:
                self.assertLess(
                    self._get_operation_num(op1)[pos1],
                    self._get_operation_num(op2)[pos2]
                )

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

    def test_autoheal_policy_triggering(self):
        self.launch_deployment(self.SIMPLE_AUTOHEAL_POLICY_YAML)
        self._publish_heart_beat_event()
        self.wait_for_executions(self.NUM_OF_INITIAL_WORKFLOWS)
        self._wait_for_event_expiration()
        self.wait_for_executions(self.NUM_OF_INITIAL_WORKFLOWS + 1)

        invocation = self.wait_for_invocations(self.deployment.id, 1)[0]

        self.assertEqual(Constants.HEART_BEAT_FAILURE, invocation['diagnose'])
        self.assertEqual(
            self.get_node_instance_by_name('node').id,
            invocation['failing_node']
        )

    def test_autoheal_policy_triggering_two_instances(self):
        self.launch_deployment('dsl/two_instances_auto_heal.yaml', 2)
        node_a = self.node_instances[0]
        node_b = self.node_instances[1]
        self.publish(
            Constants.HEART_BEAT_FAILURE,
            ttl=self.EVENTS_TTL,
            node_id=node_a.id
        )
        for _ in range(7):
            self.publish(Constants.HEART_BEAT_FAILURE, node_id=node_b.id)
            time.sleep(1)

        self.wait_for_executions(self.NUM_OF_INITIAL_WORKFLOWS+1)
        invocation = self.wait_for_invocations(self.deployment.id, 1)[0]
        self.assertEqual(
            node_a.id,
            invocation['failing_node']
        )

    def test_autoheal_ignoring_unwatched_services(self):
        self.launch_deployment(self.SIMPLE_AUTOHEAL_POLICY_YAML)
        self._publish_heart_beat_event()
        for _ in range(5):
            self._publish_heart_beat_event(service='unwatched_service')
            time.sleep(1)

        self.wait_for_executions(self.NUM_OF_INITIAL_WORKFLOWS+1)

    def test_autoheal_ignoring_unwatched_services_expiration(self):
        self.launch_deployment(self.SIMPLE_AUTOHEAL_POLICY_YAML)
        self._publish_heart_beat_event(service='unwatched_service')
        time.sleep(1)
        for _ in range(5):
            self._publish_heart_beat_event()
            time.sleep(1)

        self.wait_for_executions(self.NUM_OF_INITIAL_WORKFLOWS)

    def test_threshold_stabilized(self):
        test = TestAutohealPolicies.Threshold(self)
        test.significantly_breach_threshold()
        self.wait_for_executions(self.NUM_OF_INITIAL_WORKFLOWS+1)
        self.wait_for_invocations(self.deployment.id, 1)

    def test_threshold_stabilized_doesnt_get_triggered_unnecessarily(self):
        test = TestAutohealPolicies.Threshold(self)
        test.breach_threshold_once()
        self.wait_for_executions(self.NUM_OF_INITIAL_WORKFLOWS)

    def test_threshold_stabilized_two_nodes(self):
        test = TestAutohealPolicies.Threshold(
            self,
            'dsl/threshold_stabilized_two_nodes.yaml'
        )
        test.breach_threshold_on_one_node_from_two()
        self.wait_for_executions(self.NUM_OF_INITIAL_WORKFLOWS+1)

    def test_ewma_timeless(self):
        test = TestAutohealPolicies.EwmaTimeless(self)
        test.swinging_threshold_breach()
        self.wait_for_executions(self.NUM_OF_INITIAL_WORKFLOWS+1)
        self.wait_for_invocations(self.deployment.id, 1)

    def test_ewma_timeless_doesnt_get_triggered_unnecessarily(self):
        test = TestAutohealPolicies.EwmaTimeless(self)
        test.breach_threshold_once()
        self.wait_for_executions(self.NUM_OF_INITIAL_WORKFLOWS)

    def test_ewma_stable_rise(self):
        test = TestAutohealPolicies.EwmaTimeless(self)
        test.slowly_rise_metric()
        self.wait_for_executions(self.NUM_OF_INITIAL_WORKFLOWS+1)
        self.wait_for_invocations(self.deployment.id, 1)

    def test_autoheal_policy_doesnt_get_triggered_unnecessarily(self):
        self.launch_deployment(self.SIMPLE_AUTOHEAL_POLICY_YAML)

        for _ in range(5):
            self._publish_heart_beat_event()
            time.sleep(self.EVENTS_TTL - self.OPERATIONAL_TIME_BUFFER)

        self.wait_for_executions(self.NUM_OF_INITIAL_WORKFLOWS)

    def test_autoheal_policy_triggering_for_two_nodes(self):
        self.launch_deployment('dsl/simple_auto_heal_policy_two_nodes.yaml', 2)

        self._publish_heart_beat_event(
            'node_about_to_fail',
            'service_on_failing_node'
        )
        for _ in range(5):
            time.sleep(self.EVENTS_TTL - self.OPERATIONAL_TIME_BUFFER)
            self._publish_heart_beat_event('ok_node')

        self.wait_for_executions(self.NUM_OF_INITIAL_WORKFLOWS + 1)
        invocation = self.wait_for_invocations(self.deployment.id, 1)[0]

        self.assertEqual(Constants.HEART_BEAT_FAILURE, invocation['diagnose'])
        self.assertEqual(
            self.get_node_instance_by_name('node_about_to_fail').id,
            invocation['failing_node']
        )

    def test_multiple_autoheal_policies(self):
        self.launch_deployment('dsl/auto_heal_multiple_policies.yaml')
        self._publish_heart_beat_event()
        self._wait_for_event_expiration()
        self.wait_for_executions(self.NUM_OF_INITIAL_WORKFLOWS + 1)
        self.wait_for_invocations(self.deployment.id, 1)

    def test_autoheal_policy_nested_nodes(self):
        NODES_WITH_LIFECYCLE_OP = 3
        NODES_WITH_RELATIONSHIP_OP = 3
        NODES_FROM_FAILING_SUBGRAPH_WITH_RELATIONSHIP_OP = 2
        # For every node with relationship there are two lifecycles
        # one for target and one for source
        NUM_OF_RELATIONSHIP_LIFECYCLES = 2 * NODES_WITH_LIFECYCLE_OP
        NUM_OF_RELATIONSHIP_LIFECYCLES_IN_FAILING_SUBGRAPH = (
            2 *
            NODES_FROM_FAILING_SUBGRAPH_WITH_RELATIONSHIP_OP
        )

        self.launch_deployment('dsl/auto_heal_nested_nodes.yaml', 5)
        self._publish_heart_beat_event(self.DB)
        self._wait_for_event_expiration()
        self.wait_for_executions(self.NUM_OF_INITIAL_WORKFLOWS + 1)

        self.invocations = self.wait_for_invocations(
            self.deployment.id,
            (
                NODES_WITH_LIFECYCLE_OP * self.NUM_OF_INITIAL_LIFECYCLE_OP +
                NODES_WITH_RELATIONSHIP_OP * self.NUM_OF_LIFECYCLE_OP +
                NUM_OF_RELATIONSHIP_LIFECYCLES *
                self.NUM_OF_INITIAL_RELATIONSHIP_OP +
                NUM_OF_RELATIONSHIP_LIFECYCLES_IN_FAILING_SUBGRAPH *
                self.NUM_OF_RELATIONSHIP_OP +
                2 * self.NUM_OF_RESTART_RELATIONSHIP_OP
            )
        )

        # unlink operation is executed before the source is deleted
        self._assert_op_order(
            self.operation(
                (self.DB_STATISTICS, self.WEBSERVER),
                'unlink',
                [0, 1]
            ),
            self.operation((self.DB_STATISTICS, ), 'delete', [0])
        )

        # DB and DB_STATISTICS is contained in DB_HOST
        # so they have to be deleted before
        self._assert_op_order(
            self.operation((self.DB, ), 'delete', [0]),
            self.operation((self.DB_HOST, ), 'delete', [0])
        )
        self._assert_op_order(
            self.operation((self.DB_STATISTICS, ), 'delete', [0]),
            self.operation((self.DB_HOST, ), 'delete', [0])
        )

        # DB has two unlinks - one for db_host and one from webserver
        # Webserver unlinks from db after it is stopped
        self._assert_op_order(
            self.operation((self.DB, self.DB_HOST), 'unlink', [0, 1]),
            self.operation((self.DB, ), 'delete', [0])
        )
        self._assert_op_order(
            self.operation((self.WEBSERVER, self.DB), 'unlink', [0, 1]),
            self.operation((self.DB, ), 'delete', [0])
        )

        # DB_HOST has to be started before the nodes that are contained
        # in it are created
        self._assert_op_order(
            self.operation((self.DB_HOST, ), 'start', [1]),
            self.operation((self.DB, ), 'create', [1])
        )
        self._assert_op_order(
            self.operation((self.DB_HOST, ), 'start', [1]),
            self.operation((self.DB_STATISTICS, ), 'create', [1])
        )

        # configure operation is between preconfigure and postconfigure
        self._assert_op_order(
            self.operation((self.DB, self.DB_HOST), 'preconfigure', [2, 3]),
            self.operation((self.DB, ), 'configure', [1])
        )
        self._assert_op_order(
            self.operation((self.DB, ), 'configure', [1]),
            self.operation((self.DB, self.DB_HOST), 'postconfigure', [2, 3])
        )

        # preconfigure self.operations of both the source (DB_STATISTICS) and
        # the target (WEBSERVER) are executed before the configure
        # self.operation of the host
        self._assert_op_order(
            self.operation(
                (self.DB_STATISTICS, self.WEBSERVER),
                'preconfigure',
                [2, 3]
            ),
            self.operation((self.DB_STATISTICS, ), 'configure', [1])
        )
        # It is the same for configure and postconfigure
        self._assert_op_order(
            self.operation((self.DB_STATISTICS, ), 'configure', [1]),
            self.operation(
                (self.DB_STATISTICS, self.WEBSERVER),
                'postconfigure',
                [2, 3]
            )
        )

        self._assert_op_order(
            self.operation((self.DB, ), 'start', [1]),
            self.operation((self.DB, self.DB_HOST), 'establish', [2, 3])
        )

        # Establishing relationship is after start of the source
        self._assert_op_order(
            self.operation((self.DB_STATISTICS, ), 'start', [1]),
            self.operation(
                (self.DB_STATISTICS, self.WEBSERVER),
                'establish',
                [2, 3]
            )
        )

    def test_autoheal_policy_grandchild(self):
        NUM_OF_NODES_WITH_OP = 2

        self.launch_deployment('dsl/auto_heal_grandchild.yaml', 3)
        self._publish_heart_beat_event(self.WEBSERVER)
        self._wait_for_event_expiration()
        self.wait_for_executions(self.NUM_OF_INITIAL_WORKFLOWS + 1)

        self.invocations = self.wait_for_invocations(
            self.deployment.id,
            (
                NUM_OF_NODES_WITH_OP * self.NUM_OF_INITIAL_LIFECYCLE_OP +
                NUM_OF_NODES_WITH_OP * self.NUM_OF_INITIAL_RELATIONSHIP_OP +
                NUM_OF_NODES_WITH_OP * self.NUM_OF_LIFECYCLE_OP +
                NUM_OF_NODES_WITH_OP * self.NUM_OF_RELATIONSHIP_OP
            )
        )

        # WEBSERVER_CONSOLE is installed_on WEBSERVER
        # so WEBSERVER needs to start before WEBSERVER_CONSOLE before and
        # after failure
        self._assert_op_order(
            self.operation((self.WEBSERVER, ), 'start', [0]),
            self.operation((self.WEBSERVER_CONSOLE, ), 'start', [0])
        )
        self._assert_op_order(
            self.operation((self.WEBSERVER, ), 'start',  [1]),
            self.operation((self.WEBSERVER_CONSOLE, ), 'start', [1])
        )

        # WEBSERVER can't be stopped before WEBSERVER_CONSOLE is deleted
        self._assert_op_order(
            self.operation((self.WEBSERVER_CONSOLE, ), 'delete', [0]),
            self.operation((self.WEBSERVER, ), 'stop', [0])
        )

        # preconfigure and postconfigure are executed around configure of the
        # source node in relationship (WEBSERVER_CONSOLE)
        self._assert_op_order(
            self.operation(
                (self.WEBSERVER_CONSOLE, self.WEBSERVER),
                'preconfigure',
                [0, 1]
            ),
            self.operation((self.WEBSERVER_CONSOLE, ), 'configure', [0])
        )
        self._assert_op_order(
            self.operation((self.WEBSERVER_CONSOLE, ), 'configure', [0]),
            self.operation(
                (self.WEBSERVER_CONSOLE, self.WEBSERVER),
                'postconfigure',
                [0, 1]
            )
        )

        # After failure and restart of both nodes
        # the connection must be established
        self._assert_op_order(
            self.operation((self.WEBSERVER_CONSOLE, ), 'start',  [1]),
            self.operation(
                (self.WEBSERVER_CONSOLE, self.WEBSERVER),
                'establish',
                [2, 3]
            )
        )
