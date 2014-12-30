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

import uuid
import time
import errno
from os import path

import cloudify.context
from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify_rest_client.executions import Execution

from testenv import TestCase
from testenv.utils import get_resource as resource
from testenv.utils import do_retries
from testenv.utils import timeout
from testenv.utils import verify_deployment_environment_creation_complete
from testenv.utils import deploy_application as deploy
from testenv.utils import undeploy_application as undeploy


class BasicWorkflowsTest(TestCase):

    def test_execute_operation(self):
        dsl_path = resource('dsl/basic.yaml')
        blueprint_id = self.id()
        deployment, _ = deploy(
            dsl_path,
            blueprint_id=blueprint_id,
            timeout_seconds=15
        )

        self.assertEqual(blueprint_id, deployment.blueprint_id)

        machines = self.get_plugin_data(
            plugin_name='cloudmock',
            deployment_id=deployment.id
        )['machines']
        self.assertEquals(1, len(machines))

        outputs = self.client.deployments.outputs.get(deployment.id).outputs
        # ip runtime property is not set in this case
        self.assertEquals(outputs['ip_address'], '')

    def test_dependencies_order_with_two_nodes(self):
        dsl_path = resource("dsl/dependencies_order_with_two_nodes.yaml")
        blueprint_id = self.id()
        deployment, _ = deploy(dsl_path, blueprint_id=blueprint_id)

        self.assertEquals(blueprint_id, deployment.blueprint_id)

        states = self.get_plugin_data(
            plugin_name='testmockoperations',
            deployment_id=deployment.id
        )['state']
        self.assertEquals(2, len(states))
        self.assertTrue('host_node' in states[0]['id'])
        self.assertTrue('db_node' in states[1]['id'])

    @timeout(seconds=120)
    def test_execute_operation_failure(self):
        deployment_id = str(uuid.uuid4())
        dsl_path = resource("dsl/basic.yaml")
        try:
            deploy(dsl_path, deployment_id=deployment_id)
            self.fail('expected exception')
        except Exception as e:
            if e.message:
                self.logger.info(e.message)
            pass

    def test_cloudify_runtime_properties_injection(self):
        dsl_path = resource("dsl/dependencies_order_with_two_nodes.yaml")
        deployment, _ = deploy(dsl_path)
        states = self.get_plugin_data(
            plugin_name='testmockoperations',
            deployment_id=deployment.id
        )['state']
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
        dsl_path = resource("dsl/hardcoded_operation_properties.yaml")
        deployment, _ = deploy(dsl_path)
        states = self.get_plugin_data(
            plugin_name='testmockoperations',
            deployment_id=deployment.id
        )['state']
        invocations = self.get_plugin_data(
            plugin_name='testmockoperations',
            deployment_id=deployment.id
        )['mock_operation_invocation']
        self.assertEqual(1, len(invocations))
        invocation = invocations[0]
        self.assertEqual('mockpropvalue', invocation['mockprop'])
        self.assertEqual(states[0]['id'], invocation['id'])

    def test_start_monitor_node_operation(self):
        dsl_path = resource("dsl/hardcoded_operation_properties.yaml")
        deployment, _ = deploy(dsl_path)
        invocations = self.get_plugin_data(
            plugin_name='testmockoperations',
            deployment_id=deployment.id
        )['monitoring_operations_invocation']
        self.assertEqual(1, len(invocations))
        invocation = invocations[0]
        self.assertEqual('start_monitor', invocation['operation'])

    def test_plugin_get_resource(self):
        dsl_path = resource("dsl/get_resource_in_plugin.yaml")
        deployment, _ = deploy(dsl_path)
        invocations = self.get_plugin_data(
            plugin_name='testmockoperations',
            deployment_id=deployment.id
        )['get_resource_operation_invocation']
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

        machines = self.get_plugin_data(
            plugin_name='cloudmock',
            deployment_id=deployment.id
        )['machines']
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

        def change_execution_status(_execution_id, status):
            self.client.executions.update(_execution_id, status)
            time.sleep(2)  # waiting for elasticsearch to update...
            executions = self.client.executions.list(deployment_id)
            updated_execution = next(execution for execution in executions
                                     if execution.id == _execution_id)
            self.assertEqual(status, updated_execution.status)

        # verifying a deletion of a new deployment, i.e. one which hasn't
        # been installed yet, and therefore all its nodes are still in
        # 'uninitialized' state.
        self.client.blueprints.upload(dsl_path, blueprint_id)
        self.client.deployments.create(blueprint_id, deployment_id)
        do_retries(verify_deployment_environment_creation_complete, 30,
                   deployment_id=deployment_id)

        self.client.deployments.delete(deployment_id, False)
        time.sleep(5)  # elasticsearch...
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
            _deployment_nodes = self.client.node_instances.list(
                deployment_id=deployment_id)
            self.assertEqual(1, len(_deployment_nodes))

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
        node_states = self.get_plugin_data(
            plugin_name='testmockoperations',
            deployment_id=deployment.id
        )['node_states']
        self.assertEquals(node_states, [
            'creating', 'configuring', 'starting'
        ])

        deployment_nodes = self.client.node_instances.list(
            deployment_id=deployment_id)
        self.assertEqual(1, len(deployment_nodes))
        node_id = deployment_nodes[0].id
        node_instance = self.client.node_instances.get(node_id)
        self.assertEqual('started', node_instance.state)

    def test_deploy_with_agent_worker(self):
        dsl_path = resource('dsl/with_agent_worker.yaml')
        deployment, _ = deploy(dsl_path)
        deployment_nodes = self.client.node_instances.list(
            deployment_id=deployment.id
        )

        webserver_nodes = filter(lambda node: 'host' not in node.node_id,
                                 deployment_nodes)
        self.assertEquals(1, len(webserver_nodes))
        webserver_node = webserver_nodes[0]
        invocations = self.get_plugin_data(
            plugin_name='mock_agent_plugin',
            deployment_id=deployment.id
        )[webserver_node.id]

        worker_installer_data = self.get_plugin_data(
            plugin_name='agent_installer',
            deployment_id=deployment.id
        )

        # agent on host should have been started and restarted
        self.assertEqual(
            worker_installer_data[webserver_node.host_id]['states'],
            ['installed', 'started', 'restarted'])

        plugin_installer_data = self.get_plugin_data(
            plugin_name='plugin_installer',
            deployment_id=deployment.id
        )

        self.assertEqual(
            plugin_installer_data[
                webserver_node.host_id
            ]['mock_agent_plugin'],
            ['installed'])

        expected_invocations = ['create', 'start']
        self.assertListEqual(invocations, expected_invocations)

        undeploy(deployment_id=deployment.id)
        invocations = self.get_plugin_data(
            plugin_name='mock_agent_plugin',
            deployment_id=deployment.id
        )[webserver_node.id]

        expected_invocations = ['create', 'start', 'stop', 'delete']
        self.assertListEqual(invocations, expected_invocations)

        # agent on host should have also
        # been stopped and uninstalled
        worker_installer_data = self.get_plugin_data(
            plugin_name='agent_installer',
            deployment_id=deployment.id
        )
        self.assertEqual(
            worker_installer_data[webserver_node.host_id]['states'],
            ['installed', 'started', 'restarted', 'stopped', 'uninstalled'])

    def test_deploy_with_agent_worker_windows(self):
        dsl_path = resource('dsl/with_agent_worker_windows.yaml')
        deployment, _ = deploy(dsl_path)
        deployment_nodes = self.client.node_instances.list(
            deployment_id=deployment.id
        )

        webserver_nodes = filter(lambda node: 'host' not in node.node_id,
                                 deployment_nodes)
        self.assertEquals(1, len(webserver_nodes))
        webserver_node = webserver_nodes[0]
        invocations = self.get_plugin_data(
            plugin_name='mock_agent_plugin',
            deployment_id=deployment.id
        )[webserver_node.id]

        worker_installer_data = self.get_plugin_data(
            plugin_name='agent_installer',
            deployment_id=deployment.id
        )

        # agent on host should have been started and restarted
        self.assertEqual(
            worker_installer_data[webserver_node.host_id]['states'],
            ['installed', 'started', 'restarted'])

        plugin_installer_data = self.get_plugin_data(
            plugin_name='windows_plugin_installer',
            deployment_id=deployment.id
        )

        self.assertEqual(
            plugin_installer_data[
                webserver_node.host_id
            ]['mock_agent_plugin'],
            ['installed'])

        expected_invocations = ['create', 'start']
        self.assertListEqual(invocations, expected_invocations)

        undeploy(deployment_id=deployment.id)
        invocations = self.get_plugin_data(
            plugin_name='mock_agent_plugin',
            deployment_id=deployment.id
        )[webserver_node.id]

        expected_invocations = ['create', 'start', 'stop', 'delete']
        self.assertListEqual(invocations, expected_invocations)

        # agent on host should have also
        # been stopped and uninstalled
        worker_installer_data = self.get_plugin_data(
            plugin_name='agent_installer',
            deployment_id=deployment.id
        )
        self.assertEqual(
            worker_installer_data[webserver_node.host_id]['states'],
            ['installed', 'started', 'restarted', 'stopped', 'uninstalled'])

    def test_deploy_with_operation_executor_override(self):
        dsl_path = resource('dsl/operation_executor_override.yaml')
        deployment, _ = deploy(dsl_path)
        deployment_nodes = self.client.node_instances.list(
            deployment_id=deployment.id
        )

        webserver_nodes = filter(lambda node: 'host' not in node.node_id,
                                 deployment_nodes)
        self.assertEquals(1, len(webserver_nodes))
        webserver_node = webserver_nodes[0]
        start_invocation = self.get_plugin_data(
            plugin_name='target_aware_mock_plugin',
            deployment_id=deployment.id
        )[webserver_node.id]['start']

        expected_start_invocation = {'target': deployment.id}
        self.assertEqual(expected_start_invocation, start_invocation)

        plugin_installer_data = self.get_plugin_data(
            plugin_name='plugin_installer',
            deployment_id=deployment.id
        )

        deployment_operations_worker_name = deployment.id
        # target_aware_mock_plugin should have been installed
        # on the deployment worker as well because 'start'
        # overrides the executor
        self.assertEqual(
            plugin_installer_data[
                deployment_operations_worker_name
            ]['target_aware_mock_plugin'],
            ['installed'])
        undeploy(deployment_id=deployment.id)

    def test_deployment_creation_workflow(self):

        dsl_path = resource(
            'dsl/basic_with_deployment_plugin_and_workflow_plugin.yaml'
        )
        deployment, _ = deploy(dsl_path)

        def _is_riemann_core_up():
            try:
                with open(path.join(self.riemann_workdir,
                                    deployment.id,
                                    'ok')) as f:
                    return f.read().strip() == 'ok'
            except IOError, e:
                if e.errno == errno.ENOENT:
                    return False
                raise

        self.assertTrue(_is_riemann_core_up())

        deployment_operations_worker_name = deployment.id
        deployment_workflows_worker_name = '{0}_workflows'\
            .format(deployment.id)

        data = self.get_plugin_data(plugin_name='agent_installer',
                                    deployment_id=deployment.id)

        # assert both deployment and workflows plugins
        # were installed, started and restarted
        # this is because we both install a custom
        # workflow and a deployment plugin
        self.assertEqual(data[deployment_operations_worker_name]['states'],
                         ['installed', 'started', 'restarted'])
        self.assertEqual(data[deployment_workflows_worker_name]['states'],
                         ['installed', 'started', 'restarted'])

        # assert plugin installer installed
        # the necessary plugins.
        plugin_installer_data = self.get_plugin_data(
            plugin_name='plugin_installer',
            deployment_id=deployment.id
        )

        # cloudmock should have been installed
        # on the deployment worker
        self.assertEqual(
            plugin_installer_data[
                deployment_operations_worker_name
            ]['cloudmock'],
            ['installed'])

        # mock_workflows should have been
        # installed on the workflows worker
        self.assertEqual(plugin_installer_data[
                         deployment_workflows_worker_name
                         ]['mock_workflows'],
                         ['installed'])

        undeploy(deployment.id, delete_deployment=True)

        data = self.get_plugin_data(plugin_name='agent_installer',
                                    deployment_id=deployment.id)

        # assert both deployment and workflows plugins
        # were stopped and uninstalled
        self.assertEqual(data[deployment_operations_worker_name]['states'],
                         ['installed', 'started', 'restarted',
                          'stopped', 'uninstalled'])
        self.assertEqual(data[deployment_workflows_worker_name]['states'],
                         ['installed', 'started', 'restarted',
                          'stopped', 'uninstalled'])

        self.assertFalse(_is_riemann_core_up())

    def test_get_attribute(self):
        # assertion happens in operation get_attribute.tasks.assertion
        dsl_path = resource('dsl/get_attributes.yaml')
        deployment, _ = deploy(dsl_path)
        data = self.get_plugin_data(plugin_name='get_attribute',
                                    deployment_id=deployment.id)
        invocations = data['invocations']
        self.assertEqual(2, len([
            i for i in invocations
            if i == cloudify.context.RELATIONSHIP_INSTANCE]))
        self.assertEqual(1, len([
            i for i in invocations
            if i == cloudify.context.NODE_INSTANCE]))
