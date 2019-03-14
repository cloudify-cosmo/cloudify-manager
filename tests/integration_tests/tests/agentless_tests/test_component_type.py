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

from cloudify_rest_client.executions import Execution
from cloudify_rest_client.exceptions import CloudifyClientError

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import (
    verify_deployment_env_created,
    do_retries,
    get_resource as resource)


class ComponentTypeTest(AgentlessTestCase):
    component_name = 'component'

    def test_component_creation_with_blueprint_id(self):
        basic_blueprint_path = resource('dsl/basic.yaml')
        self.client.blueprints.upload(basic_blueprint_path,
                                      entity_id='basic')
        deployment_id = 'd{0}'.format(uuid.uuid4())
        dsl_path = resource('dsl/component_with_blueprint_id.yaml')
        self.deploy_application(dsl_path, deployment_id=deployment_id)
        self.assertTrue(self.client.deployments.get(self.component_name))
        self.undeploy_application(deployment_id, is_delete_deployment=True)
        self.assertRaises(CloudifyClientError,
                          self.client.deployments.get,
                          self.component_name)
        self.assertRaises(CloudifyClientError,
                          self.client.deployments.get,
                          deployment_id)

    def test_component_creation_with_blueprint_package(self):
        deployment_id = 'd{0}'.format(uuid.uuid4())
        dsl_path = resource('dsl/component_with_blueprint_package.yaml')
        self.deploy_application(dsl_path,
                                deployment_id=deployment_id)
        self.assertTrue(self.client.deployments.get(self.component_name))
        self.undeploy_application(deployment_id, is_delete_deployment=True)
        self.assertRaises(CloudifyClientError,
                          self.client.deployments.get,
                          deployment_id)
        self.assertRaises(CloudifyClientError,
                          self.client.deployments.get,
                          self.component_name)

    def test_component_creation_with_secrets_and_plugins(self):
        basic_blueprint_path = resource('dsl/basic.yaml')
        self.client.blueprints.upload(basic_blueprint_path,
                                      entity_id='basic')
        deployment_id = 'd{0}'.format(uuid.uuid4())
        dsl_path = resource('dsl/component_with_plugins_and_secrets.yaml')
        self.deploy_application(dsl_path, deployment_id=deployment_id)
        self.assertTrue(self.client.deployments.get(self.component_name))
        self.assertEqual(self.client.secrets.get('secret1')['value'], 'test')
        plugins_list = self.client.plugins.list()
        self.assertEqual(len(plugins_list), 1)
        self.assertTrue(plugins_list[0]['package_name'],
                        'cloudify-openstack-plugin')
        self.undeploy_application(deployment_id, is_delete_deployment=True)
        self.assertRaises(CloudifyClientError,
                          self.client.deployments.get,
                          self.component_name)
        self.assertRaises(CloudifyClientError,
                          self.client.deployments.get,
                          deployment_id)


class ComponentTypeFailuresTest(AgentlessTestCase):

    def test_component_creation_with_not_existing_blueprint_id(self):
        deployment_id = 'd{0}'.format(uuid.uuid4())
        dsl_path = resource('dsl/component_with_blueprint_id.yaml')
        self.assertRaises(RuntimeError,
                          self.deploy_application,
                          dsl_path,
                          deployment_id=deployment_id)

    def test_component_creation_with_not_existing_blueprint_package(self):
        deployment_id = 'd{0}'.format(uuid.uuid4())
        dsl_path = resource(
            'dsl/component_with_not_existing_blueprint_package.yaml')
        self.assertRaises(RuntimeError,
                          self.deploy_application,
                          dsl_path,
                          deployment_id=deployment_id)


class ComponentScaleCreation(AgentlessTestCase):
    component_name = 'component'

    def test_given_deployment_name_with_auto_inc_suffix_option(self):
        basic_blueprint_path = resource('dsl/basic.yaml')
        self.client.blueprints.upload(basic_blueprint_path,
                                      entity_id='basic')
        deployment_id = 'd{0}'.format(uuid.uuid4())
        main_blueprint = """
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
          id: basic
        deployment:
          id: component
          auto_inc_suffix: true
    capabilities:
        scalable:
            properties:
                default_instances: 2
"""
        blueprint_path = self.make_yaml_file(main_blueprint)
        self.deploy_application(blueprint_path, deployment_id=deployment_id)
        deployments = self.client.deployments.list(_include=['id'])
        self.assertEqual(len(deployments), 3)
        self.undeploy_application(deployment_id, is_delete_deployment=True)
        deployments = self.client.deployments.list(_include=['id'])
        self.assertEqual(len(deployments), 0)

    def test_auto_inc_suffix_option_with_deployment_name_collision(self):
        basic_blueprint_path = resource('dsl/basic.yaml')
        self.client.blueprints.upload(basic_blueprint_path,
                                      entity_id='basic')

        # Creating collision with main blueprint's components
        self.deploy_application(basic_blueprint_path,
                                deployment_id='{0}-1'.
                                format(self.component_name))

        deployment_id = 'd{0}'.format(uuid.uuid4())
        main_blueprint = """
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
          id: basic
        deployment:
          id: component
          auto_inc_suffix: true
    capabilities:
        scalable:
            properties:
                default_instances: 2
"""
        blueprint_path = self.make_yaml_file(main_blueprint)
        self.deploy_application(blueprint_path, deployment_id=deployment_id)
        deployments = self.client.deployments.list(_include=['id'])
        self.assertEqual(len(deployments), 4)
        self.undeploy_application(deployment_id, is_delete_deployment=True)
        deployments = self.client.deployments.list(_include=['id'])
        self.assertEqual(len(deployments), 1)

    def test_given_deployment_name_with_no_auto_inc_suffix_option(self):
        basic_blueprint_path = resource('dsl/basic.yaml')
        self.client.blueprints.upload(basic_blueprint_path,
                                      entity_id='basic')
        deployment_id = 'd{0}'.format(uuid.uuid4())
        main_blueprint = """
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
          id: basic
        deployment:
          id: component
    capabilities:
        scalable:
            properties:
                default_instances: 2
"""
        blueprint_path = self.make_yaml_file(main_blueprint)
        self.assertRaises(RuntimeError,
                          self.deploy_application,
                          blueprint_path,
                          deployment_id=deployment_id)
        deployments = self.client.deployments.list(_include=['id'])
        self.assertEqual(len(deployments), 2)
        executions = self.client.executions.list(is_descending=True,
                                                 _include=['id',
                                                           'status',
                                                           'workflow_id'])
        install_executions = [execution for execution in executions
                              if execution.workflow_id == 'install']

        # Verifying that the second component had failed in install
        self.assertEqual(install_executions[0].status, 'failed')
        self.assertEqual(install_executions[1].status, 'terminated')


class ComponentCascadingCancel(AgentlessTestCase):
    def _wait_for_component_install(self, deployment_id):
        # waiting for component to create it's deployment
        do_retries(verify_deployment_env_created,
                   30,
                   deployment_id=deployment_id)
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
            self.assertEquals(expected_status, execution.status)

        executions = self.client.executions.list(workflow_id='install')
        for execution in executions:
            self.wait_for_execution_to_end(execution)

        # Asserting all is finished in the correct state
        executions = self.client.executions.list(workflow_id='install')
        for execution in executions:
            self.assertEquals(Execution.CANCELLED, execution.status)
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
        do_retries(verify_deployment_env_created,
                   30,
                   deployment_id=deployment_id)
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
        self.assertEquals(Execution.TERMINATED, main_execution.status)
        executions = self.client.executions.list(workflow_id='install')
        for execution in executions:
            self.wait_for_execution_to_end(execution)
        # Asserting all is finished in the correct state
        executions = self.client.executions.list(workflow_id='install')
        for execution in executions:
            self.assertEquals(Execution.TERMINATED, execution.status)

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
            self.assertEquals(Execution.CANCELLED, execution.status)

    def test_three_level_cascading_cancel(self):
        sleep = resource('dsl/sleep_node.yaml')
        self.client.blueprints.upload(sleep, entity_id='sleep')

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
        do_retries(verify_deployment_env_created,
                   30,
                   deployment_id=deployment_id)
        main_execution = self.client.executions.start(deployment_id, 'install')
        self._wait_for_component_install(deployment_id='component')
        main_execution = self.client.executions.cancel(main_execution.id)
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
        do_retries(verify_deployment_env_created,
                   30,
                   deployment_id=deployment_id)
        main_execution = self.client.executions.start(deployment_id, 'install')
        main_execution = self.client.executions.cancel(main_execution.id)
        self._verify_cancel_install_execution(main_execution, False, False)
        self._resume_and_verify_executions_end(main_execution, 3)
