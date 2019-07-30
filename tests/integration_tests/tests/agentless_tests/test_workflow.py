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
import re
import time
import uuid
import shutil
import tarfile
import tempfile
from contextlib import contextmanager

import sh
import retrying

from cloudify import constants
from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify_rest_client.executions import Execution

from integration_tests import AgentlessTestCase
from integration_tests.framework.utils import timeout, create_zip
from integration_tests.tests.utils import (
    get_resource,
    do_retries,
    verify_deployment_env_created
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

    def test_restart_workflow(self):
        """Check that the restart workflow runs stop, and then start"""
        dsl_path = get_resource('dsl/basic.yaml')
        blueprint_id = self.id()
        deployment, _ = self.deploy_application(
            dsl_path,
            blueprint_id=blueprint_id,
            timeout_seconds=15
        )
        execution = self.execute_workflow('restart', deployment.id)
        # event storing is async, allow some time for them to be stored
        time.sleep(2)
        events = self.client.events.list(
            execution_id=execution.id, include_logs=True)

        # check that the expected logs exist - and that they're
        # in the correct order
        seen_logs = [event['message'] for event in events
                     if re.match('stopping|starting', event['message'])]
        self.assertEqual(len(seen_logs), 2)
        self.assertIn('stopping machine', seen_logs[0])
        self.assertIn('starting machine', seen_logs[1])

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
        deployment_id = 'd{0}'.format(uuid.uuid4())
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
        blueprint_id = 'b{0}'.format(uuid.uuid4())
        deployment, _ = self.deploy_application(dsl_path,
                                                blueprint_id=blueprint_id)

        self.assertEqual(blueprint_id, deployment.blueprint_id)
        blueprint = self.client.blueprints.get(blueprint_id)
        self.assertEqual(blueprint_id, blueprint.id)
        self.assertTrue(len(blueprint['plan']) > 0)

    def test_publish_tar_archive(self):
        archive_location = self._make_archive_file("dsl/basic.yaml")

        blueprint_id = self.client.blueprints.publish_archive(
            archive_location, 'b{0}'.format(uuid.uuid4()), 'basic.yaml').id
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
            dsl_path, 'b{0}'.format(uuid.uuid4())).id

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
        deployment_id = 'd{0}'.format(uuid.uuid4())

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
        do_retries(verify_deployment_env_created,
                   timeout_seconds=60,
                   deployment_id=deployment_id)

        self.delete_deployment(deployment_id,
                               ignore_live_nodes=False,
                               validate=True)
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
        deleted_deployment_id = self.delete_deployment(
            deployment_id, True, validate=True).id
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

    def test_deployment_create_workflow_and_source_plugin(self):
        # Get the whole directory
        dsl_path = get_resource('dsl/plugin_tests')

        # Copy the blueprint folder into a temp dir, because we want to
        # create a plugin zip, in order to install it from source
        base_temp_dir = tempfile.mkdtemp()
        blueprint_dir = os.path.join(base_temp_dir, 'blueprint')
        shutil.copytree(dsl_path, blueprint_dir)

        blueprint_path = os.path.join(blueprint_dir, 'source_plugin.yaml')

        # Create a zip archive of the
        source_plugin = os.path.join(
            blueprint_dir, 'plugins', 'mock-plugin'
        )
        plugin_zip = '{0}.zip'.format(source_plugin)

        try:
            create_zip(source_plugin, plugin_zip)

            deployment, _ = self.deploy_application(blueprint_path)
            deployment_folder = self._get_deployment_folder(deployment)
            plugin_path = self._get_plugin_path(deployment)

            # assert plugin installer installed the necessary plugin
            self._assert_path_exists_on_manager(deployment_folder, True)
            self._assert_path_exists_on_manager(plugin_path)

            self.undeploy_application(deployment.id, is_delete_deployment=True)

            # Retry several times, because uninstalling plugins may take time
            self._assert_paths_removed(deployment_folder, plugin_path)

        finally:
            shutil.rmtree(base_temp_dir)

    @retrying.retry(wait_fixed=5000, stop_max_attempt_number=10)
    def _assert_paths_removed(self, deployment_folder, plugin_path):
        # assert plugin installer uninstalled the necessary plugin
        self._assert_path_doesnt_exist_on_manager(deployment_folder, True)
        self._assert_path_doesnt_exist_on_manager(plugin_path)

    @staticmethod
    def _get_deployment_folder(deployment):
        return os.path.join(
            '/opt/mgmtworker/work/deployments',
            DEFAULT_TENANT_NAME,
            deployment.id
        )

    @staticmethod
    def _get_plugin_path(deployment):
        return os.path.join(
            '/opt/mgmtworker/env/plugins/',
            DEFAULT_TENANT_NAME,
            '{0}-plugin1'.format(deployment.id),
            'lib/python2.7/site-packages/',
            'mock_plugin/ops.py'
        )

    def _assert_path_doesnt_exist_on_manager(self, path, directory=False):
        self.assertRaises(sh.ErrorReturnCode,
                          self._assert_path_exists_on_manager,
                          path, directory)

    def _assert_path_exists_on_manager(self, path, directory=False):
        flag = '-d' if directory else '-f'
        self.execute_on_manager('test {0} {1}'.format(flag, path))

    def test_get_attribute(self):
        # assertion happens in operation get_attribute.tasks.assertion
        dsl_path = get_resource('dsl/get_attributes.yaml')
        deployment, _ = self.deploy_application(dsl_path)
        data = self.get_plugin_data(plugin_name='get_attribute',
                                    deployment_id=deployment.id)
        invocations = data['invocations']
        self.assertEqual(2, len([
            i for i in invocations
            if i == constants.RELATIONSHIP_INSTANCE]))
        self.assertEqual(1, len([
            i for i in invocations
            if i == constants.NODE_INSTANCE]))
