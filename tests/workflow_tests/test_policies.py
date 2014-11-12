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
from testenv import utils
from testenv.utils import get_resource as resource
from testenv.utils import deploy_application as deploy
from testenv.utils import undeploy_application as undeploy
from riemann_controller.config_constants import Constants

import time
from nose.tools import nottest


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
        utils.do_retries(assertion)
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

    #TODO:Needs fixing due to the source/target distinction by relationship ops
    @nottest
    def test_autoheal_policy_nested_nodes(self):

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

        DB_HOST = 'db_host'
        DB = 'db'
        DB_STATISTICS = 'db_statistics'
        WEBSERVER = 'webserver'

        self.launch_deployment('dsl/auto_heal_nested_nodes.yaml', 5)
        self._publish_heart_beat_event(DB)
        self._wait_for_event_expiration()
        self.wait_for_executions(NUM_OF_INITIAL_WORKFLOWS + 1)

        invocations = self.wait_for_invocations(
            self.deployment.id,
            (
                NODES_WITH_LIFECYCLE_OP * NUM_OF_INITIAL_LIFECYCLE_OP +
                NODES_WITH_RELATIONSHIP_OP * NUM_OF_LIFECYCLE_OP +
                NUM_OF_RELATIONSHIP_LIFECYCLES *
                NUM_OF_INITIAL_RELATIONSHIP_OP +
                NUM_OF_RELATIONSHIP_LIFECYCLES_IN_FAILING_SUBGRAPH *
                NUM_OF_RELATIONSHIP_OP +
                2 * NUM_OF_RESTART_RELATIONSHIP_OP
            )
        )

        # unlink operation is executed before the source is deleted
        self.assertLess(
            self._get_operation_num(DB_STATISTICS, 'unlink', invocations)[0],
            self._get_operation_num(DB_STATISTICS, 'delete', invocations)[0]
        )
        self.assertLess(
            self._get_operation_num(WEBSERVER, 'unlink', invocations)[0],
            self._get_operation_num(DB_STATISTICS, 'delete', invocations)[0]
        )

        # DB and DB_STATISTICS is contained in DB_HOST
        # so they have to be deleted before
        self.assertLess(
            self._get_operation_num(DB, 'delete', invocations)[0],
            self._get_operation_num(DB_HOST, 'delete', invocations)[0]
        )
        self.assertLess(
            self._get_operation_num(DB_STATISTICS, 'delete', invocations)[0],
            self._get_operation_num(DB_HOST, 'delete', invocations)[0]
        )

        # DB has two unlinks - one for db_host and one from webserver
        # Webserver unlinks from db after it is stopped
        self.assertLess(
            self._get_operation_num(DB, 'unlink', invocations)[0],
            self._get_operation_num(DB, 'delete', invocations)[0]
        )
        self.assertLess(
            self._get_operation_num(DB, 'unlink', invocations)[1],
            self._get_operation_num(DB, 'delete', invocations)[0]
        )
        self.assertLess(
            self._get_operation_num(WEBSERVER, 'unlink', invocations)[0],
            self._get_operation_num(DB, 'delete', invocations)[0]
        )

        # DB_HOST has to be started before the nodes that are contained
        # in it are created
        self.assertLess(
            self._get_operation_num(DB_HOST, 'start', invocations)[1],
            self._get_operation_num(DB, 'create', invocations)[1]
        )
        self.assertLess(
            self._get_operation_num(DB_HOST, 'start', invocations)[1],
            self._get_operation_num(DB_STATISTICS, 'create', invocations)[1]
        )

        # configure operation is between preconfigure and postconfigure
        self.assertLess(
            self._get_operation_num(DB, 'preconfigure', invocations)[2],
            self._get_operation_num(DB, 'configure', invocations)[1]
        )
        self.assertLess(
            self._get_operation_num(DB, 'configure', invocations)[1],
            self._get_operation_num(DB, 'postconfigure', invocations)[2]
        )

        # preconfigure operations of both the source (DB_STATISTICS) and
        # the target (WEBSERVER) are executed before the configure
        # operation of the host
        self.assertLess(
            self._get_operation_num(
                DB_STATISTICS,
                'preconfigure',
                invocations
            )[1],
            self._get_operation_num(DB_STATISTICS, 'configure', invocations)[1]
        )
        self.assertLess(
            self._get_operation_num(WEBSERVER, 'preconfigure', invocations)[2],
            self._get_operation_num(DB_STATISTICS, 'configure', invocations)[1]
        )
        # It is the same for configure and postconfigure
        self.assertLess(
            self._get_operation_num(
                DB_STATISTICS,
                'configure',
                invocations
            )[1],
            self._get_operation_num(
                DB_STATISTICS,
                'postconfigure',
                invocations
            )[1]
        )
        self.assertLess(
            self._get_operation_num(
                DB_STATISTICS,
                'configure',
                invocations
            )[1],
            self._get_operation_num(
                WEBSERVER,
                'postconfigure',
                invocations
            )[2]
        )

        self.assertLess(
            self._get_operation_num(DB, 'start', invocations)[1],
            self._get_operation_num(DB, 'establish', invocations)[2]
        )

        # Establishing relationship is after start of the source
        self.assertLess(
            self._get_operation_num(DB_STATISTICS, 'start', invocations)[1],
            self._get_operation_num(
                DB_STATISTICS,
                'establish',
                invocations
            )[1]
        )
        self.assertLess(
            self._get_operation_num(DB_STATISTICS, 'start', invocations)[1],
            self._get_operation_num(WEBSERVER, 'establish', invocations)[3]
        )

    def test_autoheal_policy_doesnt_get_triggered_unnecessarily(self):
        self.launch_deployment(self.SIMPLE_AUTOHEAL_POLICY_YAML)

        for _ in range(5):
            self._publish_heart_beat_event()
            time.sleep(self.EVENTS_TTL - self.OPERATIONAL_TIME_BUFFER)

        self.wait_for_executions(NUM_OF_INITIAL_WORKFLOWS)

    #TODO: fix blueprint to conform to version 3.1
    @nottest
    def test_autoheal_policy_grandchild(self):
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

        NUM_OF_NODES_WITH_OP = 2

        self.launch_deployment('dsl/auto_heal_grandchild.yaml', 3)
        self._publish_heart_beat_event(WEBSERVER)
        self._wait_for_event_expiration()
        self.wait_for_executions(NUM_OF_INITIAL_WORKFLOWS + 1)

        invocations = self.wait_for_invocations(
            self.deployment.id,
            (
                NUM_OF_NODES_WITH_OP * NUM_OF_INITIAL_LIFECYCLE_OP +
                NUM_OF_NODES_WITH_OP * NUM_OF_INITIAL_RELATIONSHIP_OP +
                NUM_OF_NODES_WITH_OP * NUM_OF_LIFECYCLE_OP +
                NUM_OF_NODES_WITH_OP * NUM_OF_RELATIONSHIP_OP
            )
        )

        # WEBSERVER_CONSOLE is installed_on WEBSERVER
        # so WEBSERVER needs to start before WEBSERVER_CONSOLE before and
        # after failure
        self.assertLess(
            self._get_operation_num(WEBSERVER, 'start', invocations)[0],
            self._get_operation_num(
                WEBSERVER_CONSOLE,
                'start',
                invocations
            )[0]
        )
        self.assertLess(
            self._get_operation_num(WEBSERVER, 'start', invocations)[1],
            self._get_operation_num(
                WEBSERVER_CONSOLE,
                'start',
                invocations
            )[1]
        )

        # WEBSERVER can't be stopped before WEBSERVER_CONSOLE is deleted
        self.assertLess(
            self._get_operation_num(
                WEBSERVER_CONSOLE,
                'delete',
                invocations
            )[0],
            self._get_operation_num(WEBSERVER, 'stop', invocations)[0]
        )

        # preconfigure and postconfigure are executed around configure of the
        # source node in relationship (WEBSERVER_CONSOLE)
        self.assertLess(
            self._get_operation_num(
                WEBSERVER,
                'preconfigure',
                invocations
            )[0],
            self._get_operation_num(
                WEBSERVER_CONSOLE,
                'configure',
                invocations
            )[0]
        )
        self.assertLess(
            self._get_operation_num(
                WEBSERVER_CONSOLE,
                'preconfigure',
                invocations
            )[0],
            self._get_operation_num(
                WEBSERVER_CONSOLE,
                'configure',
                invocations
            )[0]
        )
        self.assertLess(
            self._get_operation_num(
                WEBSERVER,
                'preconfigure',
                invocations
            )[1],
            self._get_operation_num(
                WEBSERVER_CONSOLE,
                'configure',
                invocations
            )[1]
        )
        self.assertLess(
            self._get_operation_num(
                WEBSERVER_CONSOLE,
                'preconfigure',
                invocations
            )[1],
            self._get_operation_num(
                WEBSERVER_CONSOLE,
                'configure',
                invocations
            )[1]
        )
        self.assertLess(
            self._get_operation_num(
                WEBSERVER_CONSOLE,
                'configure',
                invocations
            )[0],
            self._get_operation_num(
                WEBSERVER,
                'postconfigure',
                invocations
            )[0]
        )
        self.assertLess(
            self._get_operation_num(
                WEBSERVER_CONSOLE,
                'configure',
                invocations
            )[0],
            self._get_operation_num(
                WEBSERVER_CONSOLE,
                'postconfigure',
                invocations
            )[0]
        )
        self.assertLess(
            self._get_operation_num(
                WEBSERVER_CONSOLE,
                'configure',
                invocations
            )[1],
            self._get_operation_num(
                WEBSERVER,
                'postconfigure',
                invocations
            )[1]
        )
        self.assertLess(
            self._get_operation_num(
                WEBSERVER_CONSOLE,
                'configure',
                invocations
            )[1],
            self._get_operation_num(
                WEBSERVER_CONSOLE,
                'postconfigure',
                invocations
            )[1]
        )

        # After failure and restart of both nodes
        # the connection must be established
        self.assertLess(
            self._get_operation_num(
                WEBSERVER_CONSOLE,
                'start',
                invocations
            )[1],
            self._get_operation_num(
                WEBSERVER_CONSOLE,
                'establish',
                invocations
            )[1]
        )
        self.assertLess(
            self._get_operation_num(
                WEBSERVER_CONSOLE,
                'start',
                invocations
            )[1],
            self._get_operation_num(WEBSERVER, 'establish', invocations)[1]
        )

    #TODO: fix blueprint to conform to version 3.1
    @nottest
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

    #TODO: fix blueprint to conform to version 3.1
    @nottest
    def test_swap_policy(self):
        try:
            self.launch_deployment('dsl/swap_policy.yaml')
            self.wait_for_executions(NUM_OF_INITIAL_WORKFLOWS + 1)
            invocation = self.wait_for_invocations(self.deployment.id, 1)[0]
            self.assertEqual('restart', invocation['operation'])
        finally:
            try:
                undeploy(self.deployment.id)
            except BaseException as e:
                if e.message:
                    self.logger.warning(e.message)

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

    def _get_operation_num(self, node, operation, invocations):
            op_nums = []
            for invocation in invocations:
                if (
                    node == invocation['node'] and
                    operation == invocation['operation']
                ):
                    op_nums.append(invocation['num'])
            return op_nums
