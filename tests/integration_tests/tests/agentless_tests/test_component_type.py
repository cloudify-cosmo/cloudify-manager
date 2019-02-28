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
        basic_blueprint_path = \
            resource('dsl/basic.yaml')
        self.client.blueprints.upload(basic_blueprint_path,
                                      entity_id='basic')
        deployment_id = 'd{0}'.format(uuid.uuid4())
        dsl_path = resource(
            'dsl/component_with_blueprint_id.yaml')
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
        dsl_path = resource(
            'dsl/component_with_blueprint_package.yaml')
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
        basic_blueprint_path = \
            resource('dsl/basic.yaml')
        self.client.blueprints.upload(basic_blueprint_path,
                                      entity_id='basic')
        deployment_id = 'd{0}'.format(uuid.uuid4())
        dsl_path = resource(
            'dsl/component_with_plugins_and_secrets.yaml')
        self.deploy_application(dsl_path, deployment_id=deployment_id)
        self.assertTrue(self.client.deployments.get(self.component_name))
        self.assertEqual(self.client.secrets.get('secret1')['value'], 'test')
        plugins_list = self.client.plugins.list()
        self.assertEqual(len(plugins_list), 1)
        self.assertTrue(plugins_list[0]['package_name'], 'cloudify-openstack-plugin')
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
        dsl_path = resource(
            'dsl/component_with_blueprint_id.yaml')
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
