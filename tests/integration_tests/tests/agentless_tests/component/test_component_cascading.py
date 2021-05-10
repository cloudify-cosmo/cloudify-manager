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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import uuid
import time

import pytest

from cloudify_rest_client.executions import Execution
from cloudify_rest_client.exceptions import CloudifyClientError

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import (
    verify_deployment_env_created,
    do_retries,
    get_resource as resource,
    wait_for_blueprint_upload)


@pytest.mark.usefixtures('testmockoperations_plugin')
class ComponentCascadingCancelAndResume(AgentlessTestCase):
    def _wait_for_component_deployment(self,
                                       deployment_id,
                                       client=None,
                                       timeout_seconds=60):
        # waiting for component to create it's deployment
        client = client or self.client
        do_retries(
            verify_deployment_env_created,
            container_id=self.env.container_id,
            deployment_id=deployment_id,
            client=client,
            timeout_seconds=timeout_seconds
        )

    def _wait_for_component_install(self, deployment_id):
        # waiting for component to create it's deployment
        self._wait_for_component_deployment(deployment_id)
        # Waiting for the sleep node to start
        node_instance_id = self.client.node_instances.list(
            deployment_id=deployment_id)[0].id
        for retry in range(30):
            if self.client.node_instances.get(
                    node_instance_id).state == 'creating':
                break
            time.sleep(1)
        else:
            raise RuntimeError("sleep node instance was expected to go"
                               " into 'creating' status")

    def _verify_cancel_install_execution(self,
                                         execution,
                                         force,
                                         kill_cancel,
                                         verify_intermediate_state=True):
        expected_status = Execution.CANCELLING
        if force:
            expected_status = Execution.FORCE_CANCELLING
        elif kill_cancel:
            expected_status = Execution.KILL_CANCELLING

        if verify_intermediate_state:
            do_retries(
                self.assertEqual,
                first=expected_status,
                second=execution.status,
            )

        executions = self.client.executions.list(workflow_id='install')
        for execution in executions:
            self.wait_for_execution_to_end(execution)

        # Asserting all is finished in the correct state
        executions = self.client.executions.list(workflow_id='install')
        for execution in executions:
            self.assertEqual(Execution.CANCELLED, execution.status)
        return executions

    def _execute_and_cancel_execution(self,
                                      force=False,
                                      kill_cancel=False,
                                      wait_for_component=True,
                                      verify_intermediate_state=True):
        # component's blueprint
        sleep_blueprint = resource('dsl/sleep_node.yaml')
        self.client.blueprints.upload(sleep_blueprint, entity_id='basic')

        main_blueprint = resource(
            'dsl/component_with_blueprint_id.yaml')
        test_id = uuid.uuid1()
        blueprint_id = 'blueprint_{0}'.format(test_id)
        deployment_id = 'deployment_{0}'.format(test_id)
        self.client.blueprints.upload(main_blueprint, blueprint_id)
        self.client.deployments.create(blueprint_id, deployment_id,
                                       skip_plugins_validation=True)

        self._wait_for_component_deployment(deployment_id)
        execution = self.client.executions.start(deployment_id, 'install')

        if wait_for_component:
            self._wait_for_component_install('component')

        execution = self.client.executions.cancel(execution.id,
                                                  force,
                                                  kill=kill_cancel)
        self._verify_cancel_install_execution(execution,
                                              force,
                                              kill_cancel,
                                              verify_intermediate_state)

        return execution

    def _resume_and_verify_executions_end(
            self, main_execution, expected_number_executions):
        main_execution = self.client.executions.resume(main_execution.id,
                                                       force=True)
        main_execution = self.wait_for_execution_to_end(main_execution)
        self.assertEqual(Execution.TERMINATED, main_execution.status)
        executions = self.client.executions.list(workflow_id='install')
        for execution in executions:
            self.wait_for_execution_to_end(execution)
        # Asserting all is finished in the correct state
        executions = self.client.executions.list(workflow_id='install')
        for execution in executions:
            self.assertEqual(Execution.TERMINATED, execution.status)

        self.assertEqual(expected_number_executions, len(executions))

    def test_basic_cascading_cancel(self):
        self._execute_and_cancel_execution()

    def test_basic_cascading_cancel_when_not_started(self):
        self._execute_and_cancel_execution(wait_for_component=False)

    def test_basic_cascading_cancel_and_resume(self):
        """
        This test does not wait for the components to be created, so
        the resume operation will complete the install.
        """
        main_execution = self._execute_and_cancel_execution(
            wait_for_component=False)
        self._resume_and_verify_executions_end(main_execution, 2)

    def test_basic_cascading_force_cancel(self):
        self._execute_and_cancel_execution(force=True)

    def test_basic_cascading_kill_cancel(self):
        """
        This only checks for the final stage of the cancellation,
        in order to avoid race conditions in catching the intermediate
        stage of kill_canceling.
        """
        self._execute_and_cancel_execution(kill_cancel=True,
                                           verify_intermediate_state=False)
        executions = self.client.executions.list(workflow_id='install')
        for execution in executions:
            self.assertEqual(Execution.CANCELLED, execution.status)

    def test_three_level_cascading_cancel(self):
        sleep = resource('dsl/sleep_node.yaml')
        self.client.blueprints.upload(sleep, entity_id='sleep')
        wait_for_blueprint_upload('sleep', self.client)

        layer_1 = """
tosca_definitions_version: cloudify_dsl_1_3

imports:
  - cloudify/types/types.yaml

node_templates:

  component_node:
    type: cloudify.nodes.Component
    properties:
      resource_config:
        blueprint:
          external_resource: true
          id: sleep
        deployment:
          id: sleep_component
"""
        layer_1_path = self.make_yaml_file(layer_1)
        self.client.blueprints.upload(layer_1_path, entity_id='layer_1')
        wait_for_blueprint_upload('layer_1', self.client)

        layer_2 = """
tosca_definitions_version: cloudify_dsl_1_3

imports:
  - cloudify/types/types.yaml

node_templates:

  component_node:
    type: cloudify.nodes.Component
    properties:
      resource_config:
        blueprint:
          external_resource: true
          id: layer_1
        deployment:
          id: component
"""
        layer_2_path = self.make_yaml_file(layer_2)
        test_id = uuid.uuid1()
        blueprint_id = 'blueprint_{0}'.format(test_id)
        deployment_id = 'deployment_{0}'.format(test_id)
        self.client.blueprints.upload(layer_2_path, blueprint_id)
        self.client.deployments.create(blueprint_id, deployment_id,
                                       skip_plugins_validation=True)

        self._wait_for_component_deployment(deployment_id)
        main_execution = self.client.executions.start(deployment_id, 'install')
        self._wait_for_component_install(deployment_id='component')
        main_execution = self.client.executions.cancel(main_execution.id)
        time.sleep(0.2)  # give time for the cancel to take place
        executions = self._verify_cancel_install_execution(main_execution,
                                                           False,
                                                           False)
        # The number of executions depends when the cancel occurred
        self.assertLessEqual(len(executions), 3)

    def test_three_level_cascading_cancel_and_resume(self):
        """
        This test does not wait for the components to be created, so
        the resume operation will complete the install.
        """
        dsl_path = resource('dsl/sleep_node.yaml')
        self.client.blueprints.upload(dsl_path, entity_id='sleep')
        wait_for_blueprint_upload('sleep', self.client)

        layer_1 = """
tosca_definitions_version: cloudify_dsl_1_3

imports:
  - cloudify/types/types.yaml

node_templates:

  component_node:
    type: cloudify.nodes.Component
    properties:
      resource_config:
        blueprint:
          external_resource: true
          id: sleep
        deployment:
          id: sleep_component
"""
        layer_1_path = self.make_yaml_file(layer_1)
        self.client.blueprints.upload(layer_1_path, entity_id='layer_1')
        wait_for_blueprint_upload('layer_1', self.client)

        layer_2 = """
tosca_definitions_version: cloudify_dsl_1_3

imports:
  - cloudify/types/types.yaml

node_templates:

  component_node:
    type: cloudify.nodes.Component
    properties:
      resource_config:
        blueprint:
          external_resource: true
          id: layer_1
        deployment:
          id: component
"""
        layer_2_path = self.make_yaml_file(layer_2)
        test_id = uuid.uuid1()
        blueprint_id = 'blueprint_{0}'.format(test_id)
        deployment_id = 'deployment_{0}'.format(test_id)
        self.client.blueprints.upload(layer_2_path, blueprint_id)
        wait_for_blueprint_upload(blueprint_id, self.client)

        self.client.deployments.create(blueprint_id, deployment_id,
                                       skip_plugins_validation=True)
        self._wait_for_component_deployment(deployment_id)
        main_execution = self.client.executions.start(deployment_id, 'install')
        main_execution = self.client.executions.cancel(main_execution.id)
        self._verify_cancel_install_execution(main_execution, False, False)
        self._resume_and_verify_executions_end(main_execution, 3)


@pytest.mark.usefixtures('mock_workflows_plugin')
class ComponentCascadingWorkflows(AgentlessTestCase):
    component_blueprint_with_nothing_workflow = """
tosca_definitions_version: cloudify_dsl_1_3

imports:
    - cloudify/types/types.yaml
    - wf--blueprint:mock_workflows


workflows:
    nothing_workflow:
        mapping: wf--mock_workflows.mock_workflows.workflows.do_nothing
        is_cascading: true
"""

    def setUp(self):
        super(ComponentCascadingWorkflows, self).setUp()
        self.client.blueprints.upload(
            resource('dsl/mock_workflows.yaml'),
            entity_id='mock_workflows')
        wait_for_blueprint_upload('mock_workflows', self.client)

    @staticmethod
    def generate_root_blueprint_with_component(blueprint_id='workflow',
                                               deployment_id='component'):
        return """
tosca_definitions_version: cloudify_dsl_1_3

imports:
    - cloudify/types/types.yaml
    - wf--blueprint:mock_workflows

node_templates:
    component_node:
      type: cloudify.nodes.Component
      properties:
        resource_config:
          blueprint:
            external_resource: true
            id: {0}
          deployment:
            id: {1}

workflows:
    nothing_workflow:
        mapping: wf--mock_workflows.mock_workflows.workflows.do_nothing
        is_cascading: true
""".format(blueprint_id, deployment_id)

    def test_default_workflow_cascading_flag(self):
        basic_blueprint_path = self.make_yaml_file(
            self.component_blueprint_with_nothing_workflow)
        self.client.blueprints.upload(basic_blueprint_path,
                                      entity_id='workflow')
        wait_for_blueprint_upload('workflow', self.client)

        deployment_id = 'd{0}'.format(uuid.uuid4())
        main_blueprint = """
tosca_definitions_version: cloudify_dsl_1_3

imports:
    - cloudify/types/types.yaml
    - plugin:mock_workflows

node_templates:
    component_node:
      type: cloudify.nodes.Component
      properties:
        resource_config:
          blueprint:
            external_resource: true
            id: workflow
          deployment:
            id: test

workflows:
    nothing_workflow:
        mapping: mock_workflows.mock_workflows.workflows.do_nothing
"""
        main_blueprint_path = self.make_yaml_file(main_blueprint)

        self.deploy_application(main_blueprint_path,
                                deployment_id=deployment_id)

        main_execution = self.client.executions.start(deployment_id,
                                                      'nothing_workflow')
        executions = self.client.executions.list(
            workflow_id='nothing_workflow')
        for execution in executions:
            self.wait_for_execution_to_end(execution)

        executions = self.client.executions.list(
            workflow_id='nothing_workflow')
        for execution in executions:
            self.assertEqual(Execution.TERMINATED, execution.status)
            self.assertEqual(main_execution.created_by, execution.created_by)

    def test_3_layer_cascading_workflow(self):
        layer_3_path = self.make_yaml_file(
            self.component_blueprint_with_nothing_workflow)
        self.client.blueprints.upload(layer_3_path,
                                      entity_id='layer_3')
        wait_for_blueprint_upload('layer_3', self.client)

        layer_2 = self.generate_root_blueprint_with_component(
            'layer_3', 'other_component')
        layer_2_path = self.make_yaml_file(layer_2)
        self.client.blueprints.upload(layer_2_path,
                                      entity_id='layer_2')
        wait_for_blueprint_upload('layer_2', self.client)

        deployment_id = 'd{0}'.format(uuid.uuid4())
        main_blueprint = self.generate_root_blueprint_with_component(
            'layer_2', 'component')
        main_blueprint_path = self.make_yaml_file(main_blueprint)
        self.deploy_application(main_blueprint_path,
                                deployment_id=deployment_id,
                                timeout_seconds=120)

        self.client.executions.start(deployment_id, 'nothing_workflow')
        executions = self.client.executions.list(
            workflow_id='nothing_workflow')
        for execution in executions:
            self.wait_for_execution_to_end(execution)

        executions = self.client.executions.list(
            workflow_id='nothing_workflow')
        for execution in executions:
            self.assertEqual(Execution.TERMINATED, execution.status)
        self.assertEqual(len(executions), 3)

    def test_not_cascading_workflow_not_to_cascade(self):
        basic_blueprint_path = self.make_yaml_file(
            self.component_blueprint_with_nothing_workflow)
        self.client.blueprints.upload(basic_blueprint_path,
                                      entity_id='workflow')
        wait_for_blueprint_upload('workflow', self.client)

        deployment_id = 'd{0}'.format(uuid.uuid4())
        main_blueprint = """
tosca_definitions_version: cloudify_dsl_1_3

imports:
    - cloudify/types/types.yaml
    - plugin:mock_workflows

node_templates:
    component_node:
      type: cloudify.nodes.Component
      properties:
        resource_config:
          blueprint:
            external_resource: true
            id: workflow
          deployment:
            id: component

workflows:
    other_nothing_workflow:
        mapping: mock_workflows.mock_workflows.workflows.do_nothing
        is_cascading: false
"""
        main_blueprint_path = self.make_yaml_file(main_blueprint)
        self.deploy_application(main_blueprint_path,
                                deployment_id=deployment_id)

        self.client.executions.start(deployment_id, 'other_nothing_workflow')
        executions = self.client.executions.list(
            workflow_id='other_nothing_workflow')
        self.assertEqual(len(executions), 1)

    def test_cascading_workflow_stopped_in_the_path(self):
        """
        The user can define that the cascading workflow in the
        downstream Components is not cascading anymore.
        """
        layer_3_path = self.make_yaml_file(
            self.component_blueprint_with_nothing_workflow)
        self.client.blueprints.upload(layer_3_path,
                                      entity_id='layer_3')
        wait_for_blueprint_upload('layer_3', self.client)

        layer_2 = """
tosca_definitions_version: cloudify_dsl_1_3

imports:
    - cloudify/types/types.yaml
    - plugin:mock_workflows

node_templates:
    component_node:
      type: cloudify.nodes.Component
      properties:
        resource_config:
          blueprint:
            external_resource: true
            id: layer_3
          deployment:
            id: other_component


workflows:
    nothing_workflow:
        mapping: mock_workflows.mock_workflows.workflows.do_nothing
        is_cascading: false
"""
        layer_2_path = self.make_yaml_file(layer_2)
        self.client.blueprints.upload(layer_2_path,
                                      entity_id='layer_2')
        wait_for_blueprint_upload('layer_2', self.client)

        deployment_id = 'd{0}'.format(uuid.uuid4())
        main_blueprint = self.generate_root_blueprint_with_component(
            'layer_2', 'component')
        main_blueprint_path = self.make_yaml_file(main_blueprint)
        self.deploy_application(main_blueprint_path,
                                deployment_id=deployment_id,
                                timeout_seconds=120)

        self.client.executions.start(deployment_id, 'nothing_workflow')
        executions = self.client.executions.list(
            workflow_id='nothing_workflow')
        for execution in executions:
            self.wait_for_execution_to_end(execution)

        executions = self.client.executions.list(
            workflow_id='nothing_workflow')
        for execution in executions:
            self.assertEqual(Execution.TERMINATED, execution.status)
        self.assertEqual(len(executions), 2)

    def test_not_defined_cascading_workflow(self):
        basic_blueprint = """
tosca_definitions_version: cloudify_dsl_1_3

imports:
    - cloudify/types/types.yaml
"""
        basic_blueprint_path = self.make_yaml_file(basic_blueprint)
        self.client.blueprints.upload(basic_blueprint_path,
                                      entity_id='workflow')
        wait_for_blueprint_upload('workflow', self.client)

        deployment_id = 'd{0}'.format(uuid.uuid4())
        main_blueprint = self.generate_root_blueprint_with_component()
        main_blueprint_path = self.make_yaml_file(main_blueprint)
        self.deploy_application(main_blueprint_path,
                                deployment_id=deployment_id)

        self.assertRaises(CloudifyClientError,
                          self.client.executions.start,
                          deployment_id,
                          'nothing_workflow')

    def test_failing_cascading_workflow(self):
        component_1 = """
tosca_definitions_version: cloudify_dsl_1_3

imports:
    - cloudify/types/types.yaml
    - wf--blueprint:mock_workflows


workflows:
    nothing_workflow:
        mapping: wf--mock_workflows.mock_workflows.workflows.non_recoverable
        is_cascading: true
"""
        component_1_path = self.make_yaml_file(component_1)
        self.client.blueprints.upload(component_1_path,
                                      entity_id='component_1')
        wait_for_blueprint_upload('component_1', self.client)

        component_2_path = self.make_yaml_file(
            self.component_blueprint_with_nothing_workflow)
        self.client.blueprints.upload(component_2_path,
                                      entity_id='component_2')
        wait_for_blueprint_upload('component_2', self.client)

        deployment_id = 'd{0}'.format(uuid.uuid4())
        main_blueprint = """
tosca_definitions_version: cloudify_dsl_1_3

imports:
    - cloudify/types/types.yaml
    - wf--blueprint:mock_workflows

node_templates:
    component_1:
      type: cloudify.nodes.Component
      properties:
        resource_config:
          blueprint:
            external_resource: true
            id: component_1
          deployment:
            id: component_1

    component_2:
      type: cloudify.nodes.Component
      properties:
        resource_config:
          blueprint:
            external_resource: true
            id: component_2
          deployment:
            id: component_2

workflows:
    nothing_workflow:
        mapping: wf--mock_workflows.mock_workflows.workflows.do_nothing
        is_cascading: true
"""
        main_blueprint_path = self.make_yaml_file(main_blueprint)
        self.deploy_application(main_blueprint_path,
                                deployment_id=deployment_id)

        main_execution = self.client.executions.start(deployment_id,
                                                      'nothing_workflow')
        self.wait_for_execution_to_end(main_execution)

        component_2_execution = self.client.executions.list(
            workflow_id='nothing_workflow', deployment_id='component_2')[0]
        component_2_execution = self.wait_for_execution_to_end(
            component_2_execution)
        self.assertEqual(Execution.TERMINATED, component_2_execution.status)

        component_1_execution = self.client.executions.list(
            workflow_id='nothing_workflow', deployment_id='component_1')[0]
        self.assertRaises(RuntimeError,
                          self.wait_for_execution_to_end,
                          component_1_execution)
        component_1_execution = self.client.executions.list(
            workflow_id='nothing_workflow', deployment_id='component_1')[0]
        self.assertEqual(Execution.FAILED, component_1_execution.status)

    def test_cascading_dry_run_workflow(self):
        basic_blueprint_path = self.make_yaml_file(
            self.component_blueprint_with_nothing_workflow)
        self.client.blueprints.upload(basic_blueprint_path,
                                      entity_id='workflow')
        wait_for_blueprint_upload('workflow', self.client)

        deployment_id = 'd{0}'.format(uuid.uuid4())
        main_blueprint = self.generate_root_blueprint_with_component()
        main_blueprint_path = self.make_yaml_file(main_blueprint)
        self.deploy_application(main_blueprint_path,
                                deployment_id=deployment_id)

        self.client.executions.start(deployment_id,
                                     'nothing_workflow',
                                     dry_run=True)
        executions = self.client.executions.list(
            workflow_id='nothing_workflow')
        for execution in executions:
            self.wait_for_execution_to_end(execution)

        executions = self.client.executions.list(
            workflow_id='nothing_workflow')
        for execution in executions:
            self.assertEqual(Execution.TERMINATED, execution.status)
            self.assertTrue(execution.is_dry_run)

    def test_cascading_workflow_with_parameters(self):
        basic_blueprint_path = self.make_yaml_file(
            self.component_blueprint_with_nothing_workflow)
        self.client.blueprints.upload(basic_blueprint_path,
                                      entity_id='workflow')
        wait_for_blueprint_upload('workflow', self.client)

        deployment_id = 'd{0}'.format(uuid.uuid4())
        main_blueprint = self.generate_root_blueprint_with_component()
        main_blueprint_path = self.make_yaml_file(main_blueprint)
        self.deploy_application(main_blueprint_path,
                                deployment_id=deployment_id)

        parameters = {'param': 1}
        self.client.executions.start(deployment_id,
                                     'nothing_workflow',
                                     parameters=parameters,
                                     allow_custom_parameters=True)
        executions = self.client.executions.list(
            workflow_id='nothing_workflow')
        for execution in executions:
            self.wait_for_execution_to_end(execution)

        executions = self.client.executions.list(
            workflow_id='nothing_workflow')
        for execution in executions:
            self.assertEqual(Execution.TERMINATED, execution.status)
            self.assertTrue(execution.parameters, parameters)

    def test_cascading_queued_workflow_execution(self):
        basic_blueprint = """
tosca_definitions_version: cloudify_dsl_1_3

imports:
    - cloudify/types/types.yaml
    - plugin:mock_workflows


workflows:
    nothing_workflow:
        mapping: mock_workflows.mock_workflows.workflows.simple_sleep
        is_cascading: true

    other_workflow:
        mapping: mock_workflows.mock_workflows.workflows.do_nothing
        is_cascading: true
"""
        basic_blueprint_path = self.make_yaml_file(basic_blueprint)
        self.client.blueprints.upload(basic_blueprint_path,
                                      entity_id='workflow')
        wait_for_blueprint_upload('workflow', self.client)

        deployment_id = 'd{0}'.format(uuid.uuid4())
        main_blueprint = self.generate_root_blueprint_with_component(
            deployment_id='component')
        main_blueprint_path = self.make_yaml_file(main_blueprint)
        self.deploy_application(main_blueprint_path,
                                deployment_id=deployment_id)

        self.execute_workflow('nothing_workflow', deployment_id)
        self.client.executions.start(deployment_id,
                                     'nothing_workflow',
                                     queue=True)
        component_execution = self.client.executions.list(
            deployment_id='component',
            workflow_id='nothing_workflow',
            is_descending=True,
            sort='created_at')[0]
        self.assertEqual(component_execution.status, Execution.QUEUED)
        executions = self.client.executions.list(
            workflow_id='nothing_workflow')
        self.assertEqual(len(executions), 4)
