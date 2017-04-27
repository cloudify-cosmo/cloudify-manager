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

import os
import uuid
import tarfile
import tempfile
from contextlib import contextmanager

import retrying
import sh

from cloudify import context
from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify_rest_client.executions import Execution

from integration_tests import AgentlessTestCase
from integration_tests.framework.utils import timeout
from integration_tests.tests.utils import (
    get_resource,
    do_retries,
    verify_deployment_environment_creation_complete
)

from manager_rest.constants import DEFAULT_TENANT_NAME


class BasicWorkflowsTest(AgentlessTestCase):
    def test_execute_operation(self):
        dsl_path = get_resource('dsl/basic.yaml')
        blueprint_id = self.id()
        deployment, _ = self.deploy_application(
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
        self.assertEquals(outputs['ip_address'], '')

    def test_dependencies_order_with_two_nodes(self):
        dsl_path = get_resource("dsl/dependencies_order_with_two_nodes.yaml")
        blueprint_id = self.id()
        deployment, _ = self.deploy_application(dsl_path,
                                                blueprint_id=blueprint_id)

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
        dsl_path = get_resource("dsl/basic.yaml")
        try:
            self.deploy_application(dsl_path, deployment_id=deployment_id)
            self.fail('expected exception')
        except Exception as e:
            if e.message:
                self.logger.info(e.message)
            pass

    def test_cloudify_runtime_properties_injection(self):
        dsl_path = get_resource("dsl/dependencies_order_with_two_nodes.yaml")
        deployment, _ = self.deploy_application(dsl_path)
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
        dsl_path = get_resource("dsl/wrong_operation_name.yaml")
        self.assertRaises(RuntimeError, self.deploy_application, dsl_path)

    def test_inject_properties_to_operation(self):
        dsl_path = get_resource("dsl/hardcoded_operation_properties.yaml")
        deployment, _ = self.deploy_application(dsl_path)
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
        dsl_path = get_resource("dsl/hardcoded_operation_properties.yaml")
        deployment, _ = self.deploy_application(dsl_path)
        invocations = self.get_plugin_data(
            plugin_name='testmockoperations',
            deployment_id=deployment.id
        )['monitoring_operations_invocation']
        self.assertEqual(1, len(invocations))
        invocation = invocations[0]
        self.assertEqual('start_monitor', invocation['operation'])

    def test_plugin_get_resource(self):
        dsl_path = get_resource("dsl/get_resource_in_plugin.yaml")
        deployment, _ = self.deploy_application(dsl_path)
        invocations = self.get_plugin_data(
            plugin_name='testmockoperations',
            deployment_id=deployment.id
        )['get_resource_operation_invocation']
        self.assertEquals(1, len(invocations))
        invocation = invocations[0]
        with open(get_resource("dsl/basic.yaml")) as f:
            basic_data = f.read()

        # checking the resources are the correct data
        self.assertEquals(basic_data, invocation['res1_data'])
        self.assertEquals(basic_data, invocation['res2_data'])

        # checking the custom filepath provided is indeed where the second
        # resource was saved
        self.assertEquals(invocation['custom_filepath'],
                          invocation['res2_path'])

    def test_get_blueprint(self):
        dsl_path = get_resource("dsl/basic.yaml")
        blueprint_id = str(uuid.uuid4())
        deployment, _ = self.deploy_application(dsl_path,
                                                blueprint_id=blueprint_id)

        self.assertEqual(blueprint_id, deployment.blueprint_id)
        blueprint = self.client.blueprints.get(blueprint_id)
        self.assertEqual(blueprint_id, blueprint.id)
        self.assertTrue(len(blueprint['plan']) > 0)

    def test_publish_tar_archive(self):
        archive_location = self._make_archive_file("dsl/basic.yaml")

        blueprint_id = self.client.blueprints.publish_archive(
            archive_location, str(uuid.uuid4()), 'basic.yaml').id
        # verifying blueprint exists
        result = self.client.blueprints.get(blueprint_id)
        self.assertEqual(blueprint_id, result.id)

    def _make_archive_file(self, blueprint_path, write_mode='w'):
        dsl_path = get_resource(blueprint_path)
        blueprint_dir = os.path.dirname(dsl_path)
        archive_location = tempfile.mkstemp()[1]
        arcname = os.path.basename(blueprint_dir)
        with tarfile.open(archive_location, write_mode) as tar:
            tar.add(blueprint_dir, arcname=arcname)
        return archive_location

    def test_delete_blueprint(self):
        dsl_path = get_resource("dsl/basic.yaml")
        blueprint_id = self.client.blueprints.upload(
            dsl_path, str(uuid.uuid4())).id

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
        dsl_path = get_resource("dsl/basic.yaml")
        blueprint_id = self.id()
        deployment_id = str(uuid.uuid4())

        def change_execution_status(execution_id, status):
            self.client.executions.update(execution_id, status)
            updated_execution = self.client.executions.get(deployment_id)
            self.assertEqual(status, updated_execution.status)

        @contextmanager
        def client_error_check(expect_in_error_message, failer_message):
            try:
                yield
                self.fail(failer_message)
            except CloudifyClientError as exc:
                self.assertTrue(expect_in_error_message in str(exc))

        # verifying a deletion of a new deployment, i.e. one which hasn't
        # been installed yet, and therefore all its nodes are still in
        # 'uninitialized' state.

        self.client.blueprints.upload(dsl_path, blueprint_id)
        self.client.deployments.create(blueprint_id, deployment_id,
                                       skip_plugins_validation=True)
        do_retries(verify_deployment_environment_creation_complete,
                   timeout_seconds=60,
                   deployment_id=deployment_id)

        self.delete_deployment(deployment_id, ignore_live_nodes=False)
        self.client.blueprints.delete(blueprint_id)

        # recreating the deployment, this time actually deploying it too
        _, execution_id = self.deploy_application(
            dsl_path,
            blueprint_id=blueprint_id,
            deployment_id=deployment_id,
            wait_for_execution=True)

        execution = self.client.executions.get(execution_id)
        self.assertEqual(Execution.TERMINATED, execution.status)

        # verifying deployment exists
        deployment = self.client.deployments.get(deployment_id)
        self.assertEqual(deployment_id, deployment.id)

        # retrieving deployment nodes
        nodes = self.client.node_instances.list(deployment_id=deployment_id)
        self.assertTrue(len(nodes) > 0)

        # setting one node's state to 'started' (making it a 'live' node)
        # node must be read using get in order for it to have a version.
        node = self.client.node_instances.get(nodes[0].id)
        self.client.node_instances.update(
            node.id, state='started', version=node.version)

        modification = self.client.deployment_modifications.start(
            deployment_id,
            nodes={'webserver_host': {'instances': 2}})
        self.client.deployment_modifications.finish(modification.id)

        # get updated node instances list
        nodes = self.client.node_instances.list(deployment_id=deployment_id)
        self.assertTrue(len(nodes) > 0)
        nodes_ids = [_node.id for _node in nodes]

        # attempting to delete deployment - should fail because there are
        # live nodes for this deployment
        with client_error_check(
                failer_message='Deleted deployment {0} successfully even '
                               'though it should have had live nodes and the '
                               'ignore_live_nodes flag was set to False'
                               .format(deployment_id),
                expect_in_error_message='live nodes'):
            self.delete_deployment(deployment_id)

        # deleting deployment - this time there's no execution running,
        # and using the ignore_live_nodes parameter to force deletion
        deleted_deployment_id = self.delete_deployment(deployment_id, True).id
        self.assertEqual(deployment_id, deleted_deployment_id)

        # verifying deployment does no longer exist
        with client_error_check(
                failer_message="Got deployment {0} successfully even though "
                               "it wasn't expected to exist"
                               .format(deployment_id),
                expect_in_error_message='not found'):
            self.client.deployments.get(deployment_id)

        # verifying deployment's execution does no longer exist
        with client_error_check(
                failer_message='execution {0} still exists even though it '
                               'should have been deleted when its deployment '
                               'was deleted'.format(execution_id),
                expect_in_error_message='not found'):
            self.client.executions.get(execution_id)

        # verifying deployment modification no longer exists
        with client_error_check(
                failer_message='deployment modification {0} still exists even '
                               'though it should have been deleted when its '
                               'deployment was deleted',
                expect_in_error_message='not found'):
            self.client.deployment_modifications.get(modification.id)

        # verifying deployment's nodes do no longer exist
        for node_id in nodes_ids:
            with client_error_check(
                    failer_message='node {0} still exists even though it '
                                   'should have been deleted when its '
                                   'deployment was deleted'.format(node_id),
                    expect_in_error_message='not found'):
                self.client.node_instances.get(node_id)

        # trying to delete a nonexistent deployment
        with client_error_check(
                failer_message="Deleted deployment {0} successfully even "
                               "though it wasn't expected to exist"
                               .format(deployment_id),
                expect_in_error_message='not found'):
            self.delete_deployment(deployment_id)

    def test_node_state_uninitialized(self):
        dsl_path = get_resource('dsl/node_states.yaml')
        _id = uuid.uuid1()
        blueprint_id = 'blueprint_{0}'.format(_id)
        deployment_id = 'deployment_{0}'.format(_id)
        self.client.blueprints.upload(dsl_path, blueprint_id)
        self.client.deployments.create(blueprint_id, deployment_id,
                                       skip_plugins_validation=True)

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
        dsl_path = get_resource('dsl/node_states.yaml')
        _id = uuid.uuid1()
        blueprint_id = 'blueprint_{0}'.format(_id)
        deployment_id = 'deployment_{0}'.format(_id)
        deployment, _ = self.deploy_application(
            dsl_path,
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
        dsl_path = get_resource('dsl/with_agent_worker.yaml')
        deployment, _ = self.deploy_application(dsl_path)
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

        agent_data = self.get_plugin_data(
            plugin_name='agent',
            deployment_id=deployment.id
        )

        # agent on host should have been started and restarted
        self.assertEqual(
            agent_data[webserver_node.host_id]['states'],
            ['created', 'configured', 'started'])

        self.assertEqual(
            agent_data[
                webserver_node.host_id
            ]['mock_agent_plugin'],
            ['installed'])

        expected_invocations = ['create', 'start']
        self.assertListEqual(invocations, expected_invocations)

        self.undeploy_application(deployment_id=deployment.id)
        invocations = self.get_plugin_data(
            plugin_name='mock_agent_plugin',
            deployment_id=deployment.id
        )[webserver_node.id]

        expected_invocations = ['create', 'start', 'stop', 'delete']
        self.assertListEqual(invocations, expected_invocations)

        # agent on host should have also
        # been stopped and uninstalled
        agent_data = self.get_plugin_data(
            plugin_name='agent',
            deployment_id=deployment.id
        )
        self.assertEqual(
            agent_data[webserver_node.host_id]['states'],
            ['created', 'configured', 'started',
             'stopped', 'deleted'])

    def test_deploy_with_operation_executor_override(self):
        dsl_path = get_resource('dsl/operation_executor_override.yaml')
        deployment, _ = self.deploy_application(dsl_path)
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

        expected_start_invocation = {'target': 'cloudify.management'}
        self.assertEqual(expected_start_invocation, start_invocation)

        agent_data = self.get_plugin_data(
            plugin_name='agent',
            deployment_id=deployment.id
        )

        # target_aware_mock_plugin should have been installed
        # on the management worker as well because 'start'
        # overrides the executor (with a local task)
        self.assertEqual(agent_data['local']['target_aware_mock_plugin'],
                         ['installed'])
        self.undeploy_application(deployment_id=deployment.id)

    def test_deployment_creation_workflow(self):
        dsl_path = get_resource(
            'dsl/basic_with_deployment_plugin_and_workflow_plugin.yaml'
        )
        deployment, _ = self.deploy_application(dsl_path)

        deployment_dir_path = os.path.join(
            '/opt/mgmtworker/work/deployments',
            DEFAULT_TENANT_NAME,
            deployment.id
        )

        self.execute_on_manager('test -d {0}'.format(deployment_dir_path))

        # assert plugin installer installed
        # the necessary plugins.
        agent_data = self.get_plugin_data(
            plugin_name='agent',
            deployment_id=deployment.id)

        # cloudmock and mock_workflows should have been installed
        # on the management worker as local tasks
        installed = ['installed']
        self.assertEqual(agent_data['local']['cloudmock'], installed)
        self.assertEqual(agent_data['local']['mock_workflows'], installed)

        self.undeploy_application(deployment.id, is_delete_deployment=True)

        # assert plugin installer uninstalled
        # the necessary plugins.
        self._assert_plugin_uninstalled(deployment)

        self.assertRaises(sh.ErrorReturnCode,
                          self.execute_on_manager,
                          'test -d {0}'.format(deployment_dir_path))

    @retrying.retry(wait_fixed=5000, stop_max_attempt_number=10)
    def _assert_plugin_uninstalled(self, deployment):
        agent_data = self.get_plugin_data(
                plugin_name='agent',
                deployment_id=deployment.id)
        uninstalled = ['installed', 'uninstalled']
        self.assertEqual(agent_data['local']['cloudmock'], uninstalled)
        self.assertEqual(agent_data['local']['mock_workflows'], uninstalled)

    def test_get_attribute(self):
        # assertion happens in operation get_attribute.tasks.assertion
        dsl_path = get_resource('dsl/get_attributes.yaml')
        deployment, _ = self.deploy_application(dsl_path)
        data = self.get_plugin_data(plugin_name='get_attribute',
                                    deployment_id=deployment.id)
        invocations = data['invocations']
        self.assertEqual(2, len([
            i for i in invocations
            if i == context.RELATIONSHIP_INSTANCE]))
        self.assertEqual(1, len([
            i for i in invocations
            if i == context.NODE_INSTANCE]))

    def test_riemann_core_started_with_policies(self):
        """A riemann core is started if the blueprint defines policies
        """
        dsl_path = get_resource('dsl/with_policies1.yaml')
        deployment, _ = self.deploy_application(dsl_path)

        self.assertTrue(self.is_riemann_core_up(deployment.id))

        self.undeploy_application(deployment.id, is_delete_deployment=True)

        self._assert_riemann_core_is_down(deployment)

    @retrying.retry(wait_fixed=5000, stop_max_attempt_number=10)
    def _assert_riemann_core_is_down(self, deployment):
        self.assertFalse(self.is_riemann_core_up(deployment.id))

    def test_riemann_core_not_started_without_policies(self):
        """A riemann core isn't started if there's no policies defined
        """
        dsl_path = get_resource('dsl/without_policies.yaml')
        deployment, _ = self.deploy_application(dsl_path)

        self.assertFalse(self.is_riemann_core_up(deployment.id))

        self.undeploy_application(deployment.id, is_delete_deployment=True)

        self._assert_riemann_core_is_down(deployment)
