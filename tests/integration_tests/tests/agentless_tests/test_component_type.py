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

    def test_given_deployment_name_with_auto_suffix_inc_option(self):
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

    def test_auto_suffix_inc_option_with_deployment_name_collision(self):
        basic_blueprint_path = resource('dsl/basic.yaml')
        self.client.blueprints.upload(basic_blueprint_path,
                                      entity_id='basic')

        # Creating collision with main blueprint's components
        self.deploy_application(basic_blueprint_path,
                                deployment_id='{}-1'.
                                format(self.component_name))

        deployment_id = 'd{0}'.format(uuid.uuid4())
        main_blueprint = """
tosca_definitions_version: cloudify_dsl_1_3

imports:
  - https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager/CY-1119/resources/rest-service/cloudify/types/types.yaml

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

    def test_given_deployment_name_with_no_auto_suffix_inc_option(self):
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
    def _execute_and_cancel_execution(self,
                                      workflow_id,
                                      force=False,
                                      wait_for_termination=True,
                                      is_wait_for_asleep_node=True,
                                      workflow_params=None,
                                      kill_cancel=False):
        dsl_path = resource('dsl/sleep_workflows.yaml')
        self.client.blueprints.upload(dsl_path, entity_id='basic')

        dsl_path = resource(
            'dsl/component_with_blueprint_id.yaml')
        test_id = uuid.uuid1()
        blueprint_id = 'blueprint_{0}'.format(test_id)
        deployment_id = 'deployment_{0}'.format(test_id)
        self.client.blueprints.upload(dsl_path, blueprint_id)
        self.client.deployments.create(blueprint_id, deployment_id,
                                       skip_plugins_validation=True)
        do_retries(verify_deployment_env_created,
                   30,
                   deployment_id=deployment_id)
        execution = self.client.executions.start(
            deployment_id, workflow_id, parameters=workflow_params)

        node_inst_id = self.client.node_instances.list(
            deployment_id=deployment_id)[0].id

        if is_wait_for_asleep_node:
            for retry in range(30):
                if self.client.node_instances.get(
                        node_inst_id).state == 'asleep':
                    break
                time.sleep(1)
            else:
                raise RuntimeError("Execution was expected to go"
                                   " into 'sleeping' status")

        execution = self.client.executions.cancel(execution.id, force, kill=kill_cancel)
        expected_status = Execution.FORCE_CANCELLING if force else \
            Execution.CANCELLING
        self.assertEquals(expected_status, execution.status)
        if wait_for_termination:
            self.wait_for_execution_to_end(execution)
            execution = self.client.executions.get(execution.id)
        return execution, deployment_id

    def test_basic_cascading_cancel(self):
        execution, deployment_id = self._execute_and_cancel_execution(
            'sleep_with_cancel_support')
        self.assertEquals(Execution.CANCELLED, execution.status)

    def test_basic_cascading_force_cancel(self):
        execution, deployment_id = self._execute_and_cancel_execution(
            'sleep', True)
        self.assertEquals(Execution.CANCELLED, execution.status)

    def test_basic_cascading_kill_cancel(self):
        execution, deployment_id = self._execute_and_cancel_execution(
            'sleep', True, kill_cancel=True)
        self.assertEquals(Execution.CANCELLED, execution.status)

    def test_three_level_cascading_cancel(self):
        pass


class ComponentCascadingResume(AgentlessTestCase):
    def test_basic_cascading_resume(self):
        pass

    def test_basic_cascading_force_resume(self):
        pass

    def test_three_level_cascading_resume(self):
        pass
