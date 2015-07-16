########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
############

from testenv import ProcessModeTestCase
from testenv.utils import get_resource
from testenv.utils import deploy_application
from testenv.utils import undeploy_application
from testenv.utils import wait_for_execution_to_end
from testenv.utils import delete_provider_context
from testenv.utils import restore_provider_context
from cloudify_rest_client.executions import Execution


class TransientDeploymentWorkersTest(ProcessModeTestCase):

    def setUp(self):
        super(TransientDeploymentWorkersTest, self).setUp()
        delete_provider_context()
        self.addCleanup(restore_provider_context)

    def configure(self):
        context = {'cloudify': {
            'transient_deployment_workers_mode': {
                'enabled': True}}}
        self.client.manager.create_context(self._testMethodName, context)

    def test_basic_sanity(self):
        self.configure()
        dsl_path = get_resource('dsl/basic.yaml')
        blueprint_id = self.id()
        deployment, _ = deploy_application(
            dsl_path,
            blueprint_id=blueprint_id,
            timeout_seconds=30)

        self.assertEqual(blueprint_id, deployment.blueprint_id)

        machines = self.get_plugin_data(
            plugin_name='cloudmock',
            deployment_id=deployment.id
        )['machines']
        self.assertEquals(1, len(machines))

        outputs = self.client.deployments.outputs.get(deployment.id).outputs
        # ip runtime property is not set in this case
        self.assertEquals(outputs['ip_address'], '')

        self._wait_for_stop_dep_env_execution_to_end(deployment.id)
        undeploy_application(deployment.id, delete_deployment=True)
        deployments = self.client.deployments.list()
        self.assertEqual(0, len(deployments))

    def test_system_workflows_execution(self):
        self.configure()
        dsl_path = get_resource('dsl/basic.yaml')
        bp_and_dep_id = self.id()
        deployment, _ = deploy_application(
            dsl_path,
            blueprint_id=bp_and_dep_id,
            deployment_id=bp_and_dep_id,
            timeout_seconds=30)

        executions = self.client.executions.list(include_system_workflows=True)
        executions.sort(key=lambda e: e.created_at)

        # expecting 4 executions: deployment environment creation,
        # deployment environment start, install workflow, and
        # deployment environment stop
        self.assertEquals(4, len(executions))
        self.assertEquals('create_deployment_environment',
                          executions[0].workflow_id)
        self.assertEquals('_start_deployment_environment',
                          executions[1].workflow_id)
        self.assertEquals('install',
                          executions[2].workflow_id)
        self.assertEquals('_stop_deployment_environment',
                          executions[3].workflow_id)
        self.assertEqual([executions[1], executions[3]],
                         [e for e in executions if e.is_system_workflow])

        self._wait_for_stop_dep_env_execution_to_end(deployment.id)
        undeploy_application(bp_and_dep_id)

        executions = self.client.executions.list(include_system_workflows=True)
        executions.sort(key=lambda e: e.created_at)

        # expecting 7 executions, the last 3 being deployment environment
        # start, uninstall workflow, and deployment environment stop
        self.assertEquals(7, len(executions))
        self.assertEquals('_start_deployment_environment',
                          executions[4].workflow_id)
        self.assertEquals('uninstall',
                          executions[5].workflow_id)
        self.assertEquals('_stop_deployment_environment',
                          executions[6].workflow_id)
        self.assertEqual([executions[1], executions[3], executions[4],
                          executions[6]],
                         [e for e in executions if e.is_system_workflow])

    def _wait_for_stop_dep_env_execution_to_end(self, deployment_id,
                                                timeout_seconds=240):
        executions = self.client.executions.list(deployment_id=deployment_id,
                                                 include_system_workflows=True)
        running_stop_executions = [e for e in executions if e.workflow_id ==
                                   '_stop_deployment_environment' and
                                   e.status not in Execution.END_STATES]

        if not running_stop_executions:
            return

        if len(running_stop_executions) > 1:
            raise RuntimeError('There is more than one running '
                               '"_stop_deployment_environment" execution: {0}'
                               .format(running_stop_executions))

        execution = running_stop_executions[0]
        return wait_for_execution_to_end(execution, timeout_seconds)
