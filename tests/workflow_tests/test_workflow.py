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

__author__ = 'idanmo'

import uuid
import time
from testenv import TestCase
from testenv import get_resource as resource
from testenv import deploy_application as deploy
from testenv import timeout
from testenv import send_task
from testenv import verify_workers_installation_complete
from testenv import do_retries
from testenv import wait_for_execution_to_end
from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify_rest_client.executions import Execution


class BasicWorkflowsTest(TestCase):

    def test_execute_operation(self):
        dsl_path = resource("dsl/basic.yaml")
        blueprint_id = self.id()
        deployment, _ = deploy(dsl_path, blueprint_id=blueprint_id)

        self.assertEqual(blueprint_id, deployment.blueprint_id)

        from plugins.cloudmock.tasks import get_machines
        result = send_task(get_machines)
        machines = result.get(timeout=10)

        self.assertEquals(1, len(machines))

    def test_dependencies_order_with_two_nodes(self):
        dsl_path = resource("dsl/dependencies-order-with-two-nodes.yaml")
        blueprint_id = self.id()
        deployment, _ = deploy(dsl_path, blueprint_id=blueprint_id)

        self.assertEquals(blueprint_id, deployment.blueprint_id)

        from plugins.testmockoperations.tasks import get_state as \
            testmock_get_state
        states = send_task(testmock_get_state) \
            .get(timeout=10)
        self.assertEquals(2, len(states))
        self.assertTrue('host_node' in states[0]['id'])
        self.assertTrue('db_node' in states[1]['id'])

    @timeout(seconds=120)
    def test_execute_operation_failure(self):
        from plugins.cloudmock.tasks import set_raise_exception_on_start
        send_task(set_raise_exception_on_start).get(timeout=10)
        dsl_path = resource("dsl/basic.yaml")
        try:
            deploy(dsl_path)
            self.fail('expected exception')
        except Exception:
            pass

    def test_cloudify_runtime_properties_injection(self):
        dsl_path = resource("dsl/dependencies-order-with-two-nodes.yaml")
        deploy(dsl_path)

        from plugins.testmockoperations.tasks import get_state as \
            testmock_get_state
        states = send_task(testmock_get_state).get(timeout=10)
        node_runtime_props = None
        for k, v in states[1]['capabilities'].iteritems():
            if 'host_node' in k:
                node_runtime_props = v
                break
        self.assertEquals('value1', node_runtime_props['property1'])
        self.assertEquals(1,
                          len(node_runtime_props),
                          msg='Expected 2 but contains: {0}'.format(
                              node_runtime_props))

    def test_non_existing_operation_exception(self):
        dsl_path = resource("dsl/wrong_operation_name.yaml")
        self.assertRaises(RuntimeError, deploy, dsl_path)

    def test_inject_properties_to_operation(self):
        dsl_path = resource("dsl/hardcoded-operation-properties.yaml")
        deploy(dsl_path)
        from plugins.testmockoperations.tasks import get_state as \
            testmock_get_state
        states = send_task(testmock_get_state).get(timeout=10)
        from plugins.testmockoperations.tasks import \
            get_mock_operation_invocations as testmock_get__invocations
        invocations = send_task(testmock_get__invocations).get(timeout=10)
        self.assertEqual(1, len(invocations))
        invocation = invocations[0]
        self.assertEqual('mockpropvalue', invocation['mockprop'])
        self.assertEqual('mockpropvalue2', invocation['properties']
                                                     ['mockprop2'])
        self.assertEqual(states[0]['id'], invocation['id'])

    def test_start_monitor_node_operation(self):
        dsl_path = resource("dsl/hardcoded-operation-properties.yaml")
        deploy(dsl_path)
        from plugins.testmockoperations.tasks import \
            get_monitoring_operations_invocation
        invocations = send_task(get_monitoring_operations_invocation)\
            .get(timeout=10)
        self.assertEqual(1, len(invocations))
        invocation = invocations[0]
        self.assertEqual('start_monitor', invocation['operation'])

    def test_plugin_get_resource(self):
        dsl_path = resource("dsl/get_resource_in_plugin.yaml")
        deploy(dsl_path)
        from plugins.testmockoperations.tasks import \
            get_resource_operation_invocations as testmock_get_invocations
        invocations = send_task(testmock_get_invocations).get(
            timeout=10)
        self.assertEquals(1, len(invocations))
        invocation = invocations[0]
        with open(resource("dsl/basic.yaml")) as f:
            basic_data = f.read()

        # checking the resources are the correct data
        self.assertEquals(basic_data, invocation['res1_data'])
        self.assertEquals(basic_data, invocation['res2_data'])

        # checking the custom filepath provided is indeed where the second
        # resource was saved
        self.assertEquals(invocation['custom_filepath'],
                          invocation['res2_path'])

    def test_search(self):
        dsl_path = resource("dsl/basic.yaml")
        blueprint_id = 'my_new_blueprint'
        deployment, _ = deploy(dsl_path, blueprint_id=blueprint_id)

        self.assertEqual(blueprint_id, deployment.blueprint_id)

        from plugins.cloudmock.tasks import get_machines
        result = send_task(get_machines)
        machines = result.get(timeout=10)

        self.assertEquals(1, len(machines))
        result = self.client.search.run_query('')
        hits = map(lambda x: x['_source'], result['hits']['hits'])

        self.assertEquals(7, len(hits))

    def test_get_blueprint(self):
        dsl_path = resource("dsl/basic.yaml")
        blueprint_id = str(uuid.uuid4())
        deployment, _ = deploy(dsl_path, blueprint_id=blueprint_id)

        self.assertEqual(blueprint_id, deployment.blueprint_id)
        blueprint = self.client.blueprints.get(blueprint_id)
        self.assertEqual(blueprint_id, blueprint.id)
        self.assertTrue(len(blueprint['plan']) > 0)

    def test_delete_blueprint(self):
        dsl_path = resource("dsl/basic.yaml")
        blueprint_id = self.client.blueprints.upload(dsl_path,
                                                     str(uuid.uuid4())).id
        # verifying blueprint exists
        result = self.client.blueprints.get(blueprint_id)
        self.assertEqual(blueprint_id, result.id)
        # deleting blueprint
        deleted_bp_id = self.client.blueprints.delete(blueprint_id).id
        self.assertEqual(blueprint_id, deleted_bp_id)
        # verifying blueprint does no longer exist
        try:
            self.client.blueprints.get(blueprint_id)
            self.fail("Got blueprint {0} successfully even though it "
                      "wasn't expected to exist".format(blueprint_id))
        except CloudifyClientError:
            pass
        # trying to delete a nonexistent blueprint
        try:
            self.client.blueprints.delete(blueprint_id)
            self.fail("Deleted blueprint {0} successfully even though it "
                      "wasn't expected to exist".format(blueprint_id))
        except CloudifyClientError:
            pass

    def test_delete_deployment(self):
        dsl_path = resource("dsl/basic.yaml")
        blueprint_id = self.id()
        deployment_id = str(uuid.uuid4())

        def change_execution_status(execution_id, status):
            self.client.executions.update(execution_id, status)
            time.sleep(5)  # waiting for elasticsearch to update...
            executions = self.client.deployments.list_executions(deployment_id)
            updated_execution = next(execution for execution in executions
                                     if execution.id == execution_id)
            self.assertEqual(status, updated_execution.status)

        # verifying a deletion of a new deployment, i.e. one which hasn't
        # been installed yet, and therefore all its nodes are still in
        # 'uninitialized' state.
        self.client.blueprints.upload(dsl_path, blueprint_id)
        self.client.deployments.create(blueprint_id, deployment_id)
        time.sleep(5)  # waiting for elasticsearch to update execution...
        self.client.deployments.delete(deployment_id, False)
        time.sleep(5)  # waiting for elasticsearch to clear deployment...
        self.client.blueprints.delete(blueprint_id)

        # recreating the deployment, this time actually deploying it too
        _, execution_id = deploy(dsl_path,
                                 blueprint_id=blueprint_id,
                                 deployment_id=deployment_id,
                                 wait_for_execution=True)

        # execution is supposed to be 'terminated' anyway, but verifying it
        # anyway (plus elasticsearch might need time to update..)
        change_execution_status(execution_id, Execution.TERMINATED)

        # verifying deployment exists
        result = self.client.deployments.get(deployment_id)
        self.assertEqual(deployment_id, result.id)

        # retrieving deployment nodes
        nodes = self.client.node_instances.list(deployment_id=deployment_id)
        self.assertTrue(len(nodes) > 0)
        nodes_ids = [node.id for node in nodes]

        # setting one node's state to 'started' (making it a 'live' node)
        # node must be read using get in order for it to have a version.
        node = self.client.node_instances.get(nodes[0].id)
        self.client.node_instances.update(node.id,
                                          state='started',
                                          version=node.version)

        # setting the execution's status to 'started' so it'll prevent the
        # deployment deletion
        change_execution_status(execution_id, Execution.STARTED)

        # attempting to delete the deployment - should fail because the
        # execution is active
        try:
            self.client.deployments.delete(deployment_id)

            self.fail("Deleted deployment {0} successfully even though it "
                      "should have had a running execution"
                      .format(deployment_id))
        except CloudifyClientError, e:
            self.assertTrue('running executions' in str(e))

        # setting the execution's status to 'terminated' so it won't prevent
        #  the deployment deletion
        change_execution_status(execution_id, Execution.TERMINATED)

        # attempting to delete deployment - should fail because there are
        # live nodes for this deployment
        try:
            self.client.deployments.delete(deployment_id)
            self.fail("Deleted deployment {0} successfully even though it "
                      "should have had live nodes and the ignore_live_nodes "
                      "flag was set to False".format(deployment_id))
        except CloudifyClientError, e:
            self.assertTrue('live nodes' in str(e))

        # deleting deployment - this time there's no execution running,
        # and using the ignore_live_nodes parameter to force deletion
        deleted_deployment_id = self.client.deployments.delete(
            deployment_id, True).id
        self.assertEqual(deployment_id, deleted_deployment_id)

        # verifying deployment does no longer exist
        try:
            self.client.deployments.get(deployment_id)
            self.fail("Got deployment {0} successfully even though it "
                      "wasn't expected to exist".format(deployment_id))
        except CloudifyClientError, e:
            self.assertTrue('not found' in str(e))

        # verifying deployment's execution does no longer exist
        try:
            self.client.executions.get(execution_id)
            self.fail('execution {0} still exists even though it should have '
                      'been deleted when its deployment was deleted'
                      .format(execution_id))
        except CloudifyClientError, e:
            self.assertTrue('not found' in str(e))

        # verifying deployment's nodes do no longer exist
        for node_id in nodes_ids:
            try:
                self.client.node_instances.get(node_id)
                self.fail('node {0} still exists even though it should have '
                          'been deleted when its deployment was deleted'
                          .format(node_id))
            except CloudifyClientError, e:
                self.assertTrue('not found' in str(e))

        # trying to delete a nonexistent deployment
        try:
            self.client.deployments.delete(deployment_id)
            self.fail("Deleted deployment {0} successfully even though it "
                      "wasn't expected to exist".format(deployment_id))
        except CloudifyClientError, e:
            self.assertTrue('not found' in str(e))

    def test_node_state_uninitialized(self):
        dsl_path = resource('dsl/node_states.yaml')
        _id = uuid.uuid1()
        blueprint_id = 'blueprint_{0}'.format(_id)
        deployment_id = 'deployment_{0}'.format(_id)
        self.client.blueprints.upload(dsl_path, blueprint_id)
        self.client.deployments.create(blueprint_id, deployment_id)

        def assert_deployment_nodes_length():
            deployment_nodes = self.client.node_instances.list(
                deployment_id=deployment_id)
            self.assertEqual(1, len(deployment_nodes))

        self.do_assertions(assert_deployment_nodes_length, timeout=30)

        deployment_nodes = self.client.node_instances.list(
            deployment_id=deployment_id)
        node_id = deployment_nodes[0].id
        node_instance = self.client.node_instances.get(node_id)
        self.assertEqual('uninitialized', node_instance.state)

    def test_node_states(self):
        dsl_path = resource('dsl/node_states.yaml')
        _id = uuid.uuid1()
        blueprint_id = 'blueprint_{0}'.format(_id)
        deployment_id = 'deployment_{0}'.format(_id)
        deployment, _ = deploy(dsl_path,
                               blueprint_id=blueprint_id,
                               deployment_id=deployment_id)

        from plugins.testmockoperations.tasks import get_node_states
        node_states = send_task(get_node_states).get(timeout=10)

        self.assertEquals(node_states, [
            'creating', 'configuring', 'starting'
        ])

        deployment_nodes = self.client.node_instances.list(
            deployment_id=deployment_id)
        self.assertEqual(1, len(deployment_nodes))
        node_id = deployment_nodes[0].id
        node_instance = self.client.node_instances.get(node_id)
        self.assertEqual('started', node_instance.state)
