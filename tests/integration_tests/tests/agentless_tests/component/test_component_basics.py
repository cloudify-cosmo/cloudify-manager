########
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

import uuid
from time import sleep

import pytest

from cloudify_rest_client.exceptions import CloudifyClientError

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import (
    get_resource as resource,
    upload_mock_plugin,
    wait_for_blueprint_upload,
    wait_for_executions,
)

pytestmark = pytest.mark.group_service_composition


@pytest.mark.usefixtures('cloudmock_plugin')
@wait_for_executions
class ComponentTypeTest(AgentlessTestCase):
    component_name = 'component'
    basic_blueprint_id = 'basic'

    def test_component_creation_with_blueprint_id(self):
        component_blueprint = """
tosca_definitions_version: cloudify_dsl_1_4

imports:
  - cloudify/types/types.yaml

capabilities:
    test:
        value: 1
"""
        blueprint_path = self.make_yaml_file(component_blueprint)
        self.client.blueprints.upload(blueprint_path,
                                      entity_id=self.basic_blueprint_id)
        wait_for_blueprint_upload(self.basic_blueprint_id, self.client, True)
        deployment_id = 'd{0}'.format(uuid.uuid4())
        dsl_path = resource('dsl/component_with_blueprint_id.yaml')
        self.deploy_application(dsl_path, deployment_id=deployment_id)
        self._validate_component_capabilities(deployment_id, {'test': 1})
        self.assertTrue(self.client.deployments.get(self.component_name))
        self.undeploy_application(deployment_id, is_delete_deployment=True)
        self.assertRaises(CloudifyClientError,
                          self.client.deployments.get,
                          self.component_name)
        self.assertRaises(CloudifyClientError,
                          self.client.deployments.get,
                          deployment_id)

    def _validate_component_capabilities(self, deployment_id, capabilities):
        component_id = self.client.node_instances.list(
            deployment_id=deployment_id)[0].id
        component_runtime_props = self.client.node_instances.get(
            component_id).runtime_properties
        self.assertEqual(capabilities,
                         component_runtime_props['capabilities'])

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

    def test_component_creation_with_blueprint_in_internal_directory(self):
        deployment_id = 'd{0}'.format(uuid.uuid4())
        dsl_path = \
            resource('dsl/component_with_blueprint_in_internal_directory.yaml')
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
                                      entity_id=self.basic_blueprint_id)
        wait_for_blueprint_upload(self.basic_blueprint_id, self.client, True)
        deployment_id = 'd{0}'.format(uuid.uuid4())
        dsl_path = resource('dsl/component_with_plugins_and_secrets.yaml')
        self.deploy_application(dsl_path, deployment_id=deployment_id)
        self.assertTrue(self.client.deployments.get(self.component_name))
        self.assertEqual(self.client.secrets.get('secret1')['value'], 'test')
        plugins_list = self.client.plugins.list(
            package_name='cloudify-openstack-plugin')
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

    def test_component_refresh(self):
        capability_blueprint_path = resource(
          'dsl/capability_from_attribute.yaml')
        self.client.blueprints.upload(capability_blueprint_path,
                                      entity_id='bp_with_cap')
        base_bp_path = resource('dsl/component_with_blueprint_id.yaml')
        base_component_dep, _ = self.deploy_application(
            base_bp_path,
            deployment_id='d{0}'.format(uuid.uuid4()),
            inputs={'blueprint_id': 'bp_with_cap'}
        )

        shared_bp_path = resource('dsl/shared_resource_id_from_input.yaml')
        shared_dep, _ = self.deploy_application(
            shared_bp_path,
            deployment_id='d{0}'.format(uuid.uuid4()),
            inputs={'deployment_id': 'component'}
        )

        for dep in [base_component_dep, shared_dep]:
            instances = self.client.node_instances.list(deployment_id=dep.id)
            assert len(instances) == 1
            props = instances[0].runtime_properties
            assert 'capabilities' in props
            assert 'capability1' in props['capabilities']
            assert props['capabilities']['capability1'] is None

        component_instance = self.client.node_instances.list(
          deployment_id='component')[0]
        self.client.node_instances.update(
            component_instance.id,
            version=component_instance.version,
            runtime_properties={
                'attribute1': 42
            }
        )
        for dep in [base_component_dep, shared_dep]:
            instances = self.client.node_instances.list(deployment_id=dep.id)
            assert instances[0].runtime_properties[
                'capabilities']['capability1'] is None
            exc = self.client.executions.start(
                dep.id, 'execute_operation', parameters={
                    'operation': 'cloudify.interfaces.lifecycle.refresh'
                })
            self.wait_for_execution_to_end(exc)
            instances = self.client.node_instances.list(deployment_id=dep.id)
            assert instances[0].runtime_properties[
                'capabilities']['capability1'] == 42

    def test_component_labeling(self):
        component_blueprint = """
tosca_definitions_version: cloudify_dsl_1_4

imports:
  - cloudify/types/types.yaml

node_templates:
  component_node:
    type: cloudify.nodes.Root
"""
        blueprint_path = self.make_yaml_file(component_blueprint)
        self.client.blueprints.upload(blueprint_path,
                                      entity_id=self.basic_blueprint_id)
        wait_for_blueprint_upload(self.basic_blueprint_id, self.client, True)
        deployment_id = f"parent-{uuid.uuid4()}"
        dsl_path = resource('dsl/component_with_blueprint_id.yaml')
        self.deploy_application(dsl_path, deployment_id=deployment_id)
        component_deployment = self.client.deployments.get(self.component_name)

        component_obj_parent_labels = \
            [lb for lb in component_deployment.labels
             if lb.get('key') == 'csys-obj-parent']
        assert len(component_obj_parent_labels) == 1
        assert component_obj_parent_labels[0].get('value') == deployment_id

        self.undeploy_application(deployment_id, is_delete_deployment=True)
        with pytest.raises(CloudifyClientError):
            self.client.deployments.get(self.component_name)
        with pytest.raises(CloudifyClientError):
            self.client.deployments.get(deployment_id)

    def test_drift(self):
        component_blueprint = """
tosca_definitions_version: cloudify_dsl_1_4

imports:
  - cloudify/types/types.yaml

capabilities:
    test:
        value: 1
"""
        blueprint_path = self.make_yaml_file(component_blueprint)
        self.client.blueprints.upload(blueprint_path,
                                      entity_id=self.basic_blueprint_id)
        wait_for_blueprint_upload(self.basic_blueprint_id, self.client, True)
        dsl_path = resource('dsl/component_with_blueprint_id.yaml')
        self.deploy_application(dsl_path, deployment_id='root_dep')
        self.client.executions.start(
            deployment_id='root_dep',
            workflow_id='check_drift',
        )
        sleep(2)  # give triggered functions some time to run
        node_instance = self.client.node_instances.list(
            deployment_id='root_dep',
            node_id='component_node',
            _include=['id', 'runtime_properties', 'has_configuration_drift'],
        )[0]
        assert node_instance['has_configuration_drift'] is False
        node_instance_rp = node_instance.runtime_properties
        assert 'capabilities' in node_instance_rp
        node_instance_rp['capabilities'].update({'test': 2, 'foo': 'bar'})
        self.client.node_instances.update(
            node_instance['id'],
            runtime_properties=node_instance_rp,
            force=True,
        )

        # Check drift again
        self.client.executions.start(
            deployment_id='root_dep',
            workflow_id='check_drift',
        )
        sleep(2)  # give triggered functions some time to run
        node_instance = self.client.node_instances.get(node_instance.id)
        assert node_instance['has_configuration_drift'] is True
        assert 'configuration_drift' in node_instance.system_properties
        capabilities_drift = node_instance\
            .system_properties['configuration_drift']\
            .get('result', {})\
            .get('capabilities')
        assert capabilities_drift
        assert set(capabilities_drift) == {'test', 'foo'}

        deployment = self.client.deployments.get('root_dep')
        assert deployment.drifted_instances == 1


@wait_for_executions
class ComponentPluginsTest(AgentlessTestCase):
    TEST_PACKAGE_NAME = 'cloudify-script-plugin'
    TEST_PACKAGE_VERSION = '1.2'
    basic_blueprint_id = 'basic'
    test_blueprint = """
tosca_definitions_version: cloudify_dsl_1_4

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
          id: component{3}
      plugins:
        cloudify-script-plugin:
          wagon_path: {0}/{1}
          plugin_yaml_path: {0}/{2}
"""

    def test_not_loading_existing_plugin(self):
        mock_id = upload_mock_plugin(
            self.client,
            self.TEST_PACKAGE_NAME,
            self.TEST_PACKAGE_VERSION
        )['id']
        self.wait_for_all_executions_to_end()
        basic_blueprint_path = resource('dsl/empty_blueprint.yaml')
        self.client.blueprints.upload(basic_blueprint_path,
                                      entity_id=self.basic_blueprint_id)
        wait_for_blueprint_upload(self.basic_blueprint_id, self.client, True)

        deployment_id = 'd{0}'.format(uuid.uuid4())
        main_blueprint = self.test_blueprint.format(
            'https://cloudify-tests-files.s3-eu-west-1.amazonaws.com/plugins',
            'cloudify_script_plugin/1_2/'
            'cloudify_script_plugin-1.2-py27-none-any.wgn',
            'cloudify_script_plugin/1_2/plugin.yaml',
            ''
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
            self.client,
            self.TEST_PACKAGE_NAME,
            self.TEST_PACKAGE_VERSION)['id']
        self.wait_for_all_executions_to_end()
        basic_blueprint_path = resource('dsl/empty_blueprint.yaml')
        self.client.blueprints.upload(basic_blueprint_path,
                                      entity_id=self.basic_blueprint_id)
        wait_for_blueprint_upload(self.basic_blueprint_id, self.client, True)
        deployment_id = 'd{0}'.format(uuid.uuid4())
        main_blueprint = self.test_blueprint.format(
            'https://cloudify-tests-files.s3-eu-west-1.amazonaws.com/plugins',
            'cloudify_script_plugin/2_0/'
            'cloudify_script_plugin-2.0-py27-none-any.wgn',
            'cloudify_script_plugin/2_0/plugin.yaml',
            ''
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

    def test_distro_behaviour(self):
        self.copy_file_to_manager(resource('dsl/plugins'), '/tmp')
        basic_blueprint_path = resource('dsl/empty_blueprint.yaml')
        self.client.blueprints.upload(basic_blueprint_path,
                                      entity_id=self.basic_blueprint_id)
        wait_for_blueprint_upload(self.basic_blueprint_id, self.client, True)

        centos_dep_ip = 'd{0}'.format(uuid.uuid4())
        centos_bp = self.test_blueprint.format(
            '/tmp/plugins/centos_distro',
            'cloudify_script_plugin-1.3-centos-py27-none-any.wgn',
            'plugin.yaml',
            '1'
        )
        self.deploy_application(self.make_yaml_file(centos_bp),
                                deployment_id=centos_dep_ip)
        plugins_list = self.client.plugins.list()
        self.assertEqual(len(plugins_list), 1)

        foobar_dep_ip = 'd{0}'.format(uuid.uuid4())
        foobar_bp = self.test_blueprint.format(
            '/tmp/plugins/foobar_distro',
            'cloudify_script_plugin-1.3-foobar-py27-none-any.wgn',
            'plugin.yaml',
            '2'
        )
        self.deploy_application(self.make_yaml_file(foobar_bp),
                                deployment_id=foobar_dep_ip)
        plugins_list = self.client.plugins.list()
        self.assertEqual(len(plugins_list), 1)

        self.undeploy_application(centos_dep_ip, is_delete_deployment=True)
        self.undeploy_application(foobar_dep_ip, is_delete_deployment=True)
        self.assertEqual(len(self.client.plugins.list()), 0)


@pytest.mark.usefixtures('cloudmock_plugin')
@wait_for_executions
class ComponentSecretsTypesTest(AgentlessTestCase):
    basic_blueprint_id = 'basic'

    def test_basic_types_creation(self):
        basic_blueprint_path = resource('dsl/basic.yaml')
        self.client.blueprints.upload(basic_blueprint_path,
                                      entity_id=self.basic_blueprint_id)
        wait_for_blueprint_upload(self.basic_blueprint_id, self.client, True)
        deployment_id = 'd{0}'.format(uuid.uuid4())
        main_blueprint = """
tosca_definitions_version: cloudify_dsl_1_4

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
        self.assertEqual(self.client.secrets.get('dict')['value'], u"{'a': 1}")
        self.assertEqual(self.client.secrets.get('string')['value'], u'a')
        self.assertEqual(self.client.secrets.get('float')['value'], '1.5')
        self.assertEqual(self.client.secrets.get('boolean')['value'], 'False')
        self.assertEqual(self.client.secrets.get('regex')['value'], u'^.$')


@wait_for_executions
class ComponentInputsTypesTest(AgentlessTestCase):
    basic_blueprint_id = 'basic'

    def test_basic_types(self):
        component_blueprint = """
tosca_definitions_version: cloudify_dsl_1_4

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
                                      entity_id=self.basic_blueprint_id)
        wait_for_blueprint_upload(self.basic_blueprint_id, self.client, True)
        deployment_id = 'd{0}'.format(uuid.uuid4())
        main_blueprint = """
tosca_definitions_version: cloudify_dsl_1_4

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
                                      entity_id=self.basic_blueprint_id)
        wait_for_blueprint_upload(self.basic_blueprint_id, self.client)
        deployment_id = 'd{0}'.format(uuid.uuid4())
        main_blueprint = """
tosca_definitions_version: cloudify_dsl_1_4

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


@wait_for_executions
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
