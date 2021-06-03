# Copyright (c) 2019-2020 Cloudify Platform Ltd. All rights reserved
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
import pytest

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource
from integration_tests.tests.utils import wait_for_blueprint_upload

pytestmark = pytest.mark.group_service_composition


@pytest.mark.usefixtures('mock_workflows_plugin')
class TestRelationshipRunningRemoteWorkflow(AgentlessTestCase):
    shared_resource_blueprint = """
tosca_definitions_version: cloudify_dsl_1_3

imports:
    - cloudify/types/types.yaml
    - wf--blueprint:mock_workflows

workflows:
    test_wf:
        mapping: wf--mock_workflows.mock_workflows.workflows.do_nothing
    failing:
        mapping: wf--mock_workflows.mock_workflows.workflows.non_recoverable

capabilities:
    test:
        value: 1
"""

    def setUp(self):
        super(TestRelationshipRunningRemoteWorkflow, self).setUp()
        self.client.blueprints.upload(
            resource('dsl/mock_workflows.yaml'),
            entity_id='mock_workflows')
        wait_for_blueprint_upload('mock_workflows', self.client)
        self._create_shared_resource_deployment()

    @staticmethod
    def _generate_app_blueprint(relationship_type, wf_id='test_wf'):
        return """
tosca_definitions_version: cloudify_dsl_1_3

imports:
  - cloudify/types/types.yaml

node_templates:
  shared_resource_node:
    type: cloudify.nodes.SharedResource
    properties:
      resource_config:
        deployment:
            id: test

  app:
    type: cloudify.nodes.Root
    relationships:
      - type: {0}
        target: shared_resource_node
        target_interfaces:
            cloudify.interfaces.relationship_lifecycle:
                establish:
                    inputs:
                        workflow_id: {1}
""".format(relationship_type, wf_id) + """
                        parameters: {t: 1}
                unlink:
                    inputs:
                        workflow_id: test_wf
                        parameters: {t: 1}
"""

    def _create_shared_resource_deployment(self):
        blueprint_path = self.make_yaml_file(self.shared_resource_blueprint)
        self.deploy(blueprint_path, deployment_id='test')

    def _validate_shared_resource_capabilities(self,
                                               deployment_id,
                                               capabilities):
        shared_resource_id = self.client.node_instances.list(
            deployment_id=deployment_id,
            node_id='shared_resource_node')[0].id
        runtime_props = self.client.node_instances.get(
            shared_resource_id).runtime_properties
        self.assertEqual(capabilities,
                         runtime_props['capabilities'])

    def _test_shared_resource_relationship(self, test_blueprint):
        blueprint_path = self.make_yaml_file(test_blueprint)
        deployment_id = 'app'
        self.deploy_application(blueprint_path, deployment_id=deployment_id)
        executions = self.client.executions.list(
            workflow_id='test_wf')
        self.assertEqual(len(executions), 1)
        self.assertEqual(executions[0].deployment_id, 'test')
        establish_execution = executions[0]
        # Getting the install execution
        executions = self.client.executions.list(
            deployment_id=deployment_id, workflow_id='install')
        self.assertEqual(len(executions), 1)
        install_execution = executions[0]
        self.assertLess(install_execution.created_at,
                        establish_execution.created_at)
        self.assertGreater(install_execution.ended_at,
                           establish_execution.ended_at)
        self._validate_shared_resource_capabilities(deployment_id,
                                                    {'test': 1})
        self.undeploy_application(deployment_id)
        executions = self.client.executions.list(
            workflow_id='test_wf', is_descending=True, sort='created_at')
        self.assertEqual(len(executions), 2)
        for execution in executions:
            self.assertEqual(execution.deployment_id, 'test')
            self.assertEqual(execution.parameters, {'t': 1})
        unlink_execution = executions[0]
        # Getting the uninstall execution
        executions = self.client.executions.list(
            deployment_id=deployment_id, workflow_id='uninstall')
        self.assertEqual(len(executions), 1)
        uninstall_execution = executions[0]
        self.assertLess(uninstall_execution.created_at,
                        unlink_execution.created_at)
        self.assertGreater(uninstall_execution.ended_at,
                           unlink_execution.ended_at)

    def test_running_connected_to_shared_resource(self):
        test_blueprint = self._generate_app_blueprint(
            'cloudify.relationships.connected_to_shared_resource')
        self._test_shared_resource_relationship(test_blueprint)

    def test_running_depends_on_shared_resource(self):
        test_blueprint = self._generate_app_blueprint(
            'cloudify.relationships.depends_on_shared_resource')
        self._test_shared_resource_relationship(test_blueprint)

    def test_fails_on_not_existing_workflow(self):
        test_blueprint = self._generate_app_blueprint(
            'cloudify.relationships.depends_on_shared_resource',
            'not_existing')
        blueprint_path = self.make_yaml_file(test_blueprint)

        self.assertRaises(RuntimeError,
                          self.deploy_application,
                          blueprint_path,
                          deployment_id='app')
        self._validate_shared_resource_capabilities('app', {'test': 1})

    def test_fail_when_remote_workflow_fails(self):
        test_blueprint = self._generate_app_blueprint(
            'cloudify.relationships.depends_on_shared_resource',
            'failing')
        blueprint_path = self.make_yaml_file(test_blueprint)

        self.assertRaises(RuntimeError,
                          self.deploy_application,
                          blueprint_path,
                          deployment_id='app')
        self._validate_shared_resource_capabilities('app', {'test': 1})
