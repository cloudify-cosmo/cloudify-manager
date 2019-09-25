########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
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

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource


class TestRuntimeFunctionEvaluation(AgentlessTestCase):
    """Tests for the runtime_only_evaluation feature.

    Those tests will run a workflow which will gather values from various
    sources (node properties, operation inputs) into runtime properties,
    which allows us to do assertions on the runtime properties.
    """
    BASE_VALUE = 'aaa'
    CHANGED_VALUE = 'bbb'

    def setUp(self):
        super(TestRuntimeFunctionEvaluation, self).setUp()
        self.bp_path = resource('dsl/deployment_update_functions.yaml')

    def _assert_properties(self, deployment, value):
        instances_node1 = self.client.node_instances.list(
            node_id='node1', deployment_id=deployment.id)
        self.assertEqual(len(instances_node1), 1)
        instances_node2 = self.client.node_instances.list(
            node_id='node2', deployment_id=deployment.id)
        ni1 = instances_node1[0]
        ni2 = instances_node2[0]

        outputs = self.client.deployments.outputs.get(deployment.id)['outputs']
        self.assertEqual(outputs['out1'], value)
        self.assertEqual(outputs['out2'], value)
        self.assertEqual(outputs['out3'], value)
        self.assertEqual(ni1.runtime_properties['arg_value'], value)
        self.assertEqual(ni1.runtime_properties['prop1_value'], value)
        self.assertEqual(ni1.runtime_properties['prop2_value'], value)
        self.assertEqual(ni1.runtime_properties['source_input_value'], value)
        self.assertEqual(ni1.runtime_properties['target_input_value'], value)
        self.assertEqual(ni2.runtime_properties['source_input_value'], value)
        self.assertEqual(ni2.runtime_properties['target_input_value'], value)
        self.assertEqual(ni1.runtime_properties['source_prop_value'], value)
        self.assertEqual(ni2.runtime_properties['target_prop_value'], value)

    def _manual_deployment_update(self, deployment):
        """Sneakily update the deployment, without running deployment update.

        This is mocking out the deployment update procedure for the purposes
        of this test.

        This will allow us to simply rerun a workflow without explicitly
        updating it, which allows to check that the new workflow run will
        use the updated values just because of them having been changed,
        not because of what deployment update does.
        """
        update_script = resource('scripts/update_deployment.py')
        self.copy_file_to_manager(update_script, '/tmp/update_deployment.py')

        self.execute_on_manager(
            '/opt/manager/env/bin/python /tmp/update_deployment.py '
            '--deployment-id {0}'
            .format(deployment.id))

    def _update_deployment(self, deployment, skip=False):
        new_bp_path = os.path.join(
            os.path.dirname(self.bp_path),
            'altered_deployment_update_functions.yaml'
        )
        self.addCleanup(os.unlink, new_bp_path)
        with open(self.bp_path) as bp, open(new_bp_path, 'w') as new_bp:
            bp_content = bp.read()
            bp_content = bp_content.replace(
                "prop2: '{0}'".format(self.BASE_VALUE),
                "prop2: '{0}'".format(self.CHANGED_VALUE))
            new_bp.write(bp_content)

        skip_params = {}
        if skip:
            skip_params = {
                'skip_install': True,
                'skip_uninstall': True,
                'skip_reinstall': True,
            }
        dep_update = self.client.deployment_updates.update(
            deployment_id=deployment.id,
            blueprint_or_archive_path=new_bp.name,
            runtime_only_evaluation=True,
            inputs={'input1': self.CHANGED_VALUE, 'fail_create': False},
            **skip_params
        )
        execution = self.client.executions.get(dep_update.execution_id)
        self.wait_for_execution_to_end(execution)
        dep_update = self.client.deployment_updates.finalize_commit(
            dep_update.id)

    def test_manual_update_new_workflow(self):
        deployment = self.deploy(
            self.bp_path,
            inputs={'input1': self.BASE_VALUE},
            runtime_only_evaluation=True)
        self.execute_workflow('install', deployment.id)
        self._assert_properties(deployment, self.BASE_VALUE)
        self._manual_deployment_update(deployment)
        self.execute_workflow('install', deployment.id)
        self._assert_properties(deployment, self.CHANGED_VALUE)

    def test_manual_update_resume(self):
        deployment = self.deploy(
            self.bp_path,
            inputs={'input1': self.BASE_VALUE, 'fail_create': True},
            runtime_only_evaluation=True)
        install_execution = self.execute_workflow(
            'install', deployment.id, wait_for_execution=False)
        try:
            self.wait_for_execution_to_end(install_execution)
        except RuntimeError:
            pass
        else:
            self.fail('Expected execution {0} to fail'
                      .format(install_execution))
        self._manual_deployment_update(deployment)
        self.client.executions.resume(install_execution.id)
        self.wait_for_execution_to_end(install_execution)
        self._assert_properties(deployment, self.CHANGED_VALUE)

    def test_deployment_update_new_workflow(self):
        deployment = self.deploy(
            self.bp_path,
            inputs={'input1': self.BASE_VALUE},
            runtime_only_evaluation=True)

        self.execute_workflow('install', deployment.id)
        self._assert_properties(deployment, self.BASE_VALUE)
        self._update_deployment(deployment)
        self._assert_properties(deployment, self.CHANGED_VALUE)

    def test_deployment_update_resume(self):
        deployment = self.deploy(
            self.bp_path,
            inputs={'input1': self.BASE_VALUE, 'fail_create': True},
            runtime_only_evaluation=True)
        install_execution = self.execute_workflow(
            'install', deployment.id, wait_for_execution=False)
        try:
            self.wait_for_execution_to_end(install_execution)
        except RuntimeError:
            pass
        else:
            self.fail('Expected execution {0} to fail'
                      .format(install_execution))

        self._update_deployment(deployment, skip=True)
        self.client.executions.resume(install_execution.id)
        self.wait_for_execution_to_end(install_execution)
        self._assert_properties(deployment, self.CHANGED_VALUE)

    def test_change_flag_update(self):
        deployment = self.deploy(
            self.bp_path,
            inputs={'input1': self.BASE_VALUE},
            runtime_only_evaluation=False)
        self.assertFalse(deployment.runtime_only_evaluation)
        self.execute_workflow('install', deployment.id)
        self._assert_properties(deployment, self.BASE_VALUE)
        self._update_deployment(deployment)
        self._assert_properties(deployment, self.CHANGED_VALUE)

        dep = self.client.deployments.get(deployment.id)
        self.assertTrue(dep.runtime_only_evaluation)

    def test_change_flag_update_resume(self):
        deployment = self.deploy(
            self.bp_path,
            inputs={'input1': self.BASE_VALUE, 'fail_create': True},
            runtime_only_evaluation=False)
        self.assertFalse(deployment.runtime_only_evaluation)
        install_execution = self.execute_workflow(
            'install', deployment.id, wait_for_execution=False)
        try:
            self.wait_for_execution_to_end(install_execution)
        except RuntimeError:
            pass
        else:
            self.fail('Expected execution {0} to fail'
                      .format(install_execution))

        self._update_deployment(
            deployment, update_executions=[install_execution.id])
        self.client.executions.resume(install_execution.id)
        self.wait_for_execution_to_end(install_execution)
        self._assert_properties(deployment, self.CHANGED_VALUE)

        dep = self.client.deployments.get(deployment.id)
        self.assertTrue(dep.runtime_only_evaluation)
