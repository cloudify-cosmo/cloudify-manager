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
import pytest
import tarfile
import tempfile
import subprocess
from contextlib import contextmanager

import retrying

from cloudify import constants
from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify_rest_client.executions import Execution

from integration_tests import AgentlessTestCase
from integration_tests.framework.utils import create_zip
from integration_tests.tests.utils import (get_resource,
                                           wait_for_blueprint_upload)

pytestmark = pytest.mark.group_workflows


class BasicWorkflowsTest(AgentlessTestCase):
    @pytest.mark.usefixtures('cloudmock_plugin')
    def test_execute_operation(self):
        dsl_path = get_resource('dsl/basic.yaml')
        blueprint_id = self.id()
        deployment, _ = self.deploy_application(
            dsl_path,
            blueprint_id=blueprint_id,
            timeout_seconds=30
        )
        self.assertEqual(blueprint_id, deployment.blueprint_id)
        ni = self.client.node_instances.list(node_id='webserver_host')[0]
        machines = ni.runtime_properties['machines']
        self.assertEqual(1, len(machines))

        outputs = self.client.deployments.outputs.get(deployment.id).outputs
        self.assertEqual(outputs['ip_address'], '')

    @pytest.mark.usefixtures('cloudmock_plugin')
    def test_restart_workflow(self):
        """Check that the restart workflow runs stop, and then start"""
        dsl_path = get_resource('dsl/basic.yaml')
        blueprint_id = self.id()
        deployment, _ = self.deploy_application(
            dsl_path,
            blueprint_id=blueprint_id,
            timeout_seconds=30
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

    @pytest.mark.usefixtures('cloudmock_plugin')
    def test_custom_workflow(self):
        dsl_path = get_resource('dsl/custom_workflow.yaml')
        blueprint_id = self.id()
        deployment, _ = self.deploy_application(
            dsl_path,
            blueprint_id=blueprint_id,
            timeout_seconds=30
        )
        self.execute_workflow('custom', deployment.id)
        instances = self.client.node_instances.list()
        assert all(i.runtime_properties.get('custom_workflow')
                   for i in instances)

    def test_custom_workflow_intrinsic_fn_params(self):
        self.client.secrets.create('my_secret', 's3cr3t')
        self.client.secrets.create('your_secret', 's3cr3t')
        dsl_path = get_resource('dsl/custom_workflow_with_intrinsic_fn.yaml')
        blueprint_id = self.id()
        deployment, _ = self.deploy_application(
            dsl_path,
            blueprint_id=blueprint_id,
            inputs={'a_blueprint_id': blueprint_id,
                    'a_secret_key': 'my_secret',
                    'a_string': 'foobar'},
            timeout_seconds=30
        )
        self.execute_workflow(
            'test_parameters',
            deployment.id,
            parameters={
                'secret_key': 'your_secret',
                'some_string': {'get_input': 'a_string'},
                'list_of_strings': [{'get_input': 'a_string'}, 'foo', 'bar']
            }
        )
        instances = self.client.node_instances.list()
        assert all(i.runtime_properties.get('tested') for i in instances)
        rp = instances[0].runtime_properties
        assert rp.get('blueprint_id') == blueprint_id
        assert rp.get('secret') == 's3cr3t'
        assert rp.get('secret_key') == 'your_secret'
        assert rp.get('some_string') == 'foobar'
        assert set(rp.get('list_of_strings')) == {'foobar', 'foo', 'bar'}

    @pytest.mark.usefixtures('testmockoperations_plugin')
    def test_dependencies_order_with_two_nodes(self):
        dsl_path = get_resource("dsl/dependencies_order_with_two_nodes.yaml")
        blueprint_id = self.id()
        deployment, _ = self.deploy_application(dsl_path,
                                                blueprint_id=blueprint_id)

        self.assertEqual(blueprint_id, deployment.blueprint_id)

        host_ni = self.client.node_instances.list(node_id='host_node')[0]
        db_ni = self.client.node_instances.list(node_id='db_node')[0]
        self.assertLess(host_ni.runtime_properties['time'],
                        db_ni.runtime_properties['time'])

    @pytest.mark.usefixtures('testmockoperations_plugin')
    def test_cloudify_runtime_properties_injection(self):
        dsl_path = get_resource("dsl/dependencies_order_with_two_nodes.yaml")
        deployment, _ = self.deploy_application(dsl_path)
        host_ni = self.client.node_instances.list(node_id='host_node')[0]
        node_runtime_props = host_ni.runtime_properties
        self.assertEqual('value1', node_runtime_props['property1'])

    @pytest.mark.usefixtures('testmockoperations_plugin')
    def test_non_existing_operation_exception(self):
        dsl_path = get_resource("dsl/wrong_operation_name.yaml")
        self.assertRaises(RuntimeError, self.deploy_application, dsl_path)

    @pytest.mark.usefixtures('testmockoperations_plugin')
    def test_inject_properties_to_operation(self):
        dsl_path = get_resource("dsl/hardcoded_operation_properties.yaml")
        deployment, _ = self.deploy_application(dsl_path)
        ni = self.client.node_instances.list(node_id='single_node')[0]
        invocations = ni.runtime_properties['mock_operation_invocation']
        self.assertEqual(1, len(invocations))
        invocation = invocations[0]
        self.assertEqual('mockpropvalue', invocation['mockprop'])
        self.assertEqual(ni.id, invocation['id'])

    @pytest.mark.usefixtures('testmockoperations_plugin')
    def test_start_monitor_node_operation(self):
        dsl_path = get_resource("dsl/hardcoded_operation_properties.yaml")
        deployment, _ = self.deploy_application(dsl_path)
        ni = self.client.node_instances.list(node_id='single_node')[0]
        invocations = ni.runtime_properties['monitoring_operations_invocation']
        self.assertEqual(1, len(invocations))
        invocation = invocations[0]
        self.assertEqual('start_monitor', invocation['operation'])

    @pytest.mark.usefixtures('testmockoperations_plugin')
    def test_plugin_get_resource(self):
        dsl_path = get_resource("dsl/get_resource_in_plugin.yaml")
        deployment, _ = self.deploy_application(dsl_path)
        ni = self.client.node_instances.list(node_id='single_node')[0]
        invocations = \
            ni.runtime_properties['get_resource_operation_invocation']
        self.assertEqual(1, len(invocations))
        invocation = invocations[0]
        with open(get_resource("dsl/basic.yaml")) as f:
            basic_data = f.read()

        # checking the resources are the correct data
        self.assertEqual(basic_data, invocation['res1_data'])
        self.assertEqual(basic_data, invocation['res2_data'])

        # checking the custom filepath provided is indeed where the second
        # resource was saved
        self.assertEqual(invocation['custom_filepath'],
                         invocation['res2_path'])

    @pytest.mark.usefixtures('cloudmock_plugin')
    def test_get_blueprint(self):
        dsl_path = get_resource("dsl/basic.yaml")
        blueprint_id = 'b{0}'.format(uuid.uuid4())
        deployment, _ = self.deploy_application(dsl_path,
                                                blueprint_id=blueprint_id)

        self.assertEqual(blueprint_id, deployment.blueprint_id)
        blueprint = self.client.blueprints.get(blueprint_id)
        self.assertEqual(blueprint_id, blueprint.id)
        self.assertTrue(len(blueprint['plan']) > 0)

    @pytest.mark.usefixtures('cloudmock_plugin')
    def test_publish_tar_archive(self):
        archive_location = self._make_archive_file("dsl/basic.yaml")

        blueprint_id = 'b{0}'.format(uuid.uuid4())
        self.client.blueprints.publish_archive(
            archive_location, blueprint_id, 'basic.yaml')
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

    @pytest.mark.usefixtures('cloudmock_plugin')
    def test_delete_blueprint(self):
        dsl_path = get_resource("dsl/basic.yaml")
        blueprint_id = 'b{0}'.format(uuid.uuid4())
        self.client.blueprints.upload(dsl_path, blueprint_id)
        wait_for_blueprint_upload(blueprint_id, self.client)
        # verifying blueprint exists
        result = self.client.blueprints.get(blueprint_id)
        self.assertEqual(blueprint_id, result.id)
        # deleting blueprint
        self.client.blueprints.delete(blueprint_id)
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

    @pytest.mark.usefixtures('cloudmock_plugin')
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
        wait_for_blueprint_upload(blueprint_id, self.client)
        self.client.deployments.create(blueprint_id, deployment_id,
                                       skip_plugins_validation=True)
        self.wait_for_deployment_environment(deployment_id)

        self.delete_deployment(deployment_id,
                               force=False,
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
                               'force flag was set to False'
                               .format(deployment_id),
                expect_in_error_message='live nodes'):
            self.delete_deployment(deployment_id)

        # deleting deployment - this time there's no execution running,
        # and using the force parameter to force deletion
        self.delete_deployment(deployment_id, True, validate=True)

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

    @pytest.mark.usefixtures('testmockoperations_plugin')
    def test_node_state_uninitialized(self):
        dsl_path = get_resource('dsl/node_states.yaml')
        _id = uuid.uuid1()
        blueprint_id = 'blueprint_{0}'.format(_id)
        deployment_id = 'deployment_{0}'.format(_id)
        self.client.blueprints.upload(dsl_path, blueprint_id)
        wait_for_blueprint_upload(blueprint_id, self.client)
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

    @pytest.mark.usefixtures('testmockoperations_plugin')
    def test_node_states(self):
        dsl_path = get_resource('dsl/node_states.yaml')
        _id = uuid.uuid1()
        blueprint_id = 'blueprint_{0}'.format(_id)
        deployment_id = 'deployment_{0}'.format(_id)
        deployment, _ = self.deploy_application(
            dsl_path,
            blueprint_id=blueprint_id,
            deployment_id=deployment_id)
        deployment_nodes = self.client.node_instances.list(
            deployment_id=deployment_id)
        self.assertEqual(1, len(deployment_nodes))
        node_id = deployment_nodes[0].id
        node_instance = self.client.node_instances.get(node_id)
        node_states = node_instance.runtime_properties['node_states']
        self.assertEqual(node_states, [
            'creating', 'configuring', 'starting'
        ])
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
            '/opt/manager/resources/deployments',
            'default_tenant',
            deployment.id
        )

    @staticmethod
    def _get_plugin_path(deployment):
        return os.path.join(
            '/opt/mgmtworker/env/source_plugins/',
            'default_tenant',
            deployment.id,
            'mock-plugin', '0.1',
            'lib/python3.11/site-packages/',
            'mock_plugin/ops.py'
        )

    def _assert_path_doesnt_exist_on_manager(self, path, directory=False):
        self.assertRaises(subprocess.CalledProcessError,
                          self._assert_path_exists_on_manager,
                          path, directory)

    def _assert_path_exists_on_manager(self, path, directory=False):
        flag = '-d' if directory else '-f'
        self.execute_on_manager('test {0} {1}'.format(flag, path))

    @pytest.mark.usefixtures('testmockoperations_plugin')
    @pytest.mark.usefixtures('get_attribute_plugin')
    def test_get_attribute(self):
        # assertion happens in operation get_attribute.tasks.assertion
        dsl_path = get_resource('dsl/get_attributes.yaml')
        deployment, _ = self.deploy_application(dsl_path)
        ni = self.client.node_instances.list(node_id='node1')[0]
        invocations = ni.runtime_properties['invocations']
        self.assertEqual(
            2, sum(i == constants.RELATIONSHIP_INSTANCE for i in invocations))
        self.assertEqual(
            1, sum(i == constants.NODE_INSTANCE for i in invocations))

    def test_workflows_availability_node_instances_state(self):
        bp_template = """
tosca_definitions_version: cloudify_dsl_1_4

imports:
    - cloudify/types/types.yaml

node_templates:
    node1:
        type: cloudify.nodes.Root
    node2:
        type: cloudify.nodes.Root
    node3:
        type: cloudify.nodes.Root

workflows:
    wf1:
        mapping: file:///dev/null
        availability_rules:
            node_instances_active: [none, all]
    wf2:
        mapping: file:///dev/null
        availability_rules:
            node_instances_active: [partial]
"""
        base_bp_path = self.make_yaml_file(bp_template)
        deployment, _ = self.deploy_application(base_bp_path)
        self.execute_workflow('wf1', deployment.id)
        with self.assertRaises(CloudifyClientError) as cm:
            self.execute_workflow('wf2', deployment.id)
        assert cm.exception.error_code == 'unavailable_workflow_error'

        node_instances = self.client.node_instances.list(
            deployment_id=deployment.id, _include=['id', 'state'])
        active_node_instance_ids = [ni['id'] for ni in node_instances
                                    if ni['state'] == 'started']
        self.client.node_instances.update(
            active_node_instance_ids[0], state='foo', force=True)

        with self.assertRaises(CloudifyClientError) as cm:
            self.execute_workflow('wf1', deployment.id)
        assert cm.exception.error_code == 'unavailable_workflow_error'
        self.execute_workflow('wf2', deployment.id)

    def test_workflows_availability_node_instances_state_partial(self):
        bp_template = """
    tosca_definitions_version: cloudify_dsl_1_4

    imports:
        - cloudify/types/types.yaml

    node_templates:
        node1:
            type: cloudify.nodes.Root
        node2:
            type: cloudify.nodes.Root

    workflows:
        wf1:
            mapping: file:///dev/null
            availability_rules:
                node_instances_active: [partial]
    """
        base_bp_path = self.make_yaml_file(bp_template)
        deployment, _ = self.deploy_application(base_bp_path)
        node_instances = self.client.node_instances.list(
            deployment_id=deployment.id, _include=['id', 'state'])
        active_node_instance_ids = [ni['id'] for ni in node_instances
                                    if ni['state'] == 'started']

        with self.assertRaises(CloudifyClientError) as cm:
            self.execute_workflow('wf1', deployment.id)
        assert cm.exception.error_code == 'unavailable_workflow_error'

        self.client.node_instances.update(
            active_node_instance_ids[0], state='stopped', force=True)
        self.execute_workflow('wf1', deployment.id)

        self.client.node_instances.update(
            active_node_instance_ids[0], state='uninitialized', force=True)
        self.execute_workflow('wf1', deployment.id)

        self.client.node_instances.update(
            active_node_instance_ids[1], state='stopped', force=True)
        self.execute_workflow('wf1', deployment.id)

        self.client.node_instances.update(
            active_node_instance_ids[1], state='uninitialized', force=True)
        with self.assertRaises(CloudifyClientError) as cm:
            self.execute_workflow('wf1', deployment.id)
        assert cm.exception.error_code == 'unavailable_workflow_error'

    def test_workflows_availability_node_types(self):
        bp_template = """
tosca_definitions_version: cloudify_dsl_1_4

imports:
    - cloudify/types/types.yaml

node_types:
    type1:
        derived_from: cloudify.nodes.Root
    type2:
        derived_from: type1
    type3:
        derived_from: type2

node_templates:
    node1:
        type: type1
    node2:
        type: type2

workflows:
    wf1:
        mapping: file:///dev/null
        availability_rules:
            node_types_required: []
    wf2:
        mapping: file:///dev/null
        availability_rules:
            node_types_required: [type1]
    wf3:
        mapping: file:///dev/null
        availability_rules:
            node_types_required: [type1, type2]
    wf4:
        mapping: file:///dev/null
        availability_rules:
            node_types_required: [type3]
"""
        base_bp_path = \
            self.make_yaml_file(bp_template)
        deployment, _ = self.deploy_application(base_bp_path)
        self.execute_workflow('wf1', deployment.id)
        self.execute_workflow('wf2', deployment.id)
        self.execute_workflow('wf3', deployment.id)
        with self.assertRaises(CloudifyClientError) as cm:
            self.execute_workflow('wf4', deployment.id)
        assert cm.exception.error_code == 'unavailable_workflow_error'

    def test_workflows_availability_compute_nodes(self):
        compute_bp = """
tosca_definitions_version: cloudify_dsl_1_4

imports:
    - cloudify/types/types.yaml

node_types:
    test_type:
        derived_from: cloudify.nodes.Compute

node_templates:
    node1:
        type: cloudify.nodes.Root
    node2:
        type: test_type
        properties:
            ip: localhost
            agent_config:
                install_method: none
"""
        no_compute_bp = """
tosca_definitions_version: cloudify_dsl_1_4

imports:
    - cloudify/types/types.yaml

node_templates:
    node1:
        type: cloudify.nodes.Root
"""
        compute_dep, _ = self.deploy_application(
            self.make_yaml_file(compute_bp)
        )
        workflows = [
            w.name
            for w in self.client.deployments.get(compute_dep.id).workflows
            if w.is_available
        ]
        assert 'validate_agents' in workflows
        assert 'install_new_agents' in workflows

        no_compute_dep, _ = self.deploy_application(
            self.make_yaml_file(no_compute_bp)
        )
        workflows = [
            w.name
            for w in self.client.deployments.get(no_compute_dep.id).workflows
            if w.is_available
        ]
        assert 'validate_agents' not in workflows
        assert 'install_new_agents' not in workflows
