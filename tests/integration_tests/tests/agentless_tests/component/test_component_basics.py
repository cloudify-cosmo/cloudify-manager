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
from integration_tests.tests.utils import (get_resource as resource,
                                           upload_mock_plugin)


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


class ComponentPluginsTest(AgentlessTestCase):
    TEST_PACKAGE_NAME = 'cloudify-script-plugin'
    TEST_PACKAGE_VERSION = '1.2'
    test_blueprint = """
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
      plugins:
        cloudify-script-plugin:
          wagon_path: {0}/{1}
          plugin_yaml_path: {0}/{2}
"""

    def test_not_loading_existing_plugin(self):
        mock_id = upload_mock_plugin(self.TEST_PACKAGE_NAME,
                                     self.TEST_PACKAGE_VERSION)['id']
        self.wait_for_all_executions_to_end()
        basic_blueprint_path = resource('dsl/empty_blueprint.yaml')
        self.client.blueprints.upload(basic_blueprint_path,
                                      entity_id='basic')

        deployment_id = 'd{0}'.format(uuid.uuid4())
        main_blueprint = self.test_blueprint.format(
            'https://cloudify-tests-files.s3-eu-west-1.amazonaws.com/plugins',
            'cloudify_script_plugin/1_2/'
            'cloudify_script_plugin-1.2-py27-none-any.wgn',
            'cloudify_script_plugin/1_2/plugin.yaml'
        )

        blueprint_path = self.make_yaml_file(main_blueprint)
        self.deploy_application(blueprint_path, deployment_id=deployment_id)
        plugins_list = self.client.plugins.list()
        self.assertEqual(len(plugins_list), 1)
        self.assertTrue(plugins_list[0]['package_name'],
                        self.TEST_PACKAGE_NAME)
        self.undeploy_application(deployment_id, is_delete_deployment=True)
        self.assertEqual(len(self.client.plugins.list()), 1)
        self.client.plugins.delete(mock_id)

    def test_uploading_different_version_plugin_than_existing(self):
        mock_id = upload_mock_plugin(
            self.TEST_PACKAGE_NAME,
            self.TEST_PACKAGE_VERSION)['id']
        self.wait_for_all_executions_to_end()
        basic_blueprint_path = resource('dsl/empty_blueprint.yaml')
        self.client.blueprints.upload(basic_blueprint_path,
                                      entity_id='basic')
        deployment_id = 'd{0}'.format(uuid.uuid4())
        main_blueprint = self.test_blueprint.format(
            'https://cloudify-tests-files.s3-eu-west-1.amazonaws.com/plugins',
            'cloudify_script_plugin/2_0/'
            'cloudify_script_plugin-2.0-py27-none-any.wgn',
            'cloudify_script_plugin/2_0/plugin.yaml'
        )
        blueprint_path = self.make_yaml_file(main_blueprint)
        self.deploy_application(blueprint_path, deployment_id=deployment_id)
        plugins_list = self.client.plugins.list()
        self.assertEqual(len(plugins_list), 2)
        self.assertTrue(plugins_list[0]['package_version'],
                        self.TEST_PACKAGE_NAME)
        self.assertTrue(plugins_list[1]['package_version'],
                        self.TEST_PACKAGE_NAME)
        self.undeploy_application(deployment_id)
        self.assertEqual(len(self.client.plugins.list()), 1)
        self.client.plugins.delete(mock_id)


class ComponentSecretsTypesTest(AgentlessTestCase):
    def test_basic_types_creation(self):
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
      secrets:
        integer: 1
        list: [1, 2]
        dict:
            a: 1
        string: a
        float: 1.5
        boolean: false
        regex: ^.$
"""
        blueprint_path = self.make_yaml_file(main_blueprint)
        self.deploy_application(blueprint_path, deployment_id=deployment_id)
        self.assertEqual(self.client.secrets.get('integer')['value'], '1')
        self.assertEqual(self.client.secrets.get('list')['value'], '[1, 2]')
        self.assertEqual(self.client.secrets.get('dict')['value'], "{u'a': 1}")
        self.assertEqual(self.client.secrets.get('string')['value'], u'a')
        self.assertEqual(self.client.secrets.get('float')['value'], '1.5')
        self.assertEqual(self.client.secrets.get('boolean')['value'], 'False')
        self.assertEqual(self.client.secrets.get('regex')['value'], u'^.$')


class ComponentInputsTypesTest(AgentlessTestCase):
    def test_basic_types(self):
        component_blueprint = """
tosca_definitions_version: cloudify_dsl_1_3

imports:
  - cloudify/types/types.yaml

inputs:
    integer:
        type: integer
    list:
        type: list
    dict:
        type: dict
    string:
        type: string
    float:
        type: float
    boolean:
        type: boolean
    regex:
        type: regex
"""
        blueprint_path = self.make_yaml_file(component_blueprint)
        self.client.blueprints.upload(blueprint_path,
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
          inputs:
            integer: 1
            list: [1, 2]
            dict:
                a: 1
            string: a
            float: 1.5
            boolean: false
            regex: ^.$
"""
        blueprint_path = self.make_yaml_file(main_blueprint)
        self.deploy_application(blueprint_path, deployment_id=deployment_id)
        deployment = self.client.deployments.get('component')
        self.assertEqual(deployment.inputs['integer'], 1)
        self.assertEqual(deployment.inputs['list'], [1, 2])
        self.assertEqual(deployment.inputs['dict'], {'a': 1})
        self.assertEqual(deployment.inputs['string'], 'a')
        self.assertEqual(deployment.inputs['float'], 1.5)
        self.assertEqual(deployment.inputs['boolean'], False)
        self.assertEqual(deployment.inputs['regex'], '^.$')

    def test_type_mismatch_fails_install(self):
        component_blueprint = """
tosca_definitions_version: cloudify_dsl_1_3

inputs:
    integer:
        type: integer
"""
        blueprint_path = self.make_yaml_file(component_blueprint)
        self.client.blueprints.upload(blueprint_path,
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
          inputs:
            integer: 'a'
"""
        blueprint_path = self.make_yaml_file(main_blueprint)
        self.assertRaises(RuntimeError, self.deploy_application,
                          blueprint_path, deployment_id=deployment_id)


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
