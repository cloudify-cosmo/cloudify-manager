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

from cloudify_rest_client.exceptions import CloudifyClientError

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource


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
