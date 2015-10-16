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
from testenv.utils import delete_provider_context
from testenv.utils import restore_provider_context
from manager_rest.blueprints_manager import \
    TRANSIENT_WORKERS_MODE_ENABLED_DEFAULT as IS_TRANSIENT_WORKERS_MODE


class TransientDeploymentWorkersTest(ProcessModeTestCase):

    def setUp(self):
        super(TransientDeploymentWorkersTest, self).setUp()
        delete_provider_context()
        self.addCleanup(restore_provider_context)

    def configure(self, transient_mode_enabled=True):
        context = {'cloudify': {
            'transient_deployment_workers_mode': {
                'enabled': transient_mode_enabled}}}
        self.client.manager.create_context(self._testMethodName, context)

    def test_basic_sanity(self):
        # despite the module/class name, this test tests the opposite of the
        # default mode, i.e. if transient workers mode is enabled by default,
        # this will test sanity in non transient workers mode, and vice versa
        self.configure(transient_mode_enabled=not IS_TRANSIENT_WORKERS_MODE)
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

        undeploy_application(deployment.id, is_delete_deployment=True)
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
