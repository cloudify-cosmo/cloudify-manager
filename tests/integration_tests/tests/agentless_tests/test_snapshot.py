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
import time
import json
import requests
from collections import Counter

from integration_tests.framework import docl
from integration_tests.framework import utils
from integration_tests import AgentlessTestCase
from integration_tests.framework import postgresql

from cloudify.models_states import ExecutionState, AgentState
from manager_rest.constants import DEFAULT_TENANT_NAME, DEFAULT_TENANT_ROLE

from cloudify_rest_client.executions import Execution
from cloudify_rest_client.exceptions import CloudifyClientError

SNAPSHOTS = 'http://cloudify-tests-files.s3-eu-west-1.amazonaws.com/snapshots/'


class TestSnapshot(AgentlessTestCase):
    SNAPSHOT_ID = '0'
    REST_SEC_CONFIG_PATH = '/opt/manager/rest-security.conf'

    def setUp(self):
        super(TestSnapshot, self).setUp()
        self._save_security_config()
        self.addCleanup(self._restore_security_config)

    def test_v_4_snapshot_restore_validation(self):
        snapshot = self._get_snapshot('snap_4.0.0.zip')
        self.client.snapshots.upload(snapshot, self.SNAPSHOT_ID)
        username = 'username'
        password = 'password'
        self.client.users.create(username, password, role='sys_admin')
        self.client.tenants.add_user(username,
                                     DEFAULT_TENANT_NAME,
                                     DEFAULT_TENANT_ROLE)
        admin_client = utils.create_rest_client(username=username,
                                                password=password)
        self._try_restore_snapshot(
            snapshot_id=self.SNAPSHOT_ID,
            error_msg='Only the bootstrap admin is allowed '
                      'to perform this action',
            client=admin_client
        )

    def test_v_4_2_restore_validation_networks(self):
        snapshot = self._get_snapshot('snap_4.2.0_networks_validation.zip')
        self.client.snapshots.upload(snapshot, self.SNAPSHOT_ID)
        self._try_restore_snapshot(
            snapshot_id=self.SNAPSHOT_ID,
            error_msg="Networks `[u\'new_network\']` do not appear "
                      "in the provider context",
        )

    def _try_restore_snapshot(self,
                              snapshot_id,
                              error_msg,
                              tenant_name=None,
                              client=None):
        client = client or self.client
        execution = client.snapshots.restore(snapshot_id)
        try:
            self.wait_for_execution_to_end(execution)
        except RuntimeError, e:
            self.assertIn(error_msg, str(e))
        execution = client.executions.get(execution.id)
        self.assertEqual(execution.status, ExecutionState.FAILED)

    def test_4_4_snapshot_restore_with_bad_plugin_wgn_file(self):
        snapshot_path = \
            self._get_snapshot('snap_4_4_0_bad_plugin_wgn_file.zip')
        self._upload_and_restore_snapshot(
            snapshot_path,
            desired_execution_status=Execution.TERMINATED,
            error_execution_status=Execution.FAILED,
            ignore_plugin_failure=True)

        # Now make sure all the resources really exist in the DB
        # Assert snapshot restored
        self._assert_4_4_0_snapshot_restored_bad_plugin()

    def test_4_4_snapshot_restore_with_bad_plugin_no_directory(self):
        snapshot_path = \
            self._get_snapshot('snap_4_4_0_bad_plugin_no_directory.zip')
        self._upload_and_restore_snapshot(
            snapshot_path,
            desired_execution_status=Execution.TERMINATED,
            error_execution_status=Execution.FAILED,
            ignore_plugin_failure=True)

        # Now make sure all the resources really exist in the DB
        # Assert snapshot restored
        self._assert_4_4_0_snapshot_restored_bad_plugin()

    def test_4_4_snapshot_restore_with_bad_plugin_with_deps(self):
        snapshot_path = self._get_snapshot(
            'snap_4_4_0_bad_plugin_no_directory_with_deps.zip')
        self._upload_and_restore_snapshot(
            snapshot_path,
            desired_execution_status=Execution.TERMINATED,
            error_execution_status=Execution.FAILED,
            ignore_plugin_failure=True)

        # Now make sure all the resources really exist in the DB
        # Assert snapshot restored
        self._assert_4_4_0_snapshot_restored_bad_plugin(
            number_of_deployments=1)

    def test_4_4_snapshot_restore_with_bad_plugin_fails(self):
        snapshot_path = \
            self._get_snapshot('snap_4_4_0_bad_plugin_no_directory.zip')
        self._upload_and_restore_snapshot(
            snapshot_path,
            desired_execution_status=Execution.FAILED,
            error_execution_status=Execution.CANCELLED)

    def test_4_2_snapshot_with_deployment(self):
        snapshot_path = self._get_snapshot('snap_4.2.0.zip')
        self._upload_and_restore_snapshot(snapshot_path)

        # Now make sure all the resources really exist in the DB
        self._assert_snapshot_restored(
            blueprint_id='bp',
            deployment_id='dep',
            node_ids=['vm', 'http_web_server'],
            node_instance_ids=[
                'vm_monryi',
                'http_web_server_qxx9t0'
            ],
            num_of_workflows=7,
            num_of_inputs=4,
            num_of_outputs=1,
            num_of_executions=2,
            num_of_events=4,
        )

    def test_4_0_1_snapshot_with_deployment(self):
        """Restore a 4_0_1 snapshot with a deployment."""
        snapshot_path = self._get_snapshot('secretshot_4.0.1.zip')
        self._upload_and_restore_snapshot(snapshot_path)

        # Now make sure all the resources really exist in the DB
        self._assert_snapshot_restored(
            blueprint_id='t',
            deployment_id='t',
            node_ids=['vm1', 'vm2', 'some_sort_of_thing'],
            node_instance_ids=[
                'vm1_vj52lv',
                'vm2_pxra28',
                'some_sort_of_thing_papsns',
            ],
            num_of_workflows=7,
            num_of_inputs=3,
            num_of_outputs=0,
            num_of_executions=2,
            num_of_events=4,
        )

    def test_4_0_0_snapshot_with_deployment(self):
        snapshot_path = self._get_snapshot('snap_4.0.0.zip')
        self._upload_and_restore_snapshot(snapshot_path)

        # Now make sure all the resources really exist in the DB
        self._assert_snapshot_restored(
            blueprint_id='bp',
            deployment_id='dep',
            node_ids=['http_web_server', 'vm'],
            node_instance_ids=['http_web_server_qsmovz', 'vm_n19lu7'],
            num_of_workflows=7,
            num_of_inputs=4,
            num_of_outputs=1,
            num_of_executions=1,
            num_of_events=12,
        )

    def test_3_4_0_snapshot_with_deployment(self):
        snapshot_path = self._get_snapshot('snap_3.4.0.zip')
        self._upload_and_restore_snapshot(snapshot_path)
        # Now make sure all the resources really exist in the DB
        self._assert_3_4_0_snapshot_restored()

    def _assert_3_4_0_snapshot_restored(self,
                                        tenant_name=DEFAULT_TENANT_NAME):
        self._assert_snapshot_restored(
            blueprint_id='nodecellar',
            deployment_id='nodecellar',
            node_ids=['nodecellar', 'mongod', 'host', 'nodejs'],
            node_instance_ids=[
                'nodecellar_3e957',
                'mongod_983b4',
                'host_00747',
                'nodejs_35992'
            ],
            num_of_workflows=7,
            num_of_inputs=3,
            num_of_outputs=1,
            num_of_executions=7,
            tenant_name=tenant_name
        )

    def test_3_3_1_snapshot_with_plugin(self):
        snapshot_path = self._get_snapshot('snap_3.3.1_with_plugin.zip')
        self._upload_and_restore_snapshot(snapshot_path)

        # Now make sure all the resources really exist in the DB
        self._assert_3_3_1_snapshot_restored()
        self._assert_3_3_1_plugins_restored()

    def _assert_4_4_0_snapshot_restored_bad_plugin(
            self,
            tenant_name=DEFAULT_TENANT_NAME,
            number_of_deployments=0):
        self._assert_4_4_0_plugins_restored_bad_plugin(
            tenant_name=tenant_name,
            number_of_deployments=number_of_deployments
        )

    def _assert_3_3_1_snapshot_restored(self,
                                        tenant_name=DEFAULT_TENANT_NAME):
        self._assert_snapshot_restored(
            blueprint_id='hello-world-app',
            deployment_id='hello-world-app',
            node_ids=['security_group', 'vm', 'http_web_server', 'virtual_ip'],
            node_instance_ids=[
                'http_web_server_6dc13',
                'security_group_cc528',
                'virtual_ip_56b22',
                'vm_2d90e'
            ],
            num_of_workflows=6,
            num_of_inputs=4,
            num_of_outputs=1,
            num_of_executions=1,
            num_of_events=97,
            tenant_name=tenant_name,
        )

    def test_restore_2_snapshots(self):
        tenant_1_name = 'tenant_1'
        tenant_2_name = 'tenant_2'
        snapshot_1_id = 'snapshot_1'
        snapshot_2_id = 'snapshot_2'
        snapshot_1_path = self._get_snapshot('snap_3.4.0.zip')
        snapshot_2_path = self._get_snapshot('snap_3.3.1_with_plugin.zip')
        self.client.tenants.create(tenant_1_name)
        self.client.tenants.create(tenant_2_name)
        with self.client_using_tenant(self.client, tenant_1_name):
            self._upload_and_restore_snapshot(
                snapshot_1_path,
                tenant_1_name,
                snapshot_1_id,
            )
        with self.client_using_tenant(self.client, tenant_2_name):
            self._upload_and_restore_snapshot(
                snapshot_2_path,
                tenant_2_name,
                snapshot_2_id,
            )

        self._assert_3_4_0_snapshot_restored(tenant_1_name)
        self._assert_3_3_1_snapshot_restored(tenant_2_name)

    def test_v_4_1_1_restore_snapshot_with_private_resource(self):
        """
        Validate the conversion from the old column private_resource to
        the new column visibility
        """
        snapshot_path = self._get_snapshot('snap_4.1.1.zip')
        self._upload_and_restore_snapshot(snapshot_path)
        blueprints = self.client.blueprints.list(
            _include=['id', 'visibility'])
        assert (blueprints[0]['id'] == 'blueprint_1' and
                blueprints[0]['visibility'] == 'tenant')
        assert (blueprints[1]['id'] == 'blueprint_2' and
                blueprints[1]['visibility'] == 'private')
        assert (blueprints[2]['id'] == 'blueprint_3' and
                blueprints[2]['visibility'] == 'private')

    def test_v_4_2_restore_snapshot_with_resource_availability(self):
        """
        Validate the conversion from the old column resource_availability to
        the new column visibility
        """
        snapshot_name = 'snap_4.2.0_visibility_validation.zip'
        snapshot_path = self._get_snapshot(snapshot_name)
        self._upload_and_restore_snapshot(snapshot_path)
        blueprints = self.client.blueprints.list(
            _include=['id', 'visibility'])
        assert (blueprints[0]['id'] == 'blueprint_1' and
                blueprints[0]['visibility'] == 'private')
        assert (blueprints[1]['id'] == 'blueprint_2' and
                blueprints[1]['visibility'] == 'tenant')
        assert (blueprints[2]['id'] == 'blueprint_3' and
                blueprints[2]['visibility'] == 'global')

    def test_v_4_3_restore_snapshot_with_secrets(self):
        """
        Validate the encryption of the secrets values for versions before 4.4.0
        """
        self._test_secrets_restored('snap_4.3.0_with_secrets.zip')

        # The secret's value is not hidden
        second_secret = self.client.secrets.get('sec2')
        assert second_secret.value == 'top_secret2'
        assert not second_secret.is_hidden_value

    def test_v_4_4_restore_snapshot_with_secrets(self):
        """
        Validate the restore of the secrets values for snapshot of 4.4.0
        """
        self._test_secrets_restored('snap_4.4.0_with_secrets.zip')

        # The secret's value is hidden
        second_secret = self.client.secrets.get('sec2')
        assert second_secret.value == 'top_secret2'
        assert second_secret.is_hidden_value

    def test_v_4_5_restore_snapshot_with_agents(self):
        """
        Validate the restore of agents
        """
        agents = self.client.agents.list()
        assert len(agents) == 0
        snapshot_path = self._get_snapshot('snap_4.5.0_with_agents.zip')
        self._upload_and_restore_snapshot(snapshot_path)
        agents = self.client.agents.list()
        self.assertEqual(len(agents), 3)
        first_agent = self.client.agents.get(agents[0].id)
        self.assertEqual(first_agent.state, AgentState.RESTORED)
        self.assertEqual(first_agent.rabbitmq_exchange, agents[0].id)
        self.assertIsNone(first_agent.rabbitmq_username)

    def test_v_4_5_restore_snapshot_with_without_imported_blueprints(self):
        """
        Validate deletion protection against imported blueprints is not applied
        to blueprints from 4.5.0 version down.
        """
        snapshot_path = self._get_snapshot('snap_4.5.0_with_blueprint.zip')
        # This snapshot only contain one blueprint.
        self._upload_and_restore_snapshot(snapshot_path)
        blueprints = self.client.blueprints.list(_include=['id'])
        self.client.blueprints.delete(blueprints[0]['id'])
        self.assertEqual(0,
                         len(self.client.blueprints.list(_include=['id'])))

    def _test_secrets_restored(self, snapshot_name):
        snapshot_path = self._get_snapshot(snapshot_name)
        self._upload_and_restore_snapshot(snapshot_path)

        # The secrets values as in the snapshot
        secrets = self.client.secrets.list(_include=['key'])
        assert len(secrets) == 3
        secret_string = self.client.secrets.get('sec1')
        secret_file = self.client.secrets.get('sec3')
        assert secret_string.value == 'top_secret'
        assert 'test_mail' in secret_file.value

        # Validate the value is encrypted in the DB
        result = postgresql.run_query("SELECT value "
                                      "FROM secrets "
                                      "WHERE id='sec1';")
        secret_encrypted = result['all'][0][0]
        assert secret_encrypted != 'top_secret'

        # The secrets values are not hidden
        assert (not secret_string.is_hidden_value and
                not secret_file.is_hidden_value)

    def _assert_snapshot_restored(self,
                                  blueprint_id,
                                  deployment_id,
                                  node_ids,
                                  node_instance_ids,
                                  num_of_workflows,
                                  num_of_inputs,
                                  num_of_outputs,
                                  num_of_executions,
                                  num_of_events=4,
                                  tenant_name=DEFAULT_TENANT_NAME):
        with self.client_using_tenant(self.client, tenant_name):
            self.client.blueprints.get(blueprint_id)
        self._assert_deployment_restored(
            blueprint_id=blueprint_id,
            deployment_id=deployment_id,
            num_of_workflows=num_of_workflows,
            num_of_inputs=num_of_inputs,
            num_of_outputs=num_of_outputs,
            tenant_name=tenant_name
        )

        execution_id = self._assert_execution_restored(
            deployment_id,
            num_of_executions,
            tenant_name,
        )
        self._assert_events_restored(
            execution_id,
            num_of_events,
            tenant_name,
        )

        with self.client_using_tenant(self.client, tenant_name):
            for node_id in node_ids:
                self.client.nodes.get(deployment_id, node_id)
            for node_instance_id in node_instance_ids:
                self.client.node_instances.get(node_instance_id)

    def _assert_3_3_1_plugins_restored(self, tenant_name=DEFAULT_TENANT_NAME):
        with self.client_using_tenant(self.client, tenant_name):
            plugins = self.client.plugins.list()
        self.assertEqual(len(plugins), 8)
        package_names = [plugin.package_name for plugin in plugins]
        package_name_counts = Counter(package_names)
        self.assertEqual(package_name_counts['cloudify-openstack-plugin'], 1)
        self.assertEqual(package_name_counts['cloudify-fabric-plugin'], 1)
        self.assertEqual(package_name_counts['cloudify-script-plugin'], 1)
        self.assertEqual(package_name_counts['cloudify-diamond-plugin'], 5)

    def _assert_4_4_0_plugins_restored_bad_plugin(
            self,
            tenant_name=DEFAULT_TENANT_NAME,
            number_of_deployments=0):
        """
        Validate only 7 of the 8 plugins in the snapshot are being restored.
        Also, validating all deployments exist
        """
        with self.client_using_tenant(self.client, tenant_name):
            plugins = self.client.plugins.list()
            deployments = self.client.deployments.list()
        self.assertEqual(len(plugins), 7)
        self.assertEqual(len(deployments), number_of_deployments)
        package_names = [plugin.package_name for plugin in plugins]
        package_name_counts = Counter(package_names)
        self.assertEqual(package_name_counts['cloudify-fabric-plugin'], 1)
        self.assertEqual(package_name_counts['cloudify-script-plugin'], 1)
        self.assertEqual(package_name_counts['cloudify-diamond-plugin'], 5)

    def _assert_deployment_restored(self,
                                    blueprint_id,
                                    deployment_id,
                                    num_of_workflows,
                                    num_of_inputs,
                                    num_of_outputs,
                                    tenant_name):
        with self.client_using_tenant(self.client, tenant_name):
            deployment = self.client.deployments.get(deployment_id)
        self.assertEqual(deployment.id, deployment_id)
        self.assertEqual(len(deployment.workflows), num_of_workflows)
        self.assertEqual(deployment.blueprint_id, blueprint_id)
        self.assertEqual(deployment.created_by, 'admin')
        self.assertEqual(deployment['tenant_name'], tenant_name)
        self.assertEqual(len(deployment.inputs), num_of_inputs)
        self.assertEqual(len(deployment.outputs), num_of_outputs)

    def _assert_execution_restored(self,
                                   deployment_id,
                                   num_of_executions,
                                   tenant_name):
        def condition(execution):
            return execution.workflow_id == 'create_deployment_environment'

        with self.client_using_tenant(self.client, tenant_name):
            executions = self.client.executions.list(
                deployment_id=deployment_id
            )

        self.assertEqual(len(executions), num_of_executions)
        executions = [execution for execution
                      in executions if condition(execution)]
        self.assertEqual(len(executions), 1)
        return executions[0].id

    def _assert_events_restored(self,
                                execution_id,
                                num_of_events,
                                tenant_name):
        output = self.cfy.events.list(
            execution_id=execution_id,
            tenant_name=tenant_name
        )
        expected_output = 'Showing {0} of {0} events'.format(num_of_events)
        self.assertIn(expected_output, output)

    def _get_snapshot(self, name):
        snapshot_url = os.path.join(SNAPSHOTS, name)
        self.logger.info('Retrieving snapshot: {0}'.format(snapshot_url))
        tmp_file = os.path.join(self.workdir, name)
        return utils.download_file(snapshot_url, tmp_file)

    def _upload_and_restore_snapshot(
            self,
            snapshot_path,
            tenant_name=DEFAULT_TENANT_NAME,
            snapshot_id=None,
            desired_execution_status=Execution.TERMINATED,
            error_execution_status=Execution.FAILED,
            ignore_plugin_failure=False):
        """Upload the snapshot and launch the restore workflow
        """
        snapshot_id = snapshot_id or self.SNAPSHOT_ID
        rest_client = utils.create_rest_client(tenant=tenant_name)
        self._upload_and_validate_snapshot(snapshot_path,
                                           snapshot_id,
                                           rest_client)
        self.logger.debug('Restoring snapshot...')
        execution = rest_client.snapshots.restore(
            snapshot_id,
            ignore_plugin_failure=ignore_plugin_failure)
        execution = self._wait_for_restore_execution_to_end(
            execution, rest_client)
        if execution.status == error_execution_status:
            self.logger.error('Execution error: {0}'.format(execution.error))
        self.assertEqual(desired_execution_status, execution.status)

    def _upload_and_validate_snapshot(self,
                                      snapshot_path,
                                      snapshot_id,
                                      rest_client):
        self.logger.debug('Uploading snapshot: {0}'.format(snapshot_path))
        rest_client.snapshots.upload(snapshot_path, snapshot_id)
        snapshot = rest_client.snapshots.get(snapshot_id)
        self.logger.debug('Retrieved snapshot: {0}'.format(snapshot))
        self.assertEquals(snapshot['id'], snapshot_id)
        self.assertEquals(snapshot['status'], 'uploaded')
        self.logger.info('Snapshot uploaded and validated')

    def _wait_for_restore_execution_to_end(
            self, execution, rest_client, timeout_seconds=70):
        """Can't use the `wait_for_execution_to_end` in the class because
         we need to be able to handle client errors
        """
        deadline = time.time() + timeout_seconds
        while execution.status not in Execution.END_STATES:
            time.sleep(0.5)
            # This might fail due to the fact that we're changing the DB in
            # real time - it's OK. Just try again
            try:
                execution = rest_client.executions.get(execution.id)
            except (requests.exceptions.ConnectionError, CloudifyClientError):
                pass
            if time.time() > deadline:
                raise utils.TimeoutException(
                    'Execution timed out: \n{0}'.format(
                        json.dumps(execution, indent=2)
                    )
                )
        return execution

    def _save_security_config(self):
        tmp_config_path = os.path.join(self.workdir, 'rest-security.conf')
        docl.copy_file_from_manager(self.REST_SEC_CONFIG_PATH, tmp_config_path)

    def _restore_security_config(self):
        tmp_config_path = os.path.join(self.workdir, 'rest-security.conf')
        docl.copy_file_to_manager(tmp_config_path,
                                  self.REST_SEC_CONFIG_PATH)
        docl.execute('chown cfyuser: {securityconf}'.format(
            securityconf=self.REST_SEC_CONFIG_PATH,
        ))
        self.restart_service('cloudify-restservice')
