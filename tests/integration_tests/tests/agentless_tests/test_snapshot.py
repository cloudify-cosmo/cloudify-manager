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
import tempfile
import requests
from collections import Counter

from integration_tests.framework import utils
from integration_tests import AgentlessTestCase
from cloudify_rest_client.executions import Execution
from cloudify_rest_client.exceptions import CloudifyClientError

SNAPSHOTS = 'http://cloudify-tests-files.s3-eu-west-1.amazonaws.com/snapshots/'


class TestSnapshot(AgentlessTestCase):
    SNAPSHOT_ID = '0'

    def test_4_0_0_snapshot_with_deployment(self):
        snapshot_path = self._get_snapshot('snap_4.0.0.zip')
        self._upload_and_restore_snapshot(snapshot_path)

        # Now make sure all the resources really exist in the DB
        self._assert_snapshot_restored(
            blueprint_id='blueprint',
            deployment_id='dep',
            node_ids=['http_web_server', 'vm'],
            node_instance_ids=['http_web_server_o0lqdi', 'vm_vvjuj8'],
            num_of_workflows=8,
            num_of_inputs=4,
            num_of_outputs=1,
            num_of_executions=1
        )

    def test_3_4_0_snapshot_with_deployment(self):
        snapshot_path = self._get_snapshot('snap_3.4.0.zip')
        tenant_name = 'tenant'
        self._upload_and_restore_snapshot(snapshot_path, tenant_name)

        # Now make sure all the resources really exist in the DB
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
        tenant_name = 'tenant'
        self._upload_and_restore_snapshot(snapshot_path, tenant_name)

        # Now make sure all the resources really exist in the DB
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
            tenant_name=tenant_name
        )

        self._assert_3_3_1_plugins_restored()

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
                                  tenant_name='default_tenant'):
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
            num_of_executions
        )
        self._assert_events_restored(execution_id, num_of_events)

        for node_id in node_ids:
            self.client.nodes.get(deployment_id, node_id)
        for node_instance_id in node_instance_ids:
            self.client.node_instances.get(node_instance_id)

    def _assert_3_3_1_plugins_restored(self):
        plugins = self.client.plugins.list()
        self.assertEqual(len(plugins), 8)
        package_names = [plugin.package_name for plugin in plugins]
        package_name_counts = Counter(package_names)
        self.assertEqual(package_name_counts['cloudify-openstack-plugin'], 1)
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
        deployments = self.client.deployments.list()
        self.assertEqual(1, len(deployments))
        deployment = deployments[0]
        self.assertEqual(deployment.id, deployment_id)
        self.assertEqual(len(deployment.workflows), num_of_workflows)
        self.assertEqual(deployment.blueprint_id, blueprint_id)
        self.assertEqual(deployment['permission'], 'creator')
        self.assertEqual(deployment['tenant_name'], tenant_name)
        self.assertEqual(len(deployment.inputs), num_of_inputs)
        self.assertEqual(len(deployment.outputs), num_of_outputs)

    def _assert_execution_restored(self,
                                   deployment_id,
                                   num_of_executions):
        def condition(execution):
            return execution.workflow_id == 'create_deployment_environment'

        executions = self.client.executions.list(deployment_id=deployment_id)
        self.assertEqual(len(executions), num_of_executions)
        executions = [execution for execution
                      in executions if condition(execution)]
        self.assertEqual(len(executions), 1)
        return executions[0].id

    def _assert_events_restored(self, execution_id, num_of_events):
        output = self.cfy.events.list(execution_id=execution_id)
        expected_output = 'Total events: {0}'.format(num_of_events)
        self.assertIn(expected_output, output)

    def _get_snapshot(self, name):
        snapshot_url = os.path.join(SNAPSHOTS, name)
        self.logger.info('Retrieving snapshot: {0}'.format(snapshot_url))
        response = requests.get(snapshot_url, stream=True)
        destination_file = tempfile.NamedTemporaryFile(delete=False)
        destination = destination_file.name
        with destination_file as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return destination

    def _upload_and_restore_snapshot(self, snapshot_path, tenant_name=None):
        """Upload the snapshot and launch the restore workflow
        """
        self._upload_and_validate_snapshot(snapshot_path)
        self.logger.debug('Restoring snapshot...')
        execution = self.client.snapshots.restore(
            self.SNAPSHOT_ID,
            tenant_name=tenant_name
        )
        execution = self._wait_for_execution_to_end(execution)
        if execution.status == Execution.FAILED:
            self.logger.error('Execution error: {0}'.format(execution.error))
        self.assertEqual(Execution.TERMINATED, execution.status)

    def _upload_and_validate_snapshot(self, snapshot_path):
        self.logger.debug('Uploading snapshot: {0}'.format(snapshot_path))
        self.client.snapshots.upload(snapshot_path, self.SNAPSHOT_ID)
        response = self.client.snapshots.list()
        self.assertEqual(1, len(response), 'expecting 1 snapshot results,'
                                           ' got {0}'.format(len(response)))
        snapshot = response[0]
        self.logger.debug('Retrieved snapshot: {0}'.format(snapshot))
        self.assertEquals(snapshot['id'], self.SNAPSHOT_ID)
        self.assertEquals(snapshot['status'], 'uploaded')

    def _wait_for_execution_to_end(self, execution, timeout_seconds=30):
        """Can't use the `wait_for_execution_to_end` in the class because
         we need to be able to handle client errors
        """
        deadline = time.time() + timeout_seconds
        while execution.status not in Execution.END_STATES:
            time.sleep(0.5)
            # This might fail due to the fact that we're changing the DB in
            # real time - it's OK. Just try again
            try:
                execution = self.client.executions.get(execution.id)
            except CloudifyClientError:
                pass
            if time.time() > deadline:
                raise utils.TimeoutException(
                        'Execution timed out: \n{0}'
                        .format(json.dumps(execution, indent=2)))
        return execution
