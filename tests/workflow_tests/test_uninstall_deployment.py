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

__author__ = 'eitany'

from testenv import TestCase
from testenv import get_resource as resource
from testenv import deploy_application as deploy
from testenv import undeploy_application as undeploy
from testenv import get_node_instance
from plugins.cloudmock import tasks as cloudmock
import time


class TestUninstallDeployment(TestCase):

    def test_uninstall_application_single_node_no_host(self):
        from testenv import logger
        dsl_path = resource("dsl/single_node_no_host.yaml")
        logger.info('starting deploy process')
        deployment, _ = deploy(dsl_path)
        deployment_id = deployment.id
        logger.info('deploy completed')
        logger.info('starting undeploy process')
        time.sleep(5)  # give elasticsearch time to update execution status..
        undeploy(deployment_id)
        logger.info('undeploy completed')

        from plugins.testmockoperations.tasks import get_state as \
            testmock_get_state
        from plugins.testmockoperations.tasks import is_unreachable_called
        states = self.send_task(testmock_get_state).get(timeout=10)
        node_id = states[0]['id']

        result = self.send_task(is_unreachable_called, [node_id])
        self.assertTrue(result.get(timeout=10))

        node_instance = get_node_instance(node_id)
        self.assertEqual('deleted', node_instance['state'])

    def test_uninstall_application_single_host_node(self):
        dsl_path = resource("dsl/basic.yaml")

        self.logger.info('starting deploy process')
        deployment, _ = deploy(dsl_path)
        deployment_id = deployment.id
        self.logger.info('deploy completed')

        self.logger.info('starting undeploy process')
        time.sleep(5)  # give elasticsearch time to update execution status..
        undeploy(deployment_id)
        self.logger.info('undeploy completed')

        from plugins.cloudmock.tasks import get_machines
        result = self.send_task(get_machines)
        machines = result.get(timeout=10)

        self.assertEquals(0, len(machines))

    def test_uninstall_with_dependency_order(self):
        dsl_path = resource(
            "dsl/uninstall_dependencies-order-with-three-nodes.yaml")
        print('starting deploy process')
        deployment, _ = deploy(dsl_path)
        deployment_id = deployment.id
        print('deploy completed')
        print('starting undeploy process')
        time.sleep(5)  # give elasticsearch time to update execution status..
        undeploy(deployment_id)
        print('undeploy completed')
        # Checking that uninstall wasn't called on the contained node
        from plugins.testmockoperations.tasks import \
            get_unreachable_call_order \
            as testmock_get_unreachable_call_order
        from plugins.testmockoperations.tasks import get_state \
            as testmock_get_state
        states = self.send_task(testmock_get_state).get(timeout=10)
        node1_id = states[0]['id']
        node2_id = states[1]['id']
        node3_id = states[2]['id']

        unreachable_call_order = self\
            .send_task(testmock_get_unreachable_call_order)\
            .get(timeout=10)
        self.assertEquals(3, len(unreachable_call_order))
        self.assertEquals(node3_id, unreachable_call_order[0]['id'])
        self.assertEquals(node2_id, unreachable_call_order[1]['id'])
        self.assertEquals(node1_id, unreachable_call_order[2]['id'])

        from plugins.connection_configurer_mock.tasks import get_state \
            as config_get_state
        configurer_state = self.send_task(config_get_state).get(timeout=10)
        self.assertEquals(2, len(configurer_state))
        self.assertTrue(
            configurer_state[0]['id'].startswith('contained_in_node2'))
        self.assertTrue(
            configurer_state[0]['related_id'].startswith('contained_in_node1'))
        self.assertTrue(
            configurer_state[1]['id'].startswith('containing_node'))
        self.assertTrue(
            configurer_state[1]['related_id'].startswith('contained_in_node1'))

    def test_stop_monitor_node_operation(self):
        dsl_path = resource(
            "dsl/hardcoded-operation-properties.yaml")
        print('starting deploy process')
        deployment, _ = deploy(dsl_path)
        deployment_id = deployment.id
        print('deploy completed')
        print('starting undeploy process')
        time.sleep(5)  # give elasticsearch time to update execution status..
        undeploy(deployment_id)
        print('undeploy completed')
        # test stop monitor invocations
        from plugins.testmockoperations.tasks import \
            get_monitoring_operations_invocation
        invocations = self.send_task(get_monitoring_operations_invocation) \
            .get(timeout=10)
        self.assertEqual(2, len(invocations))
        self.assertTrue('single_node' in invocations[0]['id'])
        self.assertEquals('start_monitor', invocations[0]['operation'])
        self.assertTrue('single_node' in invocations[1]['id'])
        self.assertEquals('stop_monitor', invocations[1]['operation'])

    def test_failed_uninstall_task(self):
        dsl_path = resource("dsl/basic.yaml")
        self.logger.info('** install **')
        deployment, _ = deploy(dsl_path)
        deployment_id = deployment.id

        self.send_task(cloudmock.set_raise_exception_on_stop).get(timeout=10)

        self.logger.info('** uninstall **')
        time.sleep(5)  # give elasticsearch time to update execution status..
        undeploy(deployment_id)

        from plugins.cloudmock.tasks import get_machines
        result = self.send_task(get_machines)
        machines = result.get(timeout=10)

        self.assertEquals(0, len(machines))
