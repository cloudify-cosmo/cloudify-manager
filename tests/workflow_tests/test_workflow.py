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
import unittest
from testenv import undeploy_application as undeploy
from workflow_tests.testenv import TestCase
from workflow_tests.testenv import get_resource as resource
from workflow_tests.testenv import deploy_application as deploy
from workflow_tests.testenv import timeout
from workflow_tests.testenv import run_search as search
from workflow_tests.testenv import get_blueprint
from workflow_tests.testenv import delete_blueprint
from workflow_tests.testenv import get_deployment
from workflow_tests.testenv import delete_deployment
from workflow_tests.testenv import publish_blueprint
from workflow_tests.testenv import cancel_execution
from workflow_tests.testenv import get_execution
from workflow_tests.testenv import update_node_instance
from workflow_tests.testenv import DEPLOYMENT_QUEUE_NAME
from workflow_tests.testenv import create_rest_client
from testenv import get_node_instance
from testenv import get_deployment_nodes
from cosmo_manager_rest_client.cosmo_manager_rest_client \
    import CosmoManagerRestCallError


class BasicWorkflowsTest(TestCase):

    def test_execute_operation(self):
        dsl_path = resource("dsl/basic.yaml")
        blueprint_id = self.id()
        deployment, _ = deploy(dsl_path, blueprint_id=blueprint_id)

        self.assertEqual(blueprint_id, deployment.blueprintId)

        from plugins.cloudmock.tasks import get_machines
        result = self.send_task(get_machines)
        machines = result.get(timeout=10)

        self.assertEquals(1, len(machines))

    def test_dependencies_order_with_two_nodes(self):
        dsl_path = resource("dsl/dependencies-order-with-two-nodes.yaml")
        blueprint_id = self.id()
        deployment, _ = deploy(dsl_path, blueprint_id=blueprint_id)

        self.assertEquals(blueprint_id, deployment.blueprintId)

        from plugins.testmockoperations.tasks import get_state as \
            testmock_get_state
        states = self.send_task(testmock_get_state) \
            .get(timeout=10)
        self.assertEquals(2, len(states))
        self.assertTrue('host_node' in states[0]['id'])
        self.assertTrue('db_node' in states[1]['id'])

    @timeout(seconds=120)
    def test_execute_operation_failure(self):
        from plugins.cloudmock.tasks import set_raise_exception_on_start
        self.send_task(set_raise_exception_on_start).get(timeout=10)
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
        states = self.send_task(testmock_get_state).get(timeout=10)
        node_runtime_props = None
        for k, v in states[1]['capabilities'].iteritems():
            if 'host_node' in k:
                node_runtime_props = v
                break
        self.assertEquals('value1', node_runtime_props['property1'])
        # length should be 2 because of auto injected ip property
        self.assertEquals(1,
                          len(node_runtime_props),
                          msg='Expected 2 but contains: {0}'.format(
                              node_runtime_props))

    def test_dsl_with_agent_plugin(self):
        dsl_path = resource("dsl/with_plugin.yaml")
        deploy(dsl_path, deployment_id=DEPLOYMENT_QUEUE_NAME)

        from plugins.plugin_installer.tasks import get_installed_plugins as \
            test_get_installed_plugins
        result = self.send_task(test_get_installed_plugins)
        installed_plugins = result.get(timeout=10)
        self.assertTrue("test_plugin" in installed_plugins)

    def test_dsl_with_manager_plugin(self):
        dsl_path = resource("dsl/with_manager_plugin.yaml")
        deployment, _ = deploy(dsl_path, deployment_id=DEPLOYMENT_QUEUE_NAME)
        deployment_id = deployment.id

        from plugins.worker_installer.tasks import \
            RESTARTED, STARTED, INSTALLED, STOPPED, UNINSTALLED

        from plugins.worker_installer.tasks \
            import get_current_worker_state as \
            test_get_current_worker_state
        result = self.send_task(test_get_current_worker_state)
        state = result.get(timeout=10)
        self.assertEquals(state, [INSTALLED, STARTED, RESTARTED])

        undeploy(deployment_id)
        result = self.send_task(test_get_current_worker_state)
        state = result.get(timeout=10)
        self.assertEquals(state,
                          [INSTALLED, STARTED,
                           RESTARTED, STOPPED, UNINSTALLED])

    def test_non_existing_operation_exception(self):
        dsl_path = resource("dsl/wrong_operation_name.yaml")
        self.assertRaises(RuntimeError, deploy, dsl_path)

    def test_inject_properties_to_operation(self):
        dsl_path = resource("dsl/hardcoded-operation-properties.yaml")
        deploy(dsl_path)
        from plugins.testmockoperations.tasks import get_state as \
            testmock_get_state
        states = self.send_task(testmock_get_state).get(timeout=10)
        from plugins.testmockoperations.tasks import \
            get_mock_operation_invocations as testmock_get__invocations
        invocations = self.send_task(testmock_get__invocations).get(timeout=10)
        self.assertEqual(1, len(invocations))
        invocation = invocations[0]
        self.assertEqual('mockpropvalue', invocation['mockprop'])
        self.assertEqual('mockpropvalue2', invocation['kwargs']['mockprop2'])
        self.assertTrue('__cloudify_context' in invocation['kwargs'])
        self.assertEqual(states[0]['id'], invocation['id'])

    def test_plugin_get_resource(self):
        dsl_path = resource("dsl/get_resource_in_plugin.yaml")
        deploy(dsl_path)
        from plugins.testmockoperations.tasks import \
            get_resource_operation_invocations as testmock_get_invocations
        invocations = self.send_task(testmock_get_invocations).get(
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

        self.assertEqual(blueprint_id, deployment.blueprintId)

        from plugins.cloudmock.tasks import get_machines
        result = self.send_task(get_machines)
        machines = result.get(timeout=10)

        self.assertEquals(1, len(machines))
        result = search('')
        hits = map(lambda x: x['_source'], result['hits']['hits'])

        # expecting 4 results - 1 blueprint, 1 deployment, 1 execution, 1 node.
        self.assertEquals(4, len(hits))

    def test_get_blueprint(self):
        dsl_path = resource("dsl/basic.yaml")
        blueprint_id = str(uuid.uuid4())
        deployment, _ = deploy(dsl_path, blueprint_id=blueprint_id)

        self.assertEqual(blueprint_id, deployment.blueprintId)
        blueprint = get_blueprint(blueprint_id)
        self.assertEqual(blueprint_id, blueprint.id)
        self.assertTrue(len(blueprint.plan) > 0)
        self.assertEqual('None', blueprint.source)

    def test_delete_blueprint(self):
        dsl_path = resource("dsl/basic.yaml")
        blueprint_id = publish_blueprint(dsl_path)
        # verifying blueprint exists
        result = get_blueprint(blueprint_id)
        self.assertEqual(blueprint_id, result.id)
        # deleting blueprint
        deleted_bp_id = delete_blueprint(blueprint_id).id
        self.assertEqual(blueprint_id, deleted_bp_id)
        # verifying blueprint does no longer exist
        try:
            get_blueprint(blueprint_id)
            self.fail("Got blueprint {0} successfully even though it "
                      "wasn't expected to exist".format(blueprint_id))
        except CosmoManagerRestCallError:
            pass
        # trying to delete a nonexistent blueprint
        try:
            delete_blueprint(blueprint_id)
            self.fail("Deleted blueprint {0} successfully even though it "
                      "wasn't expected to exist".format(blueprint_id))
        except CosmoManagerRestCallError:
            pass

    def test_delete_deployment(self):
        dsl_path = resource("dsl/basic.yaml")
        blueprint_id = self.id()
        deployment_id = str(uuid.uuid4())

        # verifying a deletion of a new deployment, i.e. one which hasn't
        # been installed yet, and therefore all its nodes are still in
        # 'uninitialized' state.
        client = create_rest_client()
        client.publish_blueprint(dsl_path, blueprint_id)
        client.create_deployment(blueprint_id, deployment_id)
        delete_deployment(deployment_id, False)
        time.sleep(5)  # waiting for elasticsearch to clear deployment...
        delete_blueprint(blueprint_id)

        # recreating the deployment, this time actually deploying it too
        _, execution_id = deploy(dsl_path,
                                 blueprint_id=blueprint_id,
                                 deployment_id=deployment_id,
                                 wait_for_execution=False)

        # verifying deployment exists
        result = get_deployment(deployment_id)
        self.assertEqual(deployment_id, result.id)

        # retrieving deployment nodes
        nodes = get_deployment_nodes(deployment_id, True).nodes
        self.assertTrue(len(nodes) > 0)
        nodes_ids = [node.id for node in nodes]

        # setting one node's state to 'started' (making it a 'live' node)
        update_node_instance(nodes[0].id, nodes[0].stateVersion,
                             state='started')

        # attempting to delete the deployment - should fail because the
        # execution should be active
        try:
            delete_deployment(deployment_id, False)

            self.fail("Deleted deployment {0} successfully even though it "
                      "should have had a running execution"
                      .format(deployment_id))
        except CosmoManagerRestCallError, e:
            # self.assertTrue('live nodes' in str(e))
            pass

        # stopping the execution
        execution = cancel_execution(execution_id, True)
        self.assertEquals(execution.status, 'terminated')

        # attempting to delete deployment - should fail because there are
        # live nodes for this deployment
        try:
            delete_deployment(deployment_id, False)
            self.fail("Deleted deployment {0} successfully even though it "
                      "should have had live nodes and the ignore_live_nodes "
                      "flag was set to False".format(deployment_id))
        except CosmoManagerRestCallError:
            self.assertTrue('live nodes' in str(e))

        # deleting deployment - this time there's no execution running,
        # and using the ignore_live_nodes parameter to force deletion
        deleted_deployment_id = delete_deployment(deployment_id, True).id
        self.assertEqual(deployment_id, deleted_deployment_id)

        # verifying deployment does no longer exist
        try:
            get_deployment(deployment_id)
            self.fail("Got deployment {0} successfully even though it "
                      "wasn't expected to exist".format(deployment_id))
        except CosmoManagerRestCallError, e:
            self.assertTrue('not found' in str(e))

        # verifying deployment's execution does no longer exist
        try:
            get_execution(execution_id)
            self.fail('execution {0} still exists even though it should have '
                      'been deleted when its deployment was deleted'
                      .format(execution_id))
        except CosmoManagerRestCallError, e:
            self.assertTrue('not found' in str(e))

        # verifying deployment's nodes do no longer exist
        for node_id in nodes_ids:
            try:
                get_node_instance(node_id)
                self.fail('node {0} still exists even though it should have '
                          'been deleted when its deployment was deleted'
                          .format(node_id))
            except CosmoManagerRestCallError, e:
                self.assertTrue('not found' in str(e))

        # trying to delete a nonexistent deployment
        try:
            delete_deployment(deployment_id)
            self.fail("Deleted deployment {0} successfully even though it "
                      "wasn't expected to exist".format(deployment_id))
        except CosmoManagerRestCallError, e:
            self.assertTrue('not found' in str(e))

    def test_node_state_uninitialized(self):
        dsl_path = resource('dsl/node_states.yaml')
        _id = uuid.uuid1()
        blueprint_id = 'blueprint_{0}'.format(_id)
        deployment_id = 'deployment_{0}'.format(_id)
        client = create_rest_client()
        client.publish_blueprint(dsl_path, blueprint_id)
        client.create_deployment(blueprint_id, deployment_id)
        deployment_nodes = get_deployment_nodes(deployment_id)
        self.assertEqual(1, len(deployment_nodes.nodes))
        node_id = deployment_nodes.nodes[0].id
        node_instance = get_node_instance(node_id)
        self.assertEqual('uninitialized', node_instance['state'])

    def test_node_states(self):
        dsl_path = resource('dsl/node_states.yaml')
        _id = uuid.uuid1()
        blueprint_id = 'blueprint_{0}'.format(_id)
        deployment_id = 'deployment_{0}'.format(_id)
        deployment, _ = deploy(dsl_path,
                               blueprint_id=blueprint_id,
                               deployment_id=deployment_id)

        from plugins.testmockoperations.tasks import get_node_states
        node_states = self.send_task(get_node_states).get(timeout=10)

        self.assertEquals(node_states, [
            'creating', 'configuring', 'starting'
        ])

        deployment_nodes = get_deployment_nodes(deployment_id)
        self.assertEqual(1, len(deployment_nodes.nodes))
        node_id = deployment_nodes.nodes[0].id
        node_instance = get_node_instance(node_id)
        self.assertEqual('started', node_instance['state'])
